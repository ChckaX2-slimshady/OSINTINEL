"""Phase 5 exit criteria (doc 06): the image-investigation vertical slice.

- ranked location hypotheses with supporting AND contradicting evidence
- shadow/sun-angle + geo reasoning via compute.symbolic / geo adapters, with provenance
- the Skeptic actively challenges the leading location; no single-source conclusion is promoted
"""

from __future__ import annotations

import pytest

from osintenal.core.schemas import AcquisitionMethod, EpistemicClass
from osintenal.ledger import replay_state
from osintenal.scenarios.image_demo import run_image_demo


@pytest.fixture(scope="module")
def image_result():
    return run_image_demo()


def test_produces_ranked_location_hypotheses(image_result):
    ranked = image_result.ranked
    assert [f.name for f in ranked][:1] == ["Bullington ridge, Hampshire"]
    # ranked by confidence, descending
    confs = [f.confidence for f in ranked]
    assert confs == sorted(confs, reverse=True)
    assert len(ranked) == 3  # the three candidate locations (skeptic's alt is excluded)


def test_leader_has_supporting_and_contradicting_evidence(image_result):
    leader = image_result.leader
    assert leader.supporting, "leader must have supporting evidence"
    assert leader.contradicting, "leader must surface contradicting evidence, not hide it"
    # runners-up are actively contradicted
    assert all(f.contradicting for f in image_result.ranked[1:])


def test_shadow_and_geo_reasoning_carry_provenance(image_result):
    by_tool = {}
    for ev in image_result.state.evidence.values():
        by_tool.setdefault(ev.provenance.tool_used, []).append(ev)

    # shadow/sun-angle came from the compute.symbolic adapter, computed, provenanced
    solar = by_tool["compute.solar"]
    assert solar and all(e.provenance.acquisition_method is AcquisitionMethod.COMPUTATION
                         for e in solar)
    assert any("shadow" in e.summary for e in solar)
    # landmark corroboration came from a geo adapter via API
    overpass = by_tool["osm.overpass"]
    assert overpass and all(e.provenance.acquisition_method is AcquisitionMethod.API
                            for e in overpass)
    # every evidence object is provenance-stamped with a source
    assert all(e.provenance.source for e in image_result.state.evidence.values())


def test_skeptic_challenges_leader_and_blocks_single_source_promotion(image_result):
    # the Skeptic raised a blocking finding while the leader rested on one source...
    assert image_result.leader_challenged_single_source is True
    # ...and the leader was NOT promoted while single-source
    assert image_result.leader_class_when_single_source == EpistemicClass.HYPOTHESIS.value
    # a source-dependency finding exists and was ultimately resolved by corroboration
    findings = list(image_result.state.findings.values())
    dep = [f for f in findings if f.category == "source_dependency"]
    assert dep and all(f.resolved for f in dep)


def test_leader_promoted_only_with_independent_corroboration(image_result):
    leader = image_result.leader
    assert leader.epistemic_class == EpistemicClass.INSIGHT.value
    groups = image_result.state.independent_source_groups(leader.hypothesis_id)
    assert len(groups) >= 2  # multi-source, gate-cleared


def test_recommends_concrete_next_investigations(image_result):
    steps = image_result.next_steps()
    assert any("reverse-image" in s or "second independent image" in s for s in steps)
    assert any("rule out" in s.lower() for s in steps)


def test_image_run_is_replayable_and_keeps_bytes_out_of_the_ledger(image_result):
    assert replay_state(image_result.ledger).snapshot() == image_result.state.snapshot()
    # the image bytes live in the CAS, addressable by hash
    digest = image_result.image_ref.split(":", 1)[1]
    assert image_result.cas.has(digest)
    # no ledger event carries a raw image
    assert max(len(e.model_dump_json()) for e in image_result.ledger.events()) < 4000


def test_pipeline_is_deterministic():
    a, b = run_image_demo(), run_image_demo()
    assert [(f.name, round(f.confidence, 4), f.epistemic_class) for f in a.ranked] == \
           [(f.name, round(f.confidence, 4), f.epistemic_class) for f in b.ranked]
