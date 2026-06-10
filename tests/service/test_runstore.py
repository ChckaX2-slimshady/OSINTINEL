"""Durable run history: persist a compact summary, list newest-first, honor the opt-out."""

from __future__ import annotations

from osintinel.service import InvestigationSummary, RunStore


def _summary(q: str) -> InvestigationSummary:
    return InvestigationSummary(question=q, leader="a mast", leader_confidence=0.8,
                                leader_class="INSIGHT", ranked=[{"statement": "a mast",
                                "confidence": 0.8, "class": "INSIGHT"}])


def test_save_and_list_roundtrip(tmp_path):
    store = RunStore(base=tmp_path)
    store.save(_summary("first?"), "run-1", model="ollama")
    store.save(_summary("second?"), "run-2", model="deterministic")
    runs = store.list()
    assert {r["id"] for r in runs} == {"run-1", "run-2"}
    assert store.load("run-1")["question"] == "first?"
    assert store.load("missing") is None


def test_opt_out_disables_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("OSINTINEL_NO_PERSIST", "1")
    store = RunStore(base=tmp_path)
    assert store.save(_summary("x?"), "run-x") is None
    assert store.list() == []


def test_save_is_best_effort_on_unwritable_base(tmp_path):
    # a file where the runs dir should be → mkdir fails, but save must not raise
    clash = tmp_path / "blocked"
    clash.write_text("not a dir")
    store = RunStore(base=clash)
    assert store.save(_summary("x?"), "run-x") is None


def test_summary_lists_tools_and_sources():
    from osintinel.service import run_investigation
    from osintinel.service.investigation import EvidenceInput, InvestigationSummary
    result = run_investigation(
        question="Mast or turbine?", candidates=["mast", "turbine"],
        evidence=[EvidenceInput(text="man_made=mast", source="OpenStreetMap", supports=0),
                  EvidenceInput(text="radio relay nearby", source="Wikidata", supports=0)])
    summary = InvestigationSummary.from_result(result)
    names = {s["source"] for s in summary.sources}
    assert {"OpenStreetMap", "Wikidata"} <= names
    assert all("tool" in s and "count" in s for s in summary.sources)
