"""Capability tags (doc 05 §2). Adapters are selected by capability, not by name."""

from __future__ import annotations

# A representative, extensible set. The registry maps each tag to adapter ids.
CAPABILITIES = {
    # geospatial
    "geo.geocode", "geo.reverse_geocode", "geo.features", "geo.streetlevel", "geo.satellite",
    # infrastructure
    "infra.dns", "infra.subdomains", "infra.asn", "infra.certs",
    "infra.exposure", "infra.urlscan", "threat.intel",
    # identity
    "identity.username", "identity.profile",
    # archives
    "archive.snapshot", "archive.timemap", "archive.media",
    # documents
    "doc.ocr", "doc.metadata", "doc.pdf",
    # media
    "media.exif", "media.metadata", "media.reverse_image", "media.similarity",
    # web research
    "web.search", "web.fetch",
    # reference / compute
    "record.public", "dataset.open", "reference.encyclopedic", "compute.symbolic",
    # link analysis (supplemental, license-gated)
    "link.analysis",
    # phase 1 deterministic stub
    "stub.evidence",
}
