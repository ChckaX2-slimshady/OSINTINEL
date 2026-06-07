"""Read-only dashboard service layer (doc 06 Phase 7, doc 10 §interfaces).

Turns a completed ``InvestigationResult`` (and its ledger) into a single JSON-serializable
``DashboardData`` payload — the contract a REST API would serve and the static dashboard
renders. It is a pure projection: it never mutates state, the ledger, or evidence (interfaces
depend on a thin read-only service over the controller, doc 10 rule 5).

Sections mirror the Phase 7 scope: knowledge-graph view, timeline, investigation replay,
hypothesis & confidence evolution (from ``confidence_history``), source explorer, and agent
activity. ``build_dashboard_data`` works for any run; ``replay_iteration`` reconstructs the
graph as of a past iteration from the ledger alone.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field

from ...core.schemas import EpistemicClass
from ...graph import build_graph
from ...ledger import Ledger, replay_state

# Tier ordering used for the layered graph layout (left → right along the epistemic ladder).
_TIER_COLUMN = {
    "Source": 0,
    "Observation": 1,
    "EvidenceObject": 1,
    "Explanation": 2,
    "HypothesisSet": 3,
    "Hypothesis": 4,
    "Speculation": 4,
}


class GraphNodeView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str
    label: str
    epistemic_class: str | None = None
    confidence: float | None = None
    x: float = 0.0
    y: float = 0.0


class GraphEdgeView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    type: str
    weight: float | None = None


class TimelineEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    iteration: int
    event_count: int
    types: dict[str, int] = Field(default_factory=dict)


class EventView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seq: int
    iteration: int
    type: str
    actor: str
    summary: str


class EvolutionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    iteration: int
    confidence: float
    epistemic_class: str


class HypothesisTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypothesis_id: str
    statement: str
    set_id: str
    final_confidence: float
    final_class: str
    is_leader: bool
    points: list[EvolutionPoint] = Field(default_factory=list)


class SourceView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    independence_group: str
    acquisition_method: str
    tool_used: str | None = None
    license_note: str | None = None
    evidence_count: int = 0


class AgentActivityView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str
    event_count: int
    event_types: dict[str, int] = Field(default_factory=dict)
    iterations: list[int] = Field(default_factory=list)


class DashboardData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    investigation_id: str
    domain: str | None = None
    generated_at: str
    termination_reason: str
    executive_summary: str
    # headline KPIs
    kpis: dict[str, str | int | float] = Field(default_factory=dict)
    nodes: list[GraphNodeView] = Field(default_factory=list)
    edges: list[GraphEdgeView] = Field(default_factory=list)
    legend: dict[str, str] = Field(default_factory=dict)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    events: list[EventView] = Field(default_factory=list)
    hypothesis_tracks: list[HypothesisTrack] = Field(default_factory=list)
    sources: list[SourceView] = Field(default_factory=list)
    agent_activity: list[AgentActivityView] = Field(default_factory=list)
    ranked: list[dict] = Field(default_factory=list)
    known_unknowns: list[str] = Field(default_factory=list)
    unknown_unknowns: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


# Epistemic-tier palette (the visual encoding of the ladder).
TIER_COLORS = {
    EpistemicClass.INFORMATION.value: "#4aa3df",
    EpistemicClass.CONNECTION.value: "#7e8aa2",
    EpistemicClass.SPECULATION.value: "#b06fd6",
    EpistemicClass.EXTRAPOLATION.value: "#e0a13c",
    EpistemicClass.HYPOTHESIS.value: "#e0c84a",
    EpistemicClass.INSIGHT.value: "#3ddc84",
}
NODE_TYPE_COLORS = {"Source": "#5a6477", "HypothesisSet": "#33405c"}


def _event_summary(ev) -> str:
    p = ev.payload
    t = ev.type
    if t == "node_add":
        return f"{p.get('node_type', 'node')} added"
    if t == "confidence_change":
        return f"confidence {p.get('from', 0):.2f} → {p.get('to', 0):.2f}: {p.get('reason', '')}"
    if t == "hypothesis_promote":
        return f"promoted {p.get('from')} → {p.get('to')}"
    if t == "explanation_reclassify":
        return f"explanation re-typed {p.get('from')} → {p.get('to')}"
    if t == "residual_mass_change":
        return f"residual mass {p.get('from')} → {p.get('to')}"
    if t == "raw_response":
        return f"fetched from {p.get('source')} ({p.get('adapter')})"
    if t in ("hypothesis_archive", "finding_resolved", "hypothesis_reactivate"):
        return t.replace("_", " ")
    if t == "investigation_start":
        return p.get("title", "investigation started")
    if t == "report_emit":
        return f"report emitted ({p.get('termination')})"
    return t


def _layout(nodes: list[GraphNodeView]) -> None:
    """Deterministic layered layout: column by epistemic tier, evenly spread within the column."""
    by_col: dict[int, list[GraphNodeView]] = defaultdict(list)
    for n in nodes:
        by_col[_TIER_COLUMN.get(n.type, 2)].append(n)
    n_cols = (max(by_col) + 1) if by_col else 1
    for col, col_nodes in by_col.items():
        col_nodes.sort(key=lambda n: n.id)
        count = len(col_nodes)
        for i, n in enumerate(col_nodes):
            n.x = round((col + 0.5) / n_cols, 4)
            n.y = round((i + 0.5) / count, 4) if count else 0.5


def build_dashboard_data(result) -> DashboardData:
    """Project an ``InvestigationResult`` into the dashboard payload."""
    state = result.state
    store = build_graph(state)
    report = result.report

    leaders = {
        max(state.active_hypotheses(sid), key=lambda h: h.confidence).hypothesis_id
        for sid in state.hypothesis_sets if state.active_hypotheses(sid)
    }

    # --- graph view ---------------------------------------------------------
    nodes: list[GraphNodeView] = []
    for n in store.nodes():
        nodes.append(GraphNodeView(
            id=n.node_id, type=n.node_type, label=(n.label or n.node_type)[:80],
            epistemic_class=n.epistemic_class.value if n.epistemic_class else None,
            confidence=n.attributes.get("confidence")))
    _layout(nodes)
    edges = [GraphEdgeView(source=e.from_id, target=e.to_id, type=e.edge_type, weight=e.weight)
             for e in store.edges()]

    # --- timeline + events --------------------------------------------------
    timeline_map: dict[int, TimelineEntry] = {}
    events: list[EventView] = []
    for seq, ev in enumerate(result.ledger.events()):
        entry = timeline_map.setdefault(ev.iteration, TimelineEntry(iteration=ev.iteration,
                                                                    event_count=0))
        entry.event_count += 1
        entry.types[ev.type] = entry.types.get(ev.type, 0) + 1
        events.append(EventView(seq=seq, iteration=ev.iteration, type=ev.type, actor=ev.actor,
                                summary=_event_summary(ev)))
    timeline = [timeline_map[k] for k in sorted(timeline_map)]

    # --- hypothesis / confidence evolution ----------------------------------
    tracks: list[HypothesisTrack] = []
    for h in state.hypotheses.values():
        pts = [EvolutionPoint(iteration=c.iteration, confidence=round(c.confidence, 4),
                              epistemic_class=h.epistemic_class.value)
               for c in h.confidence_history]
        tracks.append(HypothesisTrack(
            hypothesis_id=h.hypothesis_id, statement=h.statement[:120], set_id=h.set_id,
            final_confidence=round(h.confidence, 4), final_class=h.epistemic_class.value,
            is_leader=h.hypothesis_id in leaders, points=pts))
    tracks.sort(key=lambda t: (not t.is_leader, -t.final_confidence))

    # --- source explorer ----------------------------------------------------
    src_count: dict[str, int] = defaultdict(int)
    for ev in state.evidence.values():
        src_count[ev.provenance.source] += 1
    sources = [SourceView(
        source=s["source"], independence_group=s["independence_group"],
        acquisition_method=s["acquisition_method"], tool_used=s.get("tool_used"),
        license_note=s.get("license_note"), evidence_count=src_count.get(s["source"], 0))
        for s in report.source_appendix]

    # --- agent activity -----------------------------------------------------
    act: dict[str, AgentActivityView] = {}
    for ev in result.ledger.events():
        a = act.setdefault(ev.actor, AgentActivityView(actor=ev.actor, event_count=0))
        a.event_count += 1
        a.event_types[ev.type] = a.event_types.get(ev.type, 0) + 1
        if ev.iteration not in a.iterations:
            a.iterations.append(ev.iteration)
    agent_activity = sorted(act.values(), key=lambda x: -x.event_count)

    # --- ranked hypotheses (from the report) --------------------------------
    ranked: list[dict] = []
    for cps in report.connective_probability_scores:
        for rh in cps.ranked_hypotheses:
            ranked.append({
                "set": cps.question, "statement": rh.statement,
                "confidence": rh.confidence, "epistemic_class": rh.epistemic_class.value,
                "explanation_type": rh.explanation_type.value if rh.explanation_type else None})

    kpis = {
        "observations": len(state.observations),
        "evidence": len(state.evidence),
        "hypotheses": len(state.hypotheses),
        "sources": len(sources),
        "iterations": result.loop.iterations,
        "ledger_events": len(result.ledger),
        "leader_confidence": ranked[0]["confidence"] if ranked else 0.0,
    }

    return DashboardData(
        title=result.investigation.title,
        investigation_id=result.investigation.investigation_id,
        domain=result.investigation.domain,
        generated_at=report.generated_at.isoformat(),
        termination_reason=result.loop.termination.reason or "—",
        executive_summary=report.executive_summary,
        kpis=kpis, nodes=nodes, edges=edges,
        legend={**TIER_COLORS, **{f"type:{k}": v for k, v in NODE_TYPE_COLORS.items()}},
        timeline=timeline, events=events, hypothesis_tracks=tracks, sources=sources,
        agent_activity=agent_activity, ranked=ranked,
        known_unknowns=[ku.question for ku in (report.known_unknowns or [])],
        unknown_unknowns=[f"{uu.signal}: {uu.detail}"
                          for uu in (report.unknown_unknown_indicators or [])],
        next_steps=list(report.recommended_next_investigations),
    )


def replay_iteration(ledger: Ledger, iteration: int):
    """Reconstruct the graph as of a past iteration (Investigation Replay, doc 06 Phase 7)."""
    state = replay_state(ledger, until_iteration=iteration)
    return build_graph(state)


def dashboard_json(result) -> str:
    """The REST payload a FastAPI endpoint would return (framework-ready, dependency-free here)."""
    return build_dashboard_data(result).model_dump_json(indent=2)
