"""Investigation input layer — turn user input into a run (the shared service behind every UI).

The phase work built the *engine*; this is the **front door**: given a question, the competing
answers to weigh, and whatever evidence the user can provide, it frames the hypotheses, judges
each piece of evidence's relevance (the `task` tier when a model is present, else a lexical
heuristic or an explicit user tag), runs the reasoning quorum (Synthesis → Skeptic → Confidence
→ Epistemology), and returns a full ``InvestigationResult`` (so the dashboard, audit chain, and
ledger all work unchanged).

Scope note: this is *reasoning over a question + provided evidence* (and, with a model, model-
proposed explanations + adversarial critique). Autonomous open-web research — searching and
fetching evidence for an arbitrary question on its own — needs a general web-search/RAG adapter
and is future work; the structured adapters (geo/archive/…) already exist for their input types.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..adapters.registry import AdapterRegistry
from ..adapters.transport import AdapterError
from ..agents.base import AgentContext
from ..agents.confidence import ConfidenceAgent
from ..agents.connections import ConnectionsAgent
from ..agents.epistemology import EpistemologyAgent
from ..agents.relevance import (
    Candidate,
    HeuristicRelevanceJudge,
    LLMRelevanceJudge,
    apply_weights,
)
from ..agents.skeptic import SkepticAgent
from ..agents.synthesis import SynthesisAgent
from ..core.budget import BudgetGovernor
from ..core.runtime.controller import InvestigationResult
from ..core.runtime.loop import LoopResult
from ..core.runtime.termination import TerminationDecision
from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    Budgets,
    EvidenceObject,
    Investigation,
    InvestigationConfig,
    Provenance,
)
from ..core.state import InvestigationState
from ..ledger import Ledger
from ..reporting import build_insight_report


@dataclass
class EvidenceInput:
    """One piece of evidence the user provides."""

    text: str
    source: str = "user"
    group: str | None = None            # independence group (defaults to source)
    kind: str = "note"
    supports: int | None = None         # optional: index of the candidate this supports
    weight: float = 0.6                 # magnitude used when `supports` is given
    payload_ref: str | None = None      # CAS ref for heavy bytes (e.g. fetched web pages)
    content_hash: str | None = None
    url: str | None = None

    def independence_group(self) -> str:
        return self.group or self.source


def run_investigation(*, question: str, candidates: list[str],
                      evidence: list[EvidenceInput] | None = None, domain: str = "general",
                      gateway=None, calibrator=None, confidence_threshold: float = 0.7,
                      max_iterations: int = 3) -> InvestigationResult:
    """Run a user-posed investigation over provided evidence; returns a full InvestigationResult."""
    if len(candidates) < 2:
        candidates = list(candidates) + ["alternative / none of the above"]
    evidence = evidence or []

    ledger = Ledger()
    investigation = Investigation(
        title=question[:90], objective=question, domain=domain,
        inputs=[{"kind": "question", "question": question, "candidates": list(candidates)}],
        config=InvestigationConfig(confidence_threshold=confidence_threshold,
                                   max_iterations=max_iterations, budgets=Budgets()))
    state = InvestigationState(investigation.investigation_id, ledger)
    governor = BudgetGovernor(investigation.config.budgets)

    def ctx(iteration: int) -> AgentContext:
        return AgentContext(investigation, state, iteration, governor, AdapterRegistry(),
                            llm=gateway, calibrator=calibrator)

    # frame competing explanations (reason tier proposes more when a model is present)
    ConnectionsAgent().run(ctx(0))
    SynthesisAgent().synthesize_hypotheses(ctx(0))
    set_id = next(iter(state.hypothesis_sets))
    cand_list = [Candidate(h.hypothesis_id, h.statement)
                 for h in state.active_hypotheses(set_id)]

    judge = LLMRelevanceJudge(gateway) if gateway is not None else HeuristicRelevanceJudge()

    # ingest the user's evidence, judging or honoring its relevance to each hypothesis
    for item in evidence:
        prov = ctx(0).provenance(AgentName.ACQUISITION, method=AcquisitionMethod.HUMAN_PROVIDED,
                                 confidence=0.8, source=item.source)
        prov.url = item.url
        prov.content_hash = item.content_hash
        ev = EvidenceObject(kind=item.kind, summary=item.text, payload_ref=item.payload_ref,
                            structured={"independence_group": item.independence_group(),
                                        **({"url": item.url} if item.url else {})},
                            provenance=prov)
        if item.supports is not None and 0 <= item.supports < len(cand_list):
            target = cand_list[item.supports].hypothesis_id
            weights = {target: item.weight}
            for c in cand_list:
                if c.hypothesis_id != target:
                    weights[c.hypothesis_id] = -item.weight / 2
        else:
            weights = judge.score(kind=ev.kind, summary=ev.summary, structured=ev.structured,
                                  candidates=cand_list)
        apply_weights(ev, weights)
        state.add_evidence(ev, 0)

    # reasoning quorum
    snapshot = None
    for iteration in range(1, max_iterations + 1):
        c = ctx(iteration)
        SynthesisAgent().run(c)
        SkepticAgent().run(c)
        ConfidenceAgent().run(c)
        snapshot = EpistemologyAgent().run(c)

    report = build_insight_report(investigation, state, snapshot, "investigation_complete")
    ledger.verify()
    loop = LoopResult(report=report, iterations=max_iterations,
                      termination=TerminationDecision(True, "completed"), history=[])
    return InvestigationResult(investigation=investigation, report=report, ledger=ledger,
                               state=state, loop=loop, budget=governor.snapshot())


def _gather_web_evidence(web_adapter, query: str, limit: int,
                         backend: str | None) -> list[EvidenceInput]:
    """One search → fetch → evidence pass. Failures (missing cassette, blocked URL) raise
    AdapterError, which the caller treats as 'this query yielded nothing' and moves on."""
    aprov = Provenance(source="web", acquisition_method=AcquisitionMethod.SCRAPE,
                       agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                       investigation_id="web-research")
    args = {"query": query, "limit": limit}
    if backend is not None:
        args["backend"] = backend
    gathered = web_adapter.acquire("web.search", args, aprov)
    return [EvidenceInput(
        text=ev.summary, source=ev.provenance.source,
        group=ev.structured.get("independence_group"), kind="web_page",
        payload_ref=ev.payload_ref, content_hash=ev.provenance.content_hash,
        url=ev.structured.get("url")) for ev in gathered]


def autoresearch_investigation(*, question: str, candidates: list[str] | None = None,
                               web_adapter, limit: int = 5, backend: str | None = None,
                               gateway=None, calibrator=None, ledger=None,
                               confidence_threshold: float = 0.7, rounds: int = 1,
                               followups_per_round: int = 2, backends: list[str] | None = None,
                               query_transform=None) -> InvestigationResult:
    """Autonomous research: the web adapter gathers evidence, the loop reasons over it, and — when
    ``rounds > 1`` — the investigation *continues itself*, turning the Epistemology agent's
    **known-unknowns** into follow-up searches and re-reasoning over the growing evidence.

    ``backends`` searches several engines per query (e.g. DuckDuckGo for diverse domains *and*
    Wikipedia for reliable content) so hypotheses get independent corroboration; ``query_transform``
    pre-processes each query (e.g. keyword extraction). Both default to off, preserving the
    single-backend recorded demos. Search failures degrade to "no evidence" rather than crashing."""
    backends = backends if backends is not None else ([backend] if backend else [None])

    def gather(query: str) -> list[EvidenceInput]:
        q = query_transform(query) if query_transform else query
        out: list[EvidenceInput] = []
        for be in backends:
            try:
                out.extend(_gather_web_evidence(web_adapter, q, limit, be))
            except AdapterError:
                continue  # a backend that's down/blocked just contributes nothing
        return out

    evidence = gather(question)

    if not candidates:
        if gateway is not None:
            from ..agents.reasoning import ReasoningModel
            candidates = ReasoningModel(gateway).propose_explanations(
                question=question, observations=[e.text for e in evidence], existing=[], limit=4)
        candidates = candidates or ["the claim is supported", "the claim is not supported"]

    def reason() -> InvestigationResult:
        return run_investigation(question=question, candidates=candidates, evidence=evidence,
                                 domain="web-research", gateway=gateway, calibrator=calibrator,
                                 confidence_threshold=confidence_threshold)

    result = reason()
    asked: set[str] = {question}
    for _ in range(max(0, rounds - 1)):
        gaps = [ku.question for ku in (result.report.known_unknowns or [])
                if ku.question and ku.question not in asked][:followups_per_round]
        if not gaps:
            break  # nothing new to chase → the loop has converged
        before = len(evidence)
        for gap in gaps:
            asked.add(gap)
            evidence.extend(gather(gap))
        if len(evidence) == before:
            break  # no new evidence gathered → re-reasoning would be identical
        result = reason()
    return result


@dataclass
class InvestigationSummary:
    """A compact, serializable view of a result (for the MCP/text surfaces)."""

    question: str
    leader: str
    leader_confidence: float
    leader_class: str
    ranked: list[dict] = field(default_factory=list)
    known_unknowns: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)  # [{source, tool, count}] — what was used

    @classmethod
    def from_result(cls, result: InvestigationResult) -> "InvestigationSummary":
        cps = result.report.connective_probability_scores
        ranked = [{"statement": rh.statement, "confidence": round(rh.confidence, 3),
                   "class": rh.epistemic_class.value}
                  for s in cps for rh in s.ranked_hypotheses]
        leader = ranked[0] if ranked else {"statement": "—", "confidence": 0.0, "class": "—"}
        tallies: dict[tuple[str, str], int] = {}
        for ev in result.state.evidence.values():
            prov = ev.provenance
            tool = prov.tool_used or prov.acquisition_method.value
            tallies[(prov.source, tool)] = tallies.get((prov.source, tool), 0) + 1
        sources = [{"source": s, "tool": t, "count": n}
                   for (s, t), n in sorted(tallies.items(), key=lambda kv: -kv[1])]
        return cls(
            question=result.investigation.objective, leader=leader["statement"],
            leader_confidence=leader["confidence"], leader_class=leader["class"], ranked=ranked,
            known_unknowns=[ku.question for ku in (result.report.known_unknowns or [])],
            next_steps=list(result.report.recommended_next_investigations), sources=sources)
