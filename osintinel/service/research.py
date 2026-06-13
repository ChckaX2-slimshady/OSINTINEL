"""Autonomous web research — the one entrypoint every front door (CLI, TUI, web, MCP) shares.

Builds a live, SSRF-guarded, polite open-web adapter and drives the iterative research loop:
search several engines per query (DuckDuckGo for diverse domains + Wikipedia for reliable content),
let the reason model frame competing answers, chase the Epistemology agent's known-unknowns for
more (and contrary) evidence, run the Skeptic/independence gauntlet, and surface the insights that
survived. ``web_adapter`` is injectable for tests.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from .investigation import EvidenceInput, InvestigationResult, autoresearch_investigation

_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_URL = re.compile(r"https?://[^\s)<>\"']+")
_DOMAIN = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)
# free, keyless adapters the autonomous loop can fire on an entity it finds
CORROBORATORS = ("infra.exposure", "infra.certs", "infra.dns", "infra.asn", "archive.snapshot")


def live_web_adapter(backend: str = "wikipedia"):
    """A web-research adapter wired for live, SSRF-guarded, rate-limited open-web fetches."""
    from ..adapters import Cassette, ContentAddressedStore, HttpClient, WebSearchAdapter
    cas = ContentAddressedStore(tempfile.mkdtemp())
    http = HttpClient(Cassette(Path(tempfile.mkdtemp()) / "web.json"), mode="live",
                      block_private_net=True, min_interval=1.0)
    return WebSearchAdapter(http, cas, backend=backend)


def _entities(text: str) -> tuple[list[str], list[str], list[str]]:
    ips = [ip for ip in dict.fromkeys(_IP.findall(text))
           if all(o.isdigit() and 0 <= int(o) <= 255 for o in ip.split("."))]
    urls = list(dict.fromkeys(_URL.findall(text)))
    in_urls = " ".join(urls)
    domains = [d.lower() for d in dict.fromkeys(_DOMAIN.findall(text))
               if not _IP.fullmatch(d) and d not in in_urls and "." in d]
    return ips[:2], domains[:2], urls[:2]


def corroborate_entities(text: str, *, want=CORROBORATORS) -> list[EvidenceInput]:
    """Fire the free keyless adapters on any IP/domain/URL found in ``text`` — the corroboration
    stage of an autonomous run. Each adapter failure is swallowed (the entity just adds nothing)."""
    from ..adapters import (
        AsnAdapter,
        Cassette,
        CertTransparencyAdapter,
        ContentAddressedStore,
        DnsAdapter,
        HttpClient,
        ShodanInternetDBAdapter,
        WaybackAdapter,
    )
    from ..adapters.transport import AdapterError
    from ..core.schemas import AcquisitionMethod, AgentName, Provenance

    ips, domains, urls = _entities(text)

    def http() -> HttpClient:
        return HttpClient(Cassette(Path(tempfile.mkdtemp()) / "c.json"), mode="live",
                          block_private_net=True, min_interval=1.0)

    def prov() -> Provenance:
        return Provenance(source="corroboration", acquisition_method=AcquisitionMethod.API,
                          agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                          investigation_id="web-research")

    def to_inputs(evs) -> list[EvidenceInput]:
        return [EvidenceInput(text=e.summary, source=e.provenance.source,
                              group=e.structured.get("independence_group"), kind=e.kind,
                              url=e.provenance.url) for e in evs]

    out: list[EvidenceInput] = []
    jobs = []
    if "infra.exposure" in want:
        jobs += [(ShodanInternetDBAdapter(http()), "infra.exposure", {"ip": ip}) for ip in ips]
    if "infra.asn" in want:
        jobs += [(AsnAdapter(http()), "infra.asn", {"ip": ip}) for ip in ips]
    if "infra.certs" in want:
        jobs += [(CertTransparencyAdapter(http()), "infra.certs", {"domain": d}) for d in domains]
    if "infra.dns" in want:
        jobs += [(DnsAdapter(http()), "infra.dns", {"domain": d}) for d in domains]
    if "archive.snapshot" in want:
        cas = ContentAddressedStore(tempfile.mkdtemp())
        jobs += [(WaybackAdapter(http(), cas), "archive.snapshot", {"url": u, "limit": 3})
                 for u in urls]
    for adapter, cap, args in jobs:
        try:
            out += to_inputs(adapter.acquire(cap, args, prov()))
        except (AdapterError, KeyError, ValueError, IndexError):
            continue
    return out


def run_web_research(question: str, *, candidates: list[str] | None = None, gateway=None,
                     rounds: int = 3, limit: int = 5, web_adapter=None,
                     backends: list[str] | None = None, corroborate: bool = True) -> InvestigationResult:
    """Run an autonomous, multi-source, iterative investigation and return the full result.
    ``backends`` selects which open-web engines to comb (default DuckDuckGo + Wikipedia); when
    ``corroborate`` is set, any IP/domain/URL in the question also fires the free keyless infra/
    archive adapters (Shodan InternetDB · crt.sh · Wayback) as a corroboration stage."""
    from ..adapters.web.search import to_search_query
    adapter = web_adapter if web_adapter is not None else live_web_adapter()
    extra = corroborate_entities(question) if corroborate else []
    return autoresearch_investigation(
        question=question, candidates=candidates or None, web_adapter=adapter, limit=limit,
        gateway=gateway, rounds=rounds, backends=backends or ["duckduckgo", "wikipedia"],
        query_transform=to_search_query, extra_evidence=extra)
