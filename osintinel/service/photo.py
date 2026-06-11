"""Photo analysis (shared by every front door) — EXIF + sun/shadow geometry.

Pulls camera, capture time, and GPS from a JPEG's EXIF, and — when the photo is both geotagged and
timestamped — computes the sun elevation/azimuth and shadow bearing at that place and time. Returns
a plain dict so each surface (TUI markup, web HTML) can render it its own way. Pure; no network.
"""

from __future__ import annotations

from datetime import datetime, timezone


def analyze_photo(data: bytes) -> dict:
    """Structured 'what does this photo reveal' read. ``{"ok": False, "reason": "no_exif"}`` when
    there's no readable EXIF (e.g. a non-JPEG, or HEIC)."""
    from ..adapters.media.exif import parse_exif

    exif = parse_exif(data)
    if not exif:
        return {"ok": False, "reason": "no_exif"}

    out: dict = {
        "ok": True,
        "camera": " ".join(p for p in (exif.get("make"), exif.get("model")) if p) or None,
        "captured": exif.get("datetime_original"),
        "gps": None,
        "sun": None,
    }
    gps = exif.get("gps")
    if gps:
        out["gps"] = {"lat": gps["lat"], "lon": gps["lon"], "altitude_m": gps.get("altitude_m")}
        if out["captured"]:
            from ..adapters.compute.solar import _shadow_azimuth, solar_position
            try:
                when = datetime.strptime(out["captured"], "%Y:%m:%d %H:%M:%S").replace(
                    tzinfo=timezone.utc)
                elev, az = solar_position(gps["lat"], gps["lon"], when)
                out["sun"] = {"elevation": round(elev, 1), "azimuth": round(az, 1),
                              "shadow": round(_shadow_azimuth(az), 1)}
            except ValueError:
                pass
    return out


def osm_url(lat: float, lon: float) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
