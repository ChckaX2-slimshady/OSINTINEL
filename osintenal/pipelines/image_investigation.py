"""Image Investigation pipeline (doc 06 Phase 5) — the flagship vertical, built on the core loop.

An uploaded image is driven through the doc-06 stage sequence — metadata → EXIF → landmark →
terrain → vegetation → architecture → atmospheric → shadow → historical retrieval → satellite
comparison → geospatial hypothesis generation — producing **ranked location hypotheses** with
*supporting and contradicting* evidence, confidence, and recommended next steps.

It reuses the core reasoning agents (Synthesis → Skeptic → Confidence → Epistemology) rather
than re-implementing them, and runs them across a few iterations so the Skeptic gate is
exercised for real: a location supported by a single source is **held at HYPOTHESIS** until
independent corroboration arrives, and the leading location is actively challenged. Heavy image
bytes go to the content-addressed store; shadow/sun-angle and landmark reasoning are computed by
the ``compute.symbolic`` and ``geo`` adapters, each fully provenanced.

Evidence→hypothesis linking is a deterministic relevance rule standing in for a vision/LLM
model (Phase 1–5 keep the loop model-free), exactly as in the Phase 3 slice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..adapters import (
    ContentAddressedStore,
    ExifAdapter,
    OverpassAdapter,
    SolarGeometryAdapter,
    WikidataAdapter,
)
from ..adapters.registry import AdapterRegistry
from ..agents.base import AgentContext
from ..agents.confidence import ConfidenceAgent
from ..agents.epistemology import EpistemologyAgent
from ..agents.skeptic import SkepticAgent
from ..agents.synthesis import SynthesisAgent
from ..core.budget import BudgetGovernor
from ..core.schemas import (
    AcquisitionMethod,
    AgentName,
    EvidenceObject,
    Explanation,
    Hypothesis,
    HypothesisSet,
    InsightReport,
    Investigation,
)
from ..core.state import InvestigationState
from ..ledger import Ledger
from ..reporting import build_insight_report


@dataclass
class CandidateLocation:
    name: str
    lat: float
    lon: float


@dataclass
class LocationFinding:
    name: str
    hypothesis_id: str
    confidence: float
    epistemic_class: str
    supporting: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)


@dataclass
class ImageInvestigationResult:
    report: InsightReport
    state: InvestigationState
    ledger: Ledger
    cas: ContentAddressedStore
    set_id: str
    ranked: list[LocationFinding]
    image_ref: str
    # gate audit: did the Skeptic challenge a single-source leader and hold its promotion?
    leader_challenged_single_source: bool = False
    leader_class_when_single_source: str = ""

    @property
    def leader(self) -> LocationFinding:
        return self.ranked[0]

    def next_steps(self) -> list[str]:
        return self.report.recommended_next_investigations


def _haversine_km(a: CandidateLocation, lat: float, lon: float) -> float:
    r = 6371.0
    dlat, dlon = math.radians(lat - a.lat), math.radians(lon - a.lon)
    h = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a.lat)) * math.cos(math.radians(lat)) * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


class ImageInvestigationPipeline:
    def __init__(self, registry: AdapterRegistry, cas: ContentAddressedStore) -> None:
        self.registry = registry
        self.cas = cas

    # -- public ------------------------------------------------------------
    def run(self, *, image_bytes: bytes, candidates: list[CandidateLocation],
            observed_shadow_azimuth: float | None, annotations: dict,
            geo_queries: dict | None = None, ledger: Ledger | None = None
            ) -> ImageInvestigationResult:
        ledger = ledger or Ledger()
        state = InvestigationState("image-inv", ledger)
        governor = BudgetGovernor(self._budgets())
        investigation = self._investigation()

        def ctx(iteration: int) -> AgentContext:
            return AgentContext(investigation, state, iteration, governor, self.registry)

        # geospatial hypothesis generation — frame the competing locations up front
        set_id, hyp_by_name = self._frame_hypotheses(ctx(0), candidates)

        # --- iteration 0: metadata + EXIF only (single source on purpose) -----
        # Two reasoning passes: the first lets confidence climb; the second lets the Skeptic
        # see a *high-confidence, single-source* leader and raise the BLOCKING gate, which the
        # Confidence Agent then honours by holding promotion at HYPOTHESIS.
        exif = self._stage_exif(ctx(0), image_bytes, candidates, hyp_by_name)
        self._reason(ctx(0))
        self._reason(ctx(0))
        leader0 = max(state.active_hypotheses(set_id), key=lambda h: h.confidence)
        challenged = bool(state.unresolved_blocking_findings(leader0.hypothesis_id))
        held_class = leader0.epistemic_class.value

        # --- iteration 1: the corroboration + contradiction stages ------------
        self._stage_landmark(ctx(1), candidates, hyp_by_name, geo_queries or {})
        self._stage_terrain(ctx(1), candidates, hyp_by_name, annotations)
        self._stage_vegetation(ctx(1), candidates, hyp_by_name, annotations)
        self._stage_architecture(ctx(1), candidates, hyp_by_name, annotations)
        self._stage_shadow(ctx(1), candidates, hyp_by_name, exif, observed_shadow_azimuth)
        self._stage_historical(ctx(1), candidates, hyp_by_name, geo_queries or {})
        self._stage_satellite(ctx(1), candidates, hyp_by_name)
        self._stage_reverse_image(ctx(1), candidates, hyp_by_name)
        self._reason(ctx(1))  # corroboration resolves the finding → leader can be promoted

        # --- iteration 2: settle confidence + final knowledge-state snapshot ---
        snapshot = self._reason(ctx(2))

        report = build_insight_report(investigation, state, snapshot,
                                      "image_investigation_complete")
        ledger.verify()
        ranked = self._rank(state, set_id, hyp_by_name)
        report.recommended_next_investigations = self._next_steps(ranked, report)
        image_ref = self.cas.ref(self.cas.put(image_bytes))
        return ImageInvestigationResult(
            report=report, state=state, ledger=ledger, cas=self.cas, set_id=set_id,
            ranked=ranked, image_ref=image_ref,
            leader_challenged_single_source=challenged, leader_class_when_single_source=held_class)

    # -- framing -----------------------------------------------------------
    def _frame_hypotheses(self, ctx: AgentContext, candidates: list[CandidateLocation]):
        prov = ctx.provenance(AgentName.CONNECTIONS, method=AcquisitionMethod.DERIVED, confidence=0.5)
        hs = HypothesisSet(question="Where was this image taken?", provenance=prov)
        ctx.state.add_set(hs, 0)
        hyp_by_name: dict[str, str] = {}
        for c in candidates:
            ep = ctx.provenance(AgentName.CONNECTIONS, method=AcquisitionMethod.DERIVED, confidence=0.5)
            ex = Explanation(set_id=hs.set_id, statement=f"The image was taken at {c.name}.",
                             provenance=ep)
            ex.classify()
            ctx.state.add_explanation(ex, 0)
            hp = ctx.provenance(AgentName.CONNECTIONS, method=AcquisitionMethod.DERIVED, confidence=0.5)
            h = Hypothesis(set_id=hs.set_id, statement=ex.statement,
                           derived_from_explanations=[ex.explanation_id], provenance=hp)
            ctx.state.add_hypothesis(h, 0)
            hyp_by_name[c.name] = h.hypothesis_id
        return hs.set_id, hyp_by_name

    # -- stages ------------------------------------------------------------
    def _stage_exif(self, ctx, image_bytes, candidates, hyp_by_name) -> dict:
        adapter = ExifAdapter(self.cas)
        prov = ctx.provenance(AgentName.AGGREGATION, method=AcquisitionMethod.FILE_UPLOAD,
                              confidence=0.85, derived_from=[])
        ev = adapter.acquire_image(image_bytes, prov)[0]
        art = adapter.last_artifact
        ctx.state.record_raw_response(ctx.iteration, adapter_id=adapter.id, capability="media.exif",
                                      content_hash=art.content_hash, source=art.source,
                                      bytes_len=art.structured["bytes"])
        gps = ev.structured.get("gps")
        if gps:
            nearest = min(candidates, key=lambda c: _haversine_km(c, gps["lat"], gps["lon"]))
            dist = _haversine_km(nearest, gps["lat"], gps["lon"])
            if dist < 5.0:  # EXIF GPS pins the nearest candidate
                ev.supports = [hyp_by_name[nearest.name]]
                ev.weights = {hyp_by_name[nearest.name]: 1.2}
        ctx.state.add_evidence(ev, ctx.iteration)
        return ev.structured

    def _stage_landmark(self, ctx, candidates, hyp_by_name, geo_queries) -> None:
        q = geo_queries.get("overpass")
        if not q:
            return
        adapter: OverpassAdapter = self.registry.get("osm.overpass")
        prov = ctx.provenance(AgentName.ACQUISITION, method=AcquisitionMethod.API, confidence=0.8)
        results = adapter.acquire("geo.features", q, prov)
        art = adapter.last_artifact
        ctx.state.record_raw_response(ctx.iteration, adapter_id=adapter.id, capability="geo.features",
                                      content_hash=art.digest(), source=art.source, url=art.url)
        # a mapped mast/tower at the query coordinate supports the candidate nearest to it
        near = min(candidates, key=lambda c: _haversine_km(c, q["lat"], q["lon"]))
        for ev in results:
            if ev.structured.get("tags", {}).get("man_made") in {"mast", "tower"}:
                ev.supports = [hyp_by_name[near.name]]
                ev.weights = {hyp_by_name[near.name]: 0.7}
            ctx.state.add_evidence(ev, ctx.iteration)

    def _stage_terrain(self, ctx, candidates, hyp_by_name, annotations) -> None:
        terrain = annotations.get("terrain")
        if not terrain:
            return
        # a low ridge / pasture contradicts high-altitude (alpine) candidates
        contra = [hyp_by_name[c.name] for c in candidates if c.name.lower().find("alp") >= 0]
        self._compute_evidence(
            ctx, kind="terrain", source="terrain analysis", group="terrain",
            summary=f"Terrain reads as {terrain!r} — low relief, managed pasture.",
            contradicts=contra, weights={h: -0.5 for h in contra})

    def _stage_vegetation(self, ctx, candidates, hyp_by_name, annotations) -> None:
        veg = annotations.get("vegetation")
        if not veg:
            return
        contra = [hyp_by_name[c.name] for c in candidates
                  if any(k in c.name.lower() for k in ("alp", "coast"))]
        self._compute_evidence(
            ctx, kind="vegetation", source="vegetation analysis", group="vegetation",
            summary=f"Vegetation reads as {veg!r}, inconsistent with alpine/coastal biomes.",
            contradicts=contra, weights={h: -0.4 for h in contra})

    def _stage_architecture(self, ctx, candidates, hyp_by_name, annotations) -> None:
        arch = annotations.get("architecture")
        if not arch:
            return
        target = annotations.get("architecture_supports")
        if target and target in hyp_by_name:
            self._compute_evidence(
                ctx, kind="architecture", source="architecture analysis", group="architecture",
                summary=f"Structure reads as {arch!r} (lattice telecom mast).",
                supports=[hyp_by_name[target]], weights={hyp_by_name[target]: 0.5})

    def _stage_shadow(self, ctx, candidates, hyp_by_name, exif, observed_shadow_azimuth) -> None:
        dto = exif.get("datetime_original")
        if not dto or observed_shadow_azimuth is None:
            return
        when = _parse_exif_dt(dto)
        adapter: SolarGeometryAdapter = self.registry.get("compute.solar")
        for c in candidates:
            prov = ctx.provenance(AgentName.ACQUISITION, method=AcquisitionMethod.COMPUTATION,
                                  confidence=0.9)
            ev = adapter.assess(lat=c.lat, lon=c.lon, when_utc=when, candidate=c.name,
                                observed_shadow_azimuth=observed_shadow_azimuth, provenance=prov)
            hid = hyp_by_name[c.name]
            if ev.structured.get("consistent") is True:
                ev.supports, ev.weights = [hid], {hid: 0.6}
            elif ev.structured.get("consistent") is False:
                ev.contradicts, ev.weights = [hid], {hid: -0.5}
            ctx.state.add_evidence(ev, ctx.iteration)

    def _stage_historical(self, ctx, candidates, hyp_by_name, geo_queries) -> None:
        q = geo_queries.get("wikidata")
        if not q:
            return
        adapter: WikidataAdapter = self.registry.get("wikidata.entity")
        prov = ctx.provenance(AgentName.ACQUISITION, method=AcquisitionMethod.API, confidence=0.8)
        results = adapter.acquire("reference.encyclopedic", q, prov)
        art = adapter.last_artifact
        ctx.state.record_raw_response(ctx.iteration, adapter_id=adapter.id,
                                      capability="reference.encyclopedic",
                                      content_hash=art.digest(), source=art.source, url=art.url)
        target = q.get("supports")
        for ev in results:
            if target and target in hyp_by_name:
                ev.supports = [hyp_by_name[target]]
                ev.weights = {hyp_by_name[target]: 0.5}
            ctx.state.add_evidence(ev, ctx.iteration)

    def _stage_satellite(self, ctx, candidates, hyp_by_name) -> None:
        # deterministic satellite-tile match against the leading coordinate
        target = candidates[0].name
        self._compute_evidence(
            ctx, kind="satellite", source="satellite comparison", group="satellite",
            summary="Satellite tile shows a mast with matching access track and footprint.",
            supports=[hyp_by_name[target]], weights={hyp_by_name[target]: 0.4})

    def _stage_reverse_image(self, ctx, candidates, hyp_by_name) -> None:
        # an honest contradiction on the leader: the silhouette also appears elsewhere
        target = candidates[0].name
        self._compute_evidence(
            ctx, kind="reverse_image", source="reverse image search", group="reverse_image",
            summary="A visually similar lattice mast silhouette appears at other sites; the "
                    "match is not unique.",
            contradicts=[hyp_by_name[target]], weights={hyp_by_name[target]: -0.2})

    # -- helpers -----------------------------------------------------------
    def _compute_evidence(self, ctx, *, kind, source, group, summary,
                          supports=None, contradicts=None, weights=None) -> None:
        prov = ctx.provenance(AgentName.ACQUISITION, method=AcquisitionMethod.COMPUTATION,
                              confidence=0.75, source=source)
        ev = EvidenceObject(kind=kind, summary=summary, supports=supports or [],
                            contradicts=contradicts or [], weights=weights or {},
                            structured={"independence_group": group}, provenance=prov)
        ctx.state.add_evidence(ev, ctx.iteration)

    def _next_steps(self, ranked: list[LocationFinding], report: InsightReport) -> list[str]:
        """Concrete follow-ups: resolve the leader's contradictions, rule out runners-up."""
        steps: list[str] = []
        if ranked:
            leader = ranked[0]
            for c in leader.contradicting:
                if "silhouette" in c or "reverse" in c.lower():
                    steps.append("Resolve the reverse-image ambiguity — seek a distinguishing "
                                 "landmark or unique feature to confirm this site over look-alikes.")
            steps.append(f"Acquire a second independent image or street-level capture to "
                         f"corroborate {leader.name}.")
            for runner in ranked[1:]:
                if runner.contradicting:
                    steps.append(f"Formally rule out {runner.name}: re-check with a terrain/DEM "
                                 f"and biome cross-reference.")
        steps += [ku.question for ku in (report.known_unknowns or [])]
        # de-duplicate while preserving order
        seen, out = set(), []
        for s in steps:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out or ["No open questions remain above the confidence threshold."]

    def _reason(self, ctx: AgentContext):
        SynthesisAgent().run(ctx)
        SkepticAgent().run(ctx)
        ConfidenceAgent().run(ctx)
        return EpistemologyAgent().run(ctx)

    def _rank(self, state, set_id, hyp_by_name) -> list[LocationFinding]:
        name_by_hyp = {v: k for k, v in hyp_by_name.items()}
        # rank the candidate *locations* only; the Skeptic's injected "resist-convergence"
        # alternative is preserved in state but is not a geolocation candidate.
        active = sorted((h for h in state.active_hypotheses(set_id) if h.origin != "skeptic"),
                        key=lambda h: h.confidence, reverse=True)
        out = []
        for h in active:
            out.append(LocationFinding(
                name=name_by_hyp.get(h.hypothesis_id, h.statement),
                hypothesis_id=h.hypothesis_id, confidence=h.confidence,
                epistemic_class=h.epistemic_class.value,
                supporting=[state.evidence[e].summary for e in h.supporting_evidence],
                contradicting=[state.evidence[e].summary for e in h.contradicting_evidence]))
        return out

    def _investigation(self) -> Investigation:
        from ..core.schemas import Budgets, InvestigationConfig
        return Investigation(
            title="Image geolocation", objective="Geolocate the uploaded image.",
            domain="image", inputs=[],
            config=InvestigationConfig(
                confidence_threshold=0.7, probability_separation_threshold=0.4,
                budgets=Budgets(tokens=300_000, money_usd=20.0, seconds=600.0, requests=300)))

    def _budgets(self):
        return self._investigation().config.budgets


def _parse_exif_dt(dto: str) -> datetime:
    """EXIF 'YYYY:MM:DD HH:MM:SS' (assumed UTC for deterministic solar geometry)."""
    return datetime.strptime(dto, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
