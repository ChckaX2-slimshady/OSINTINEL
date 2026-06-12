"""Iterative autonomous research: known-unknowns drive follow-up searches (not one-shot)."""

from __future__ import annotations

from osintinel.core.schemas import AcquisitionMethod, AgentName, EvidenceObject, Provenance
from osintinel.service import autoresearch_investigation


class FakeWeb:
    """Records every query and returns one fresh, independent evidence item per search."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def acquire(self, capability, arguments, provenance):
        self.queries.append(arguments["query"])
        n = len(self.queries)
        prov = Provenance(source=f"src{n}", acquisition_method=AcquisitionMethod.SCRAPE,
                          agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                          investigation_id="t")
        prov.url = f"https://ex{n}.test/p"
        return [EvidenceObject(kind="web_page", summary=f"evidence about {arguments['query']}",
                               structured={"independence_group": f"ex{n}.test", "url": prov.url},
                               provenance=prov)]


def test_one_shot_makes_a_single_search():
    web = FakeWeb()
    autoresearch_investigation(question="Is the tower a mast?", candidates=["mast", "turbine"],
                               web_adapter=web, rounds=1)
    assert web.queries == ["Is the tower a mast?"]


def test_followups_are_driven_by_known_unknowns():
    # baseline: what does the deterministic pipeline flag as still-unknown?
    base = FakeWeb()
    result = autoresearch_investigation(question="Is the tower a mast?",
                                        candidates=["mast", "turbine"], web_adapter=base, rounds=1)
    gaps = [ku.question for ku in (result.report.known_unknowns or [])]

    web = FakeWeb()
    autoresearch_investigation(question="Is the tower a mast?", candidates=["mast", "turbine"],
                               web_adapter=web, rounds=2, followups_per_round=2)
    if gaps:
        assert len(web.queries) > 1                  # it went looking for what it didn't know
        assert set(web.queries[1:]) <= set(gaps)     # follow-ups were exactly the known-unknowns
    else:
        assert web.queries == ["Is the tower a mast?"]  # nothing unknown → converged in one pass


def test_entity_extraction_finds_ip_domain_url():
    from osintinel.service.research import _entities
    ips, domains, urls = _entities("scan 8.8.8.8 and example.com see https://archive.org/x please")
    assert "8.8.8.8" in ips
    assert "example.com" in domains
    assert any("archive.org" in u for u in urls)
    assert "999.1.1.1" not in _entities("bad 999.1.1.1")[0]  # invalid octet rejected


def test_corroborate_no_entities_is_a_noop():
    from osintinel.service.research import corroborate_entities
    assert corroborate_entities("no entities in this plain question") == []
