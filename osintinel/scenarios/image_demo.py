"""Phase 5 demo: geolocate an uploaded image (doc 06 vertical slice).

> "Upload an image; receive ranked geolocation hypotheses with an explicit contradicting-evidence
> section and recommended next investigations."

A synthesized JPEG carries real EXIF (GPS near Bullington, Hampshire; a June afternoon capture).
The pipeline frames three competing locations and corroborates/refutes them with EXIF, mapped
OSM features (Overpass), an encyclopedic entity (Wikidata), terrain/vegetation/architecture
reads, satellite comparison, a reverse-image caution, and — the headline — **shadow/sun-angle
geometry** computed for each candidate. The Bullington hypothesis is held at HYPOTHESIS while it
rests on EXIF alone, then promoted once independent sources corroborate it; the alpine and
coastal candidates are actively contradicted by the solar geometry and biome reads.

Reuses the Phase 3 cassettes (same coordinate / entity), so the whole thing runs offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..adapters import (
    Cassette,
    ContentAddressedStore,
    HttpClient,
    OverpassAdapter,
    SolarGeometryAdapter,
    WikidataAdapter,
)
from ..adapters.compute.solar import _shadow_azimuth, solar_position
from ..adapters.media.exif import write_exif_jpeg
from ..adapters.registry import AdapterRegistry
from ..pipelines.image_investigation import (
    CandidateLocation,
    ImageInvestigationPipeline,
    ImageInvestigationResult,
)

CASSETTE_DIR = Path(__file__).resolve().parent.parent / "adapters" / "_cassettes"
CAPTURE = "2021:06:21 14:30:00"  # a June afternoon (UTC)

CANDIDATES = [
    CandidateLocation("Bullington ridge, Hampshire", 51.0153, -1.3253),
    CandidateLocation("Alpine summit, Valais", 46.0, 8.0),
    CandidateLocation("Coastal tower, Algarve", 37.1, -8.0),
]
ANNOTATIONS = {
    "terrain": "low chalk ridge with managed pasture",
    "vegetation": "temperate grassland and hedgerows",
    "architecture": "steel lattice mast",
    "architecture_supports": "Bullington ridge, Hampshire",
}


def sample_image_bytes() -> bytes:
    """A deterministic JPEG with EXIF GPS near Bullington and a June afternoon timestamp."""
    return write_exif_jpeg(make="Canon", model="EOS 80D", datetime_original=CAPTURE,
                           lat=51.0153, lon=-1.3253, altitude_m=118.0)


def _observed_shadow_azimuth() -> float:
    """The shadow direction an observer at Bullington would actually see at capture time."""
    when = datetime.strptime(CAPTURE, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
    _elev, az = solar_position(51.0153, -1.3253, when)
    return round(_shadow_azimuth(az), 1)


def build_image_registry(cas: ContentAddressedStore, *, record: bool = False) -> AdapterRegistry:
    def client(name: str) -> HttpClient:
        return HttpClient(Cassette(CASSETTE_DIR / f"{name}.json"), record=record)

    reg = AdapterRegistry()
    reg.register(OverpassAdapter(client("overpass")), effectiveness=0.8)
    reg.register(WikidataAdapter(client("wikidata")), effectiveness=0.75)
    reg.register(SolarGeometryAdapter(), effectiveness=0.9)
    return reg


def run_image_demo(*, cas_dir=None) -> ImageInvestigationResult:
    cas = ContentAddressedStore(cas_dir or __import__("tempfile").mkdtemp())
    registry = build_image_registry(cas)
    pipeline = ImageInvestigationPipeline(registry, cas)
    return pipeline.run(
        image_bytes=sample_image_bytes(),
        candidates=CANDIDATES,
        observed_shadow_azimuth=_observed_shadow_azimuth(),
        annotations=ANNOTATIONS,
        geo_queries={
            "overpass": {"lat": 51.0153, "lon": -1.3253, "radius": 500, "key": "man_made"},
            "wikidata": {"qid": "Q12345", "supports": "Bullington ridge, Hampshire"},
        },
    )
