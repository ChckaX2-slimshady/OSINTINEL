"""Phase 6 exit criterion (doc 06): multi-constraint location narrowing on golden cases.

Demonstrate that intersecting ≥3 *independent* geospatial constraints narrows the feasible
region to a centroid + uncertainty radius that contains the truth, with confidence that is
calibrated — high when constraints agree, low when they conflict.
"""

from __future__ import annotations

import pytest

from osintinel.core.schemas import EpistemicClass, Location
from osintinel.pipelines.geospatial_reasoning import (
    GeospatialReasoner,
    haversine_km,
    initial_bearing,
)
from osintinel.scenarios.geospatial_demo import (
    CONFLICT_CASE,
    GOLDEN_CASES,
    constraints_for,
    narrowing_curve,
    run_geospatial_demo,
    solve_case,
)


# -- geometry sanity ---------------------------------------------------------
def test_haversine_and_bearing_are_sane():
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.32, abs=0.5)
    assert initial_bearing(0, 0, 1, 0) == pytest.approx(0, abs=0.1)    # due north
    assert initial_bearing(0, 0, 0, 1) == pytest.approx(90, abs=0.1)   # due east


# -- each golden case: ≥3 independent constraints, truth within radius --------
@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c.name for c in GOLDEN_CASES])
def test_golden_case_narrows_to_truth(case):
    result = solve_case(case)
    est = result.estimate
    assert est.n_independent >= 3                      # ≥3 independent constraint groups
    assert len(est.independence_groups) == est.n_independent
    assert result.within_radius, f"{case.name}: truth {result.error_km}km > radius {est.radius_km}km"
    assert est.confidence >= 0.7                       # confident AND correct (calibrated)
    assert 0 < est.radius_km < 60                      # a tight, finite, non-zero radius


def test_constraints_carry_group_and_provenance_detail():
    cons = constraints_for(GOLDEN_CASES[0])
    groups = {c.independence_group for c in cons}
    assert {"solar", "terrain", "landmark"} <= groups   # independent physical sources
    for c in cons:
        assert c.name and c.detail   # each constraint explains itself (auditable)


# -- narrowing: the region shrinks as independent constraints intersect -------
def test_radius_shrinks_with_independent_constraints():
    curve = narrowing_curve(GOLDEN_CASES[1])  # [(n_groups, radius_km), ...]
    radii = [r for _, r in curve]
    assert radii == sorted(radii, reverse=True)          # monotonically non-increasing
    # three independent constraints cut the radius by >10x versus one
    one = next(r for g, r in curve if g == 1)
    three = next(r for g, r in curve if g == 3)
    assert three < one / 10


# -- calibration: confidence collapses when constraints disagree -------------
def test_conflicting_constraints_yield_low_confidence():
    conflict = solve_case(CONFLICT_CASE).estimate
    assert conflict.confidence < 0.3                     # not confident, by design
    consistent = solve_case(GOLDEN_CASES[1]).estimate
    assert consistent.confidence > conflict.confidence + 0.5


def test_calibration_coverage_over_the_suite():
    # every confident golden estimate actually contains the truth (coverage == confidence claim)
    results = run_geospatial_demo()
    confident = [r for r in results if r.estimate.confidence >= 0.7]
    assert confident, "expected confident estimates"
    assert all(r.within_radius for r in confident)       # 100% coverage of confident cases


# -- Location node with a confidence radius (doc 04 §2) ----------------------
def test_estimate_maps_to_location_with_radius_and_class():
    est = solve_case(GOLDEN_CASES[0]).estimate
    loc = est.to_location(label="downs")
    assert isinstance(loc, Location)
    assert loc.confidence_radius_km > 0
    assert loc.epistemic_class is EpistemicClass.INSIGHT   # confident, ≥3 independent constraints
    assert len(loc.constraint_refs) == len(est.constraints)

    conflict_loc = solve_case(CONFLICT_CASE).estimate.to_location()
    assert conflict_loc.epistemic_class is EpistemicClass.HYPOTHESIS  # not promoted on conflict


def test_single_constraint_does_not_narrow():
    cons = constraints_for(GOLDEN_CASES[1])[:1]  # solar elevation alone → a whole circle
    est = GeospatialReasoner().solve(cons)
    assert est.radius_km > 500                    # one constraint leaves a huge feasible region
    assert est.n_independent == 1


def test_determinism():
    a = solve_case(GOLDEN_CASES[2]).estimate
    b = solve_case(GOLDEN_CASES[2]).estimate
    assert (a.lat, a.lon, a.radius_km, a.confidence) == (b.lat, b.lon, b.radius_km, b.confidence)
