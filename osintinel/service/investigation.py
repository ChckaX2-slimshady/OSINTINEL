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


def autoresearch_investigation(*, question: str, candidates: list[str] | None = None,
                               web_adapter, limit: int = 5, backend: str | None = None,
                               gateway=None, calibrator=None, ledger=None,
                               confidence_threshold: float = 0.7) -> InvestigationResult:
    """Autonomous-ish research: the web adapter gathers evidence for the question, then the loop
    reasons over it. ``candidates`` may be omitted when a model is present (the reason tier
    proposes competing answers from the search results)."""
    aprov = Provenance(source="web", acquisition_method=AcquisitionMethod.SCRAPE,
                       agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                       investigation_id="web-research")
    args = {"query": question, "limit": limit}
    if backend is not None:
        args["backend"] = backend
    gathered = web_adapter.acquire("web.search", args, aprov)
    evidence = [EvidenceInput(
        text=ev.summary, source=ev.provenance.source,
        group=ev.structured.get("independence_group"), kind="web_page",
        payload_ref=ev.payload_ref, content_hash=ev.provenance.content_hash,
        url=ev.structured.get("url")) for ev in gathered]

    if not candidates:
        if gateway is not None:
            from ..agents.reasoning import ReasoningModel
            candidates = ReasoningModel(gateway).propose_explanations(
                question=question, observations=[e.text for e in evidence], existing=[], limit=4)
        candidates = candidates or ["the claim is supported", "the claim is not supported"]

    return run_investigation(question=question, candidates=candidates, evidence=evidence,
                             domain="web-research", gateway=gateway, calibrator=calibrator,
                             confidence_threshold=confidence_threshold)


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

    @classmethod
    def from_result(cls, result: InvestigationResult) -> "InvestigationSummary":
        cps = result.report.connective_probability_scores
        ranked = [{"statement": rh.statement, "confidence": round(rh.confidence, 3),
                   "class": rh.epistemic_class.value}
                  for s in cps for rh in s.ranked_hypotheses]
        leader = ranked[0] if ranked else {"statement": "—", "confidence": 0.0, "class": "—"}
        return cls(
            question=result.investigation.objective, leader=leader["statement"],
            leader_confidence=leader["confidence"], leader_class=leader["class"], ranked=ranked,
            known_unknowns=[ku.question for ku in (result.report.known_unknowns or [])],
            next_steps=list(result.report.recommended_next_investigations))
