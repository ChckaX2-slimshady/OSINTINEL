"""Phase M milestone 2 — the `task` tier judges evidence→hypothesis relevance (doc 11)."""

from __future__ import annotations

from osintenal.agents.relevance import (
    Candidate,
    HeuristicRelevanceJudge,
    LLMRelevanceJudge,
    apply_weights,
)

MAST = Candidate("h-mast", "The structure is a communications mast operated by WindReach Telecom.")
TURB = Candidate("h-turbine", "The structure is a wind turbine.")
CANDS = [MAST, TURB]


# -- heuristic (default / CI behavior) ---------------------------------------
def test_heuristic_links_archive_snapshot_to_mast():
    w = HeuristicRelevanceJudge().score(
        kind="archive_snapshot", summary="WindReach Telecom mast hosting",
        structured={"title": "WindReach Telecom — Mast Hosting"}, candidates=CANDS)
    assert w == {"h-mast": 0.8, "h-turbine": -0.3}


def test_heuristic_links_osm_mast_feature():
    w = HeuristicRelevanceJudge().score(
        kind="osm_feature", summary="OSM node mast",
        structured={"tags": {"man_made": "mast"}}, candidates=CANDS)
    assert w == {"h-mast": 0.6, "h-turbine": -0.2}


def test_heuristic_returns_empty_for_unrelated_evidence():
    assert HeuristicRelevanceJudge().score(
        kind="osm_feature", summary="a pond", structured={"tags": {"natural": "water"}},
        candidates=CANDS) == {}


# -- LLM judge (task tier) via a stub gateway --------------------------------
class _StubGateway:
    """Minimal gateway double: returns a canned completion for the relevance role."""

    def __init__(self, response: dict):
        self._response = response
        self.calls: list[dict] = []

    def complete(self, *, tier, role, payload):
        self.calls.append({"tier": tier, "role": role})
        return self._response


def test_llm_judge_parses_structured_weights_and_clamps():
    gw = _StubGateway({"structured": {"h-mast": 0.9, "h-turbine": -2.0, "bogus": 1.0},
                       "text": ""})
    w = LLMRelevanceJudge(gw).score(kind="archive_snapshot", summary="telecom site",
                                    structured={}, candidates=CANDS)
    assert w == {"h-mast": 0.9, "h-turbine": -1.0}  # clamped to [-1,1]; unknown id dropped
    assert gw.calls == [{"tier": "task", "role": "relevance"}]


def test_llm_judge_parses_json_from_text_when_no_structured():
    gw = _StubGateway({"structured": None, "text": 'noise {"h-mast": 0.5} trailing'})
    w = LLMRelevanceJudge(gw).score(kind="archive_snapshot", summary="x", structured={},
                                    candidates=CANDS)
    assert w == {"h-mast": 0.5}


def test_llm_judge_falls_back_to_heuristic_on_garbage():
    gw = _StubGateway({"structured": None, "text": "I cannot help with that."})
    w = LLMRelevanceJudge(gw).score(
        kind="osm_feature", summary="mast", structured={"tags": {"man_made": "mast"}},
        candidates=CANDS)
    assert w == {"h-mast": 0.6, "h-turbine": -0.2}  # heuristic result


def test_llm_judge_falls_back_when_gateway_raises():
    class Boom:
        def complete(self, **_):
            raise RuntimeError("model unreachable")

    w = LLMRelevanceJudge(Boom()).score(
        kind="osm_feature", summary="tower", structured={"tags": {"man_made": "tower"}},
        candidates=CANDS)
    assert w == {"h-mast": 0.6, "h-turbine": -0.2}


def test_apply_weights_sets_supports_and_contradicts():
    class Ev:
        weights: dict = {}
        supports: list = []
        contradicts: list = []
    ev = Ev()
    apply_weights(ev, {"h-mast": 0.8, "h-turbine": -0.3})
    assert ev.supports == ["h-mast"] and ev.contradicts == ["h-turbine"]


# -- end-to-end: the slice accepts a model judge -----------------------------
def test_archive_slice_uses_injected_judge(tmp_path):
    from osintenal.core.schemas import EpistemicClass
    from osintenal.scenarios.archive_slice import run_archive_slice

    class MastJudge:  # a stand-in "model" that backs the mast hypothesis from any evidence
        def score(self, *, kind, summary, structured, candidates):
            return {c.hypothesis_id: (0.8 if "mast" in c.statement.lower() else -0.3)
                    for c in candidates}

    result = run_archive_slice(cas_dir=tmp_path / "cas", judge=MastJudge())
    mast = result.state.hypotheses[result.mast_hypothesis_id]
    assert mast.supporting_evidence                      # model-judged links were applied
    assert mast.confidence > result.state.hypotheses[result.turbine_hypothesis_id].confidence
    assert mast.epistemic_class is EpistemicClass.INSIGHT


def test_archive_slice_default_judge_is_unchanged(tmp_path):
    # no judge → heuristic path → same outcome as before (regression guard)
    from osintenal.scenarios.archive_slice import run_archive_slice
    result = run_archive_slice(cas_dir=tmp_path / "cas")
    assert result.selected_adapters == ["archive.wayback", "osm.overpass"]
    mast = result.state.hypotheses[result.mast_hypothesis_id]
    assert mast.supporting_evidence and mast.confidence > 0.5
