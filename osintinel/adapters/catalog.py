"""Adapter / tool catalog (doc 05) — the full capability inventory OSINTINEL knows about.

A single, declarative source of truth spanning the **basic framework** (lawful, free, public
sources — implemented or planned) and the **supplemental framework** (license-gated commercial
tools, off by default). Front doors render this so an operator can *see every tool* and its status
at a glance. Status is one of:

* ``live``     — implemented and usable now (free/lawful).
* ``planned``  — fits the same adapter pattern; a near-term free addition.
* ``gated``    — commercial/license-gated; off unless credentials + attestation are supplied.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    name: str
    capability: str
    status: str          # "live" | "planned" | "gated"
    note: str = ""


@dataclass(frozen=True)
class Category:
    title: str
    tools: list[Tool]


# -- basic framework: lawful, free, public-source (doc 05 §4) ----------------
BASIC: list[Category] = [
    Category("Web research", [
        Tool("Wikipedia (MediaWiki + REST)", "web.search / web.fetch", "live", "default; no key"),
        Tool("DuckDuckGo (lite)", "web.search", "live", "diverse domains; no key"),
        Tool("Brave Search", "web.search", "planned", "free key"),
        Tool("SearXNG", "web.search", "planned", "self-hosted meta-search"),
    ]),
    Category("Geospatial", [
        Tool("Nominatim", "geo.geocode / geo.reverse_geocode", "live", "OSM; no key"),
        Tool("Overpass", "geo.features", "live", "OSM map features; no key"),
        Tool("Mapillary", "geo.streetlevel", "planned", "free key"),
        Tool("Satellite imagery", "geo.satellite", "gated", "provider license"),
    ]),
    Category("Infrastructure", [
        Tool("Certificate Transparency (crt.sh)", "infra.certs", "live", "no key"),
        Tool("Shodan InternetDB", "infra.exposure", "live", "no key"),
        Tool("URLScan.io", "infra.urlscan", "live", "no key"),
        Tool("Amass / Subfinder", "infra.subdomains", "planned", "subdomain enumeration"),
        Tool("DNS over HTTPS (Google)", "infra.dns", "live", "no key"),
        Tool("ASN / network (RIPEstat)", "infra.asn", "live", "no key"),
    ]),
    Category("Threat intelligence", [
        Tool("AlienVault OTX", "threat.intel", "live", "free key"),
        Tool("abuse.ch", "threat.intel", "planned", "free key"),
    ]),
    Category("Public records", [
        Tool("OpenCorporates", "record.public", "live", "optional free token"),
        Tool("SEC EDGAR", "record.public", "live", "no key"),
        Tool("GLEIF (legal entities)", "record.public", "live", "no key"),
    ]),
    Category("Archives & reference", [
        Tool("Wayback Machine", "archive.snapshot / archive.timemap", "live", "no key"),
        Tool("Wikidata", "reference.encyclopedic", "live", "no key"),
        Tool("Archive.today", "archive.snapshot", "planned", ""),
        Tool("Wikimedia Commons", "archive.media", "live", "no key; open-licensed media"),
    ]),
    Category("Media & documents", [
        Tool("EXIF codec (built-in)", "media.exif", "live", "geotag + camera/time"),
        Tool("Solar geometry (NOAA)", "compute.symbolic", "live", "sun/shadow angles"),
        Tool("Reverse image search", "media.reverse_image", "planned", ""),
        Tool("OCR", "doc.ocr", "planned", ""),
        Tool("PDF / metadata extraction", "doc.pdf / doc.metadata", "planned", ""),
    ]),
    Category("Identity", [
        Tool("Sherlock (usernames)", "identity.username", "planned", "public profiles only"),
        Tool("Public profile discovery", "identity.profile", "planned", "no auth bypass"),
    ]),
]

# -- supplemental framework: license-gated commercial tools (doc 05 §4b) -----
# Off by default — never enabled implicitly; operator must supply credentials AND attest to
# authorized use (OSINTINEL_ATTEST_AUTHORIZED=1). None are functionally integrated (all paid).
SUPPLEMENTAL: list[Category] = [
    Category("Social media intelligence", [
        Tool("Skopenow", "social.profile", "gated"), Tool("Social Links", "social.graph", "gated"),
        Tool("ShadowDragon", "social.monitor", "gated")]),
    Category("Dark web", [
        Tool("DarkBlue", "darkweb.search", "gated"), Tool("DarkOwl Vision", "darkweb.search", "gated"),
        Tool("NexVision", "darkweb.search", "gated")]),
    Category("Due diligence", [
        Tool("Neotas", "diligence.background", "gated"), Tool("Factiva", "diligence.news", "gated"),
        Tool("Videris", "diligence.graph", "gated")]),
    Category("Link analysis", [
        Tool("Maltego", "link.analysis", "gated"), Tool("Siren", "link.analysis", "gated"),
        Tool("Recorded Future", "threat.intel", "gated")]),
    Category("Web intelligence", [
        Tool("Silobreaker", "web.intel", "gated"), Tool("Media Sonar", "web.intel", "gated"),
        Tool("Cobwebs", "web.intel", "gated")]),
    Category("People identification", [
        Tool("Pipl", "identity.profile", "gated"), Tool("Maltego (people)", "identity.profile", "gated")]),
    Category("Risk & crisis", [
        Tool("VoxCroft", "risk.monitor", "gated"), Tool("Logically", "risk.misinfo", "gated"),
        Tool("Talkwalker", "risk.monitor", "gated")]),
    Category("Image intelligence", [
        Tool("PimEyes", "media.reverse_image", "gated"), Tool("CameraForensics", "media.reverse_image", "gated"),
        Tool("CHAPSVISION", "media.analysis", "gated")]),
    Category("Threat intel (commercial)", [
        Tool("KELA", "threat.intel", "gated"), Tool("Intel471 Titan", "threat.intel", "gated"),
        Tool("CYWARE", "threat.intel", "gated")]),
]


def counts() -> dict[str, int]:
    """How many tools at each status across both frameworks (for headline KPIs)."""
    out = {"live": 0, "planned": 0, "gated": 0}
    for cat in BASIC + SUPPLEMENTAL:
        for t in cat.tools:
            out[t.status] = out.get(t.status, 0) + 1
    return out
