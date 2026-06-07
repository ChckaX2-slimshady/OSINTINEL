"""Tool adapter framework (doc 05). Tools reach the world only through adapters.

Phase 3 adds lawful, public-source reference adapters behind the same Protocol, a
cassette-backed transport for offline replay, and a content-addressed store so heavy artifacts
never enter the ledger. Supplemental commercial sources live in ``commercial/``, license-gated
and off by default.
"""

from .archives import WaybackAdapter, WikidataAdapter
from .base import Adapter, AdapterError, RawArtifact, RawHit, ReferenceAdapter
from .compute import SolarGeometryAdapter
from .geospatial import NominatimAdapter, OverpassAdapter
from .infrastructure import (
    CertTransparencyAdapter,
    ShodanInternetDBAdapter,
    UrlscanAdapter,
)
from .threat import OTXAdapter
from .media import ExifAdapter
from .registry import AdapterRegistry
from .storage import ContentAddressedStore
from .stub import StubEvidenceAdapter
from .web import WebSearchAdapter
from .transport import Cassette, HttpClient

__all__ = [
    "Adapter",
    "AdapterError",
    "AdapterRegistry",
    "Cassette",
    "CertTransparencyAdapter",
    "OTXAdapter",
    "ShodanInternetDBAdapter",
    "UrlscanAdapter",
    "ContentAddressedStore",
    "ExifAdapter",
    "HttpClient",
    "NominatimAdapter",
    "OverpassAdapter",
    "RawArtifact",
    "RawHit",
    "ReferenceAdapter",
    "SolarGeometryAdapter",
    "StubEvidenceAdapter",
    "WaybackAdapter",
    "WebSearchAdapter",
    "WikidataAdapter",
]
