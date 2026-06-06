"""EXIF codec + adapter: real binary round-trip and the image→CAS heavy path (doc 05/06)."""

from __future__ import annotations

import pytest

from osintenal.adapters import ContentAddressedStore
from osintenal.adapters.media.exif import parse_exif, write_exif_jpeg
from osintenal.adapters.media.exif_adapter import ExifAdapter
from osintenal.adapters.storage import CAS_SCHEME
from osintenal.core.schemas import AcquisitionMethod, AgentName, EvidenceObject, Provenance


def _prov() -> Provenance:
    return Provenance(source="x", acquisition_method=AcquisitionMethod.FILE_UPLOAD,
                      agent_responsible=AgentName.AGGREGATION, confidence=0.9, investigation_id="i")


@pytest.mark.parametrize("lat,lon", [(51.0153, -1.3253), (-33.8688, 151.2093), (0.0, 0.0)])
def test_exif_roundtrips_real_binary(lat, lon):
    jpeg = write_exif_jpeg(make="Canon", model="EOS 5D", datetime_original="2021:06:21 14:30:00",
                           lat=lat, lon=lon, altitude_m=120.5)
    assert jpeg.startswith(b"\xff\xd8") and jpeg.endswith(b"\xff\xd9")  # valid JPEG envelope
    exif = parse_exif(jpeg)
    assert exif["make"] == "Canon" and exif["model"] == "EOS 5D"
    assert exif["datetime_original"] == "2021:06:21 14:30:00"
    assert exif["gps"]["lat"] == pytest.approx(lat, abs=1e-3)
    assert exif["gps"]["lon"] == pytest.approx(lon, abs=1e-3)
    assert exif["gps"]["altitude_m"] == pytest.approx(120.5, abs=0.1)


def test_non_exif_bytes_return_empty():
    assert parse_exif(b"not a jpeg") == {}
    assert parse_exif(b"\xff\xd8\xff\xd9") == {}  # JPEG with no APP1


def test_exif_adapter_routes_image_to_cas_and_emits_gps_evidence(tmp_path):
    cas = ContentAddressedStore(tmp_path)
    jpeg = write_exif_jpeg(make="Nikon", model="Z6", datetime_original="2020:01:01 09:00:00",
                           lat=48.8584, lon=2.2945, altitude_m=33.0)
    adapter = ExifAdapter(cas)
    ev = adapter.acquire_image(jpeg, _prov())[0]

    assert isinstance(ev, EvidenceObject)
    assert ev.payload_ref.startswith(CAS_SCHEME)
    assert cas.has(ev.provenance.content_hash)          # image bytes recoverable by hash
    assert cas.get(ev.provenance.content_hash) == jpeg  # exact bytes
    assert ev.structured["gps"]["lat"] == pytest.approx(48.8584, abs=1e-3)
    assert ev.provenance.tool_used == "media.exiftool"
    assert ev.provenance.acquisition_method is AcquisitionMethod.FILE_UPLOAD
