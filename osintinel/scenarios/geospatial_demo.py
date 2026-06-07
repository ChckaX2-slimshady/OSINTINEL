"""Phase 6 demo (doc 06): narrow a location by intersecting ≥3 independent constraints.

A suite of golden cases at distinct points on the globe. For each, the *observed* values are
derived from the known truth via the real physics/geometry (solar position, the synthetic DEM,
landmark bearings), then handed to the reasoner as independent constraints. The reasoner, blind
to the truth, intersects them to a centroid + uncertainty radius and a calibrated confidence —
and the truth lands inside the radius. A deliberately conflicting case shows the other side of
calibration: low confidence and a large radius when the constraints disagree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..adapters.compute.solar import solar_position
from ..pipelines.geospatial_reasoning import (
    AltitudeConstraint,
    BearingConstraint,
    DistanceConstraint,
    GeoConstraint,
    GeospatialReasoner,
    LocationEstimate,
    RegionConstraint,
    SunElevationConstraint,
    SyntheticDEM,
    haversine_km,
    initial_bearing,
)

_DEM = SyntheticDEM()


@dataclass
class GoldenCase:
    name: str
    lat: float
    lon: float
    when: datetime
    landmark_name: str
    landmark_lat: float
    landmark_lon: float
    region: tuple[float, float, float, float]  # min_lat, max_lat, min_lon, max_lon
    # an optional conflicting solar elevation (degrees) to force a low-confidence result
    conflict_elevation: float | None = None


GOLDEN_CASES = [
    GoldenCase("Hampshire downs", 51.02, -1.33, datetime(2021, 6, 21, 14, 30, tzinfo=timezone.utc),
               "Winchester", 51.06, -1.31, (45, 58, -8, 6)),
    GoldenCase("Valais alps", 46.55, 8.35, datetime(2021, 6, 21, 10, 0, tzinfo=timezone.utc),
               "Zermatt", 45.98, 7.66, (43, 50, 4, 12)),
    GoldenCase("Colorado Front Range", 39.70, -105.30,
               datetime(2021, 6, 21, 18, 0, tzinfo=timezone.utc),
               "Denver", 39.74, -104.99, (35, 44, -110, -100)),
    GoldenCase("Kilimanjaro flank", -3.07, 37.35,
               datetime(2021, 6, 21, 8, 0, tzinfo=timezone.utc),
               "Moshi", -3.35, 37.34, (-8, 2, 33, 42)),
]

CONFLICT_CASE = GoldenCase(
    "Conflicting reads", 46.55, 8.35, datetime(2021, 6, 21, 10, 0, tzinfo=timezone.utc),
    "Zermatt", 45.98, 7.66, (43, 50, 4, 12), conflict_elevation=15.0)


def constraints_for(case: GoldenCase, *, include_distance: bool = True) -> list[GeoConstraint]:
    """Derive independent constraints from the case's known truth (the 'observations')."""
    elev, _az = solar_position(case.lat, case.lon, case.when)
    if case.conflict_elevation is not None:
        elev = case.conflict_elevation  # an inconsistent solar read
    alt = _DEM.elevation(case.lat, case.lon)
    bearing = initial_bearing(case.landmark_lat, case.landmark_lon, case.lat, case.lon)
    cons: list[GeoConstraint] = [
        SunElevationConstraint(round(elev, 2), case.when),       # group: solar
        AltitudeConstraint(round(alt, 1), _DEM),                 # group: terrain
        BearingConstraint(case.landmark_lat, case.landmark_lon,  # group: landmark
                          round(bearing, 1)),
        RegionConstraint(*case.region),                          # group: biome
    ]
    if include_distance:
        dist = haversine_km(case.landmark_lat, case.landmark_lon, case.lat, case.lon)
        cons.append(DistanceConstraint(case.landmark_lat, case.landmark_lon,  # group: distance
                                       round(dist, 1)))
    return cons


@dataclass
class GeoCaseResult:
    case: GoldenCase
    estimate: LocationEstimate
    error_km: float
    within_radius: bool
    constraints: list[GeoConstraint] = field(default_factory=list)


def solve_case(case: GoldenCase, *, include_distance: bool = True) -> GeoCaseResult:
    cons = constraints_for(case, include_distance=include_distance)
    est = GeospatialReasoner().solve(cons)
    err = haversine_km(est.lat, est.lon, case.lat, case.lon)
    return GeoCaseResult(case=case, estimate=est, error_km=round(err, 2),
                         within_radius=err <= est.radius_km, constraints=cons)


def run_geospatial_demo() -> list[GeoCaseResult]:
    return [solve_case(c) for c in GOLDEN_CASES]


def narrowing_curve(case: GoldenCase) -> list[tuple[int, float]]:
    """(#independent groups, radius_km) as constraints are added — shows the region shrinking."""
    cons = constraints_for(case, include_distance=True)
    reasoner = GeospatialReasoner()
    curve = []
    for k in range(1, len(cons) + 1):
        est = reasoner.solve(cons[:k])
        curve.append((est.n_independent, est.radius_km))
    return curve
