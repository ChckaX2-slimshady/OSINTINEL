"""EXIF read/write for JPEG (doc 05 §4 ``media.exif``) — the image-binary path deferred from
Phase 3 (doc 06 §Phase 3).

A small, dependency-free TIFF/EXIF codec for exactly the tags an image investigation needs:
camera ``Make``/``Model``, ``DateTimeOriginal``, and GPS latitude/longitude/altitude. ``parse_exif``
is a pure reader; ``write_exif_jpeg`` synthesizes a minimal valid JPEG carrying these tags (used
to build deterministic sample/fixture images). The two are paired and round-trip exactly.

Only little-endian ("II") EXIF is emitted; the reader accepts both byte orders.
"""

from __future__ import annotations

import struct
from typing import Any

# TIFF field types we use.
_ASCII, _SHORT, _LONG, _RATIONAL, _BYTE = 2, 3, 4, 5, 1
# Tag ids.
_MAKE, _MODEL, _DATETIME = 0x010F, 0x0110, 0x0132
_EXIF_IFD_PTR, _GPS_IFD_PTR = 0x8769, 0x8825
_DATETIME_ORIGINAL = 0x9003
_GPS_LATREF, _GPS_LAT, _GPS_LONREF, _GPS_LON, _GPS_ALTREF, _GPS_ALT = 1, 2, 3, 4, 5, 6

_EXIF_PREFIX = b"Exif\x00\x00"


# --------------------------------------------------------------------------- write
def _deg_to_dms_rationals(value: float) -> list[tuple[int, int]]:
    value = abs(value)
    deg = int(value)
    minutes_full = (value - deg) * 60
    minutes = int(minutes_full)
    seconds = round((minutes_full - minutes) * 60, 4)
    return [(deg, 1), (minutes, 1), (int(seconds * 10000), 10000)]


def write_exif_jpeg(*, make: str, model: str, datetime_original: str,
                    lat: float, lon: float, altitude_m: float) -> bytes:
    """Build a minimal JPEG whose APP1 segment carries the given EXIF tags (little-endian)."""
    # IFD sizes are fixed for our tag set; everything past the three IFDs is the data area.
    ifd0_size = 2 + 5 * 12 + 4      # Make, Model, DateTime, EXIF-ptr, GPS-ptr
    exif_size = 2 + 1 * 12 + 4      # DateTimeOriginal
    gps_size = 2 + 6 * 12 + 4       # refs + lat/lon/alt
    exif_off = 8 + ifd0_size
    gps_off = exif_off + exif_size
    data_base = gps_off + gps_size

    data = bytearray()

    def put_ascii(s: str) -> int:
        off = data_base + len(data)
        data.extend(s.encode("ascii") + b"\x00")
        return off

    def put_rationals(pairs: list[tuple[int, int]]) -> int:
        off = data_base + len(data)
        for num, den in pairs:
            data.extend(struct.pack("<II", num, den))
        return off

    def ascii_entry(tag: int, s: str) -> bytes:
        raw = s.encode("ascii") + b"\x00"
        count = len(raw)
        if count <= 4:
            value = raw + b"\x00" * (4 - count)
            return struct.pack("<HHI", tag, _ASCII, count) + value
        return struct.pack("<HHII", tag, _ASCII, count, put_ascii(s))

    # GPS IFD ------------------------------------------------------------------
    lat_ref = "N" if lat >= 0 else "S"
    lon_ref = "E" if lon >= 0 else "W"
    gps_entries = [
        struct.pack("<HHI", _GPS_LATREF, _ASCII, 2) + (lat_ref.encode() + b"\x00\x00\x00")[:4],
        struct.pack("<HHII", _GPS_LAT, _RATIONAL, 3, put_rationals(_deg_to_dms_rationals(lat))),
        struct.pack("<HHI", _GPS_LONREF, _ASCII, 2) + (lon_ref.encode() + b"\x00\x00\x00")[:4],
        struct.pack("<HHII", _GPS_LON, _RATIONAL, 3, put_rationals(_deg_to_dms_rationals(lon))),
        struct.pack("<HHI", _GPS_ALTREF, _BYTE, 1) + (b"\x00" if altitude_m >= 0 else b"\x01")
        + b"\x00\x00\x00",
        struct.pack("<HHII", _GPS_ALT, _RATIONAL, 1, put_rationals([(int(abs(altitude_m) * 100), 100)])),
    ]
    gps_ifd = struct.pack("<H", len(gps_entries)) + b"".join(gps_entries) + struct.pack("<I", 0)

    # EXIF IFD -----------------------------------------------------------------
    exif_entries = [ascii_entry(_DATETIME_ORIGINAL, datetime_original)]
    exif_ifd = struct.pack("<H", len(exif_entries)) + b"".join(exif_entries) + struct.pack("<I", 0)

    # IFD0 ---------------------------------------------------------------------
    ifd0_entries = [
        ascii_entry(_MAKE, make),
        ascii_entry(_MODEL, model),
        ascii_entry(_DATETIME, datetime_original),
        struct.pack("<HHII", _EXIF_IFD_PTR, _LONG, 1, exif_off),
        struct.pack("<HHII", _GPS_IFD_PTR, _LONG, 1, gps_off),
    ]
    ifd0 = struct.pack("<H", len(ifd0_entries)) + b"".join(ifd0_entries) + struct.pack("<I", 0)

    tiff = struct.pack("<2sHI", b"II", 0x002A, 8) + ifd0 + exif_ifd + gps_ifd + bytes(data)
    app1_payload = _EXIF_PREFIX + tiff
    app1 = b"\xff\xe1" + struct.pack(">H", len(app1_payload) + 2) + app1_payload

    # SOI + APP1 + a 1x1 grey scan so the file is a structurally complete JPEG.
    body = (b"\xff\xdb\x00\x43\x00" + bytes([16] * 64)  # quant table
            + b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"  # SOF0 1x1
            + b"\xff\xc4\x00\x14\x00\x01" + b"\x00" * 15 + b"\x08"  # trivial DC huffman
            + b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\x00"  # SOS + 1 byte
            + b"\xff\xd9")  # EOI
    return b"\xff\xd8" + app1 + body


