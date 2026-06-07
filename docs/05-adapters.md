# 05 — Adapter Specifications

OSINTINEL reaches the outside world **only** through adapters. We implement *adapters rather
than direct integrations* so tools stay interchangeable and investigative paths are never
hardcoded. The Tool Selection Agent chooses adapters dynamically by capability (doc 02 §4).

## 1. Standard Adapter Interface

Every adapter implements the same five operations. All operations emit **standardized
schemas** (doc 03) and stamp provenance.

```python
class Adapter(Protocol):
    id: str                         # e.g. "osm.overpass", "wayback.cdx"
    capabilities: list[CapabilityTag]
    cost_model: CostModel           # est. tokens/money/seconds/requests per op
    rate_limit: RateLimit
    auth: AuthSpec | None           # public/free by default; keys via env only
    legal_note: str                 # ToS/licensing notes (doc 07)

    async def search(self, query: SearchQuery) -> list[RawHit]: ...
    async def lookup(self, key: LookupKey) -> RawRecord: ...
    async def collect(self, target: CollectTarget) -> RawArtifact: ...   # bytes/files
    def parse(self, raw: RawArtifact | RawRecord) -> list[ParsedItem]: ...
    def normalize(self, parsed: ParsedItem) -> Observation | EvidenceObject: ...
```

- `search` — discovery (returns references/candidates).
- `lookup` — resolve a known key to a record.
- `collect` — fetch a concrete artifact (image, page, dataset) content-addressed to storage.
- `parse` — turn raw payload into intermediate items (pure, deterministic).
- `normalize` — emit the canonical `Observation`/`EvidenceObject` with provenance.

Not every adapter supports every verb; it declares which it implements. The split keeps the
network/IO boundary (`search/lookup/collect`, async, recorded to the ledger for replay)
separate from deterministic transformation (`parse/normalize`, pure, unit-testable).

## 2. Capability Model

Adapters are selected by **capability tags**, not by name, so they are interchangeable.
Example tags:

```
geo.geocode · geo.reverse_geocode · geo.features · geo.streetlevel · geo.satellite
infra.dns · infra.subdomains · infra.asn · infra.certs
identity.username · identity.profile
archive.snapshot · archive.timemap · archive.media
doc.ocr · doc.metadata · doc.pdf
media.exif · media.reverse_image · media.similarity
record.public · dataset.open · reference.encyclopedic · compute.symbolic
```

The Adapter Registry maps `capability -> [adapter ids]` with their cost/effectiveness priors
(seeded from defaults, refined by Investigation Memory).

## 3. Registry & Selection Contract

```python
class AdapterRegistry:
    def by_capability(self, tag: CapabilityTag) -> list[Adapter]: ...
    def get(self, adapter_id: str) -> Adapter: ...
    def cost_of(self, adapter_id: str, op: str) -> CostEstimate: ...
    def effectiveness(self, adapter_id: str, context) -> float:  # from Memory
```

Selection prefers: higher effectiveness prior · lower cost · rate-limit headroom · **source
independence** from already-used sources for the same hypothesis (doc 02 §4). Every adapter
result records the originating `ToolPlan` and a raw-response `LedgerEvent` so the run is
replayable without re-hitting the network (doc 01 §7).

## 4. Basic Adapter Framework

Adapters are **lawful, public-source only** (doc 07). Anything requiring intrusion,
authentication bypass, or non-public access is out of scope. This is the default catalogue;
the licensed/commercial tools are in the **Supplemental Adapter Framework** (§4b).

### Geospatial — `geo.*`
- OpenStreetMap / **Overpass API** (`geo.features`), **Nominatim** (`geo.geocode`,
  `geo.reverse_geocode`), **Mapillary** (`geo.streetlevel`), **Wikimapia**, satellite imagery
  providers (`geo.satellite`, license-gated).

### Infrastructure — `infra.*`
- **Amass**, **Subfinder** (`infra.subdomains`), DNS intelligence (`infra.dns`), ASN
  intelligence (`infra.asn`), Certificate Transparency (`infra.certs`).

### Identity — `identity.*`
- **Sherlock** (`identity.username`), public profile discovery (`identity.profile`), username
  correlation. *Public profiles only; no scraping behind authentication.*

### Archives — `archive.*`
- **Wayback Machine** (CDX/timemap), **Archive.today**, **Wikimedia Commons**, **Wikidata**.

### Document Analysis — `doc.*`
- OCR (`doc.ocr`), metadata extraction (`doc.metadata`), PDF analysis (`doc.pdf`).

