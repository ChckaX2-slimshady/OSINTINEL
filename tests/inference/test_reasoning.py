"""Phase M reason tier — model-generated explanations + adversarial critique (doc 11)."""

from __future__ import annotations

from osintenal.agents.reasoning import ReasoningModel


class _Gateway:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def complete(self, *, tier, role, payload):
        self.calls.append((tier, role))
        return {"text": self._text, "structured": None}


# -- explanation generation --------------------------------------------------
def test_propose_explanations_parses_dedupes_and_caps():
    gw = _Gateway('["a water tank", "a met mast", "a communications mast"]')
    out = ReasoningModel(gw).propose_explanations(
        question="what is it?", observations=["lattice tower"],
        existing=["communications mast"], limit=2)
    assert out == ["a water tank", "a met mast"]            # dedup vs existing; capped at 2
    assert gw.calls == [("reason", "connections")]


def test_propose_explanations_extracts_json_from_prose():
    gw = _Gateway('Sure! Here you go: ["a reservoir"] hope that helps')
    assert ReasoningModel(gw).propose_explanations(
        question="q", observations=[], existing=[]) == ["a reservoir"]


def test_propose_explanations_empty_on_garbage_or_no_gateway():
    assert ReasoningModel(_Gateway("I cannot help")).propose_explanations(
        question="q", observations=[], existing=[]) == []


def test_propose_explanations_falls_back_when_gateway_raises():
    class Boom:
        def complete(self, **_):
            raise RuntimeError("down")
    assert ReasoningModel(Boom()).propose_explanations(
        question="q", observations=[], existing=[]) == []


# -- critique ----------------------------------------------------------------
def test_critique_validates_categories_and_caps_severity():
    gw = _Gateway(
        '[{"category":"hidden_assumption","severity":"high","description":"shape != function"},'
        ' {"category":"source_dependency","severity":"blocking","description":"single source"},'
        ' {"category":"overfit","severity":"blocking","description":"too tailored"}]')
    out = ReasoningModel(gw).critique(statement="it is a mast", evidence=["osm node"])
    cats = [o["category"] for o in out]
    assert "hidden_assumption" in cats and "overfit" in cats
    assert "source_dependency" not in cats          # computed gate is off-limits to the model
    # model severities are bounded to <= high (never 'blocking')
    assert all(o["severity"] in ("low", "medium", "high") for o in out)


# -- wiring: Connections + Skeptic gated on a gateway ------------------------
def test_reason_demo_widens_space_and_adds_critique():
    from osintenal.scenarios.reason_demo import run_reason_demo
    r = run_reason_demo()
    assert r.after_connections > r.given            # model proposed new competing explanations
    assert any(c == "hidden_assumption" for c, _s, _d in r.model_findings)
    assert r.model_calls >= 2                        # connections + skeptic calls recorded


def test_no_gateway_means_no_model_findings_or_extra_explanations(demo_result):
    # the normal demo runs model-free → only structural findings, candidates unchanged
    cats = {f.category for f in demo_result.state.findings.values()}
    assert not ({"hidden_assumption", "reasoning_weakness", "overfit"} & cats)


def test_connections_unchanged_without_gateway():
    # Connections with no llm uses only the given candidates (deterministic floor)
    from osintenal.agents.connections import ConnectionsAgent
    from osintenal.agents.base import AgentContext
    from osintenal.core.budget import BudgetGovernor
    from osintenal.adapters import AdapterRegistry
    from osintenal.core.schemas import Budgets, Investigation, InvestigationConfig
    from osintenal.core.state import InvestigationState
    from osintenal.ledger import Ledger

    inv = Investigation(title="t", objective="o", domain="d",
                        inputs=[{"kind": "question", "question": "q?",
                                 "candidates": ["a", "b"]}],
                        config=InvestigationConfig(budgets=Budgets()))
    state = InvestigationState("c", Ledger())
    ctx = AgentContext(inv, state, 0, BudgetGovernor(inv.config.budgets), AdapterRegistry())
    ConnectionsAgent().run(ctx)
    set_id = next(iter(state.hypothesis_sets))
    assert len(state.hypothesis_sets[set_id].explanations) == 2  # only the given candidates