# --------------------------------------------------------------------------- read
def _unpack(order: str, fmt: str, data: bytes, off: int):
    return struct.unpack_from(order + fmt, data, off)


def _read_ifd(tiff: bytes, order: str, ifd_off: int) -> dict[int, tuple[int, int, int]]:
    """Return {tag: (type, count, value_or_offset)} for one IFD."""
    (count,) = _unpack(order, "H", tiff, ifd_off)
    entries: dict[int, tuple[int, int, int]] = {}
    for i in range(count):
        base = ifd_off + 2 + i * 12
        tag, typ, cnt = _unpack(order, "HHI", tiff, base)
        (val,) = _unpack(order, "I", tiff, base + 8)
        entries[tag] = (typ, cnt, val)
    return entries


def _ascii_value(tiff: bytes, entry: tuple[int, int, int], order: str, base: int) -> str:
    typ, cnt, val = entry
    raw = (struct.pack(order + "I", val) if cnt <= 4 else tiff[base + val:base + val + cnt])
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def _rationals(tiff: bytes, entry: tuple[int, int, int], order: str, base: int) -> list[float]:
    _typ, cnt, val = entry
    out = []
    for i in range(cnt):
        num, den = _unpack(order, "II", tiff, base + val + i * 8)
        out.append(num / den if den else 0.0)
    return out


def _dms_to_deg(parts: list[float], ref: str) -> float:
    deg = parts[0] + parts[1] / 60 + parts[2] / 3600
    return -deg if ref in ("S", "W") else deg


def parse_exif(jpeg: bytes) -> dict[str, Any]:
    """Extract camera + GPS fields from a JPEG's EXIF. Returns {} if no EXIF present."""
    if not jpeg.startswith(b"\xff\xd8"):
        return {}
    # locate the APP1/Exif segment
    i = 2
    tiff = b""
    while i + 4 <= len(jpeg):
        if jpeg[i] != 0xFF:
            break
        marker = jpeg[i + 1]
        (seg_len,) = struct.unpack_from(">H", jpeg, i + 2)
        seg = jpeg[i + 4:i + 2 + seg_len]
        if marker == 0xE1 and seg.startswith(_EXIF_PREFIX):
            tiff = seg[len(_EXIF_PREFIX):]
            break
        i += 2 + seg_len
    if not tiff:
        return {}

    order = "<" if tiff[:2] == b"II" else ">"
    (ifd0_off,) = _unpack(order, "I", tiff, 4)
    ifd0 = _read_ifd(tiff, order, ifd0_off)

    out: dict[str, Any] = {}
    if _MAKE in ifd0:
        out["make"] = _ascii_value(tiff, ifd0[_MAKE], order, 0)
    if _MODEL in ifd0:
        out["model"] = _ascii_value(tiff, ifd0[_MODEL], order, 0)
    if _EXIF_IFD_PTR in ifd0:
        exif_ifd = _read_ifd(tiff, order, ifd0[_EXIF_IFD_PTR][2])
        if _DATETIME_ORIGINAL in exif_ifd:
            out["datetime_original"] = _ascii_value(tiff, exif_ifd[_DATETIME_ORIGINAL], order, 0)
    if "datetime_original" not in out and _DATETIME in ifd0:
        out["datetime_original"] = _ascii_value(tiff, ifd0[_DATETIME], order, 0)

    if _GPS_IFD_PTR in ifd0:
        gps = _read_ifd(tiff, order, ifd0[_GPS_IFD_PTR][2])
        if _GPS_LAT in gps and _GPS_LON in gps:
            lat_ref = _ascii_value(tiff, gps[_GPS_LATREF], order, 0) if _GPS_LATREF in gps else "N"
            lon_ref = _ascii_value(tiff, gps[_GPS_LONREF], order, 0) if _GPS_LONREF in gps else "E"
            lat = _dms_to_deg(_rationals(tiff, gps[_GPS_LAT], order, 0), lat_ref)
            lon = _dms_to_deg(_rationals(tiff, gps[_GPS_LON], order, 0), lon_ref)
            gps_out = {"lat": round(lat, 6), "lon": round(lon, 6)}
            if _GPS_ALT in gps:
                gps_out["altitude_m"] = round(_rationals(tiff, gps[_GPS_ALT], order, 0)[0], 2)
            out["gps"] = gps_out
    return out