### Media Analysis — `media.*`
- **ExifTool** (`media.exif`), reverse image search (`media.reverse_image`), similarity search
  (`media.similarity`).

### Reference / Compute
- Encyclopedic & open datasets (`reference.encyclopedic`, `dataset.open`), Wolfram-style
  symbolic compute (`compute.symbolic`) for shadow/sun-angle, distance, and timeline math.

### Web research — `web.*`
- **Open-web search + fetch** (`web.search`, `web.fetch`): a `WebSearchAdapter` so an
  investigation gathers its own evidence. Lawful, free, **no-key** backends — **Wikipedia**
  (MediaWiki search + REST page-summary, the default) and **DuckDuckGo lite** (HTML, for diverse
  domains). Fetched bytes go to the CAS; evidence is grouped by registrable domain so the
  embed-tier independence check is not fooled by same-site pages.

### Implemented adapter inventory (all free / lawful)
`geo.geocode`/`geo.reverse_geocode` (Nominatim) · `geo.features` (Overpass) ·
`archive.timemap`/`archive.snapshot` (Wayback) · `reference.encyclopedic` (Wikidata) ·
`infra.certs` (crt.sh Certificate Transparency) · `infra.exposure` (Shodan InternetDB, no key) ·
`infra.urlscan` (URLScan.io, no key) · `threat.intel` (AlienVault OTX, free key) ·
`media.exif` (built-in EXIF codec) · `compute.symbolic` (NOAA solar geometry) ·
`web.search`/`web.fetch` (Wikipedia/DuckDuckGo).

## 4b. Supplemental Adapter Framework (license-gated, off by default)

The brief's supplemental resources — across Social Media (Skopenow, Social Links,
ShadowDragon), Dark Web (DarkBlue, DarkOwl Vision, NexVision), Due Diligence (Neotas,
Factiva, Videris), Link Analysis (Analyst's Notebook, Siren, Recorded Future), Web
Intelligence (Silobreaker, Media Sonar, Cobwebs), People ID (Maltego, Pipl), Risk & Crisis
(VoxCroft, Logically, Talkwalker), Images (PimEyes, CHAPSVISION, CameraForensics), and Threat
Intel (KELA, Intel471 Titan, CYWARE) — are modeled as **license-gated adapters** behind the
same interface. They are never enabled implicitly; the operator must supply credentials and
attest to authorized use. Provenance records which licensed source was used.

**Integration status (honest):** *none* of these commercial sources are functionally
integrated — they are all paid/licensed. Only the **gating mechanism** (`commercial/base.py`)
and a representative **Maltego stub** exist, off unless credentials + attestation are supplied.
The deliberate emphasis is on **free, lawful** sources (the inventory above). **Shodan
InternetDB**, **URLScan.io**, and **AlienVault OTX** are now built (`infra.exposure`,
`infra.urlscan`, `threat.intel`). Further high-value free additions that fit the same pattern:
**OpenCorporates** / **SEC EDGAR** / **GLEIF** (`record.public`, free), **Mapillary**
(`geo.streetlevel`, free key), **abuse.ch** (threat, free key), and **Brave Search** / **SearXNG**
backends for `web.search`.

## 5. Adapter Authoring Rules

1. **Standard schemas only out.** `normalize` must emit valid `Observation`/`EvidenceObject`
   with full provenance — including `tool_used`, `acquisition_method`, `url`, `content_hash`,
   and `license_note`.
2. **No hidden state / no side effects beyond declared IO.** `parse`/`normalize` are pure.
3. **Declare cost & rate limits honestly** — the planner and Budget Governor depend on them.
4. **Fail as data.** Network/ToS/quota errors return a typed `AdapterError` (recorded as tool-
   effectiveness signal), never an unhandled exception.
5. **Respect robots/ToS & rate limits.** Adapters honor `robots.txt`, site ToS, and polite
   rate limiting; non-compliant access patterns are rejected at review.
6. **Content-address artifacts.** `collect` stores bytes by hash so identical fetches
   deduplicate and replay is exact.
7. **Replayable.** Every external call writes a raw-response ledger event; a `replay` flag
   serves recorded responses for tests.

## 6. Testing Adapters

Each adapter ships: pure unit tests for `parse`/`normalize` against recorded fixtures
(VCR-style cassettes), a contract test asserting interface conformance and schema-valid
output, and a live "smoke" test (opt-in, network-gated) excluded from CI default. See
[09-testing-methodology.md](09-testing-methodology.md).
