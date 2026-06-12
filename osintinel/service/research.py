"""Autonomous web research — the one entrypoint every front door (CLI, TUI, web, MCP) shares.

Builds a live, SSRF-guarded, polite open-web adapter and drives the iterative research loop:
search several engines per query (DuckDuckGo for diverse domains + Wikipedia for reliable content),
let the reason model frame competing answers, chase the Epistemology agent's known-unknowns for
more (and contrary) evidence, run the Skeptic/independence gauntlet, and surface the insights that
survived. ``web_adapter`` is injectable for tests.
"""

from __future__ import annotations

from .investigation import InvestigationResult, autoresearch_investigation


def live_web_adapter(backend: str = "wikipedia"):
    """A web-research adapter wired for live, SSRF-guarded, rate-limited open-web fetches."""
    import tempfile
    from pathlib import Path

    from ..adapters import Cassette, ContentAddressedStore, HttpClient, WebSearchAdapter
    cas = ContentAddressedStore(tempfile.mkdtemp())
    http = HttpClient(Cassette(Path(tempfile.mkdtemp()) / "web.json"), mode="live",
                      block_private_net=True, min_interval=1.0)
    return WebSearchAdapter(http, cas, backend=backend)


def run_web_research(question: str, *, candidates: list[str] | None = None, gateway=None,
                     rounds: int = 3, limit: int = 5, web_adapter=None,
                     backends: list[str] | None = None) -> InvestigationResult:
    """Run an autonomous, multi-source, iterative investigation and return the full result.
    ``backends`` selects which open-web engines to comb (default DuckDuckGo + Wikipedia)."""
    from ..adapters.web.search import to_search_query
    adapter = web_adapter if web_adapter is not None else live_web_adapter()
    return autoresearch_investigation(
        question=question, candidates=candidates or None, web_adapter=adapter, limit=limit,
        gateway=gateway, rounds=rounds, backends=backends or ["duckduckgo", "wikipedia"],
        query_transform=to_search_query)
