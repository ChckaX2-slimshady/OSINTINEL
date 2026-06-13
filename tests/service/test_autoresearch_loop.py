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


def test_corroborate_fires_dns_on_a_domain(monkeypatch):
    # The corroboration stage wires the free DNS adapter onto any domain it finds. We patch the
    # adapter symbol (imported inside the function) so the test stays offline.
    calls = []

    class _FakeDns:
        def __init__(self, client):
            pass

        def acquire(self, capability, arguments, provenance):
            calls.append((capability, arguments))
            prov = Provenance(source="Google Public DNS (DoH)",
                              acquisition_method=AcquisitionMethod.API,
                              agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                              investigation_id="web-research")
            prov.url = "https://dns.google/resolve?name=example.com"
            return [EvidenceObject(kind="dns_records", summary="DNS for example.com: A×1",
                                   structured={"independence_group": "dns"}, provenance=prov)]

    monkeypatch.setattr("osintinel.adapters.DnsAdapter", _FakeDns)
    from osintinel.service.research import corroborate_entities
    out = corroborate_entities("look into example.com please", want=("infra.dns",))
    assert calls == [("infra.dns", {"domain": "example.com"})]
    assert out and out[0].group == "dns" and out[0].kind == "dns_records"


def test_dns_and_asn_are_in_the_corroborator_set():
    from osintinel.service.research import CORROBORATORS
    assert {"infra.dns", "infra.asn"} <= set(CORROBORATORS)
