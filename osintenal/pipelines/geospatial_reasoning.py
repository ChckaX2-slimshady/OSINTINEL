"""Geospatial reasoning (doc 06 Phase 6) — narrow a location by intersecting constraints.

Phase 5 ranks *discrete* candidate places. Phase 6 deepens this into continuous inference: each
independent spatial observation — the sun's elevation/azimuth at a known time, ground elevation,
a bearing or distance to a mapped landmark, a biome band — defines a feasible region over the
earth's surface. **Intersecting several independent constraints narrows the feasible region to a
centroid plus an honest uncertainty radius**, with a confidence that reflects how strongly the
constraints agree and how many *independent* sources back them.

The solver is a deterministic, dependency-free hierarchical grid search: a coarse global pass
finds the basin, then an adaptive pass sized to contain ~95% of the posterior mass yields the
centroid, the 95%-mass radius, and a calibrated confidence. Every constraint carries its source
group so "≥3 independent constraints" is checked by distinct groups, not count.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from ..adapters.compute.solar import solar_position
from ..core.schemas import EpistemicClass, Location, Provenance

EARTH_KM = 6371.0


# --------------------------------------------------------------------------- geometry
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(a)))


def initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing (deg, clockwise from north) from point 1 to point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _angular_diff(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def _gaussian(error: float, tolerance: float) -> float:
    return math.exp(-0.5 * (error / tolerance) ** 2)


# --------------------------------------------------------------------------- constraints
@runtime_checkable
class GeoConstraint(Protocol):
    name: str
    independence_group: str
    detail: str

    def likelihood(self, lat: float, lon: float) -> float: ...


@dataclass
class SunElevationConstraint:
    observed_elevation_deg: float
    when_utc: datetime
    tolerance_deg: float = 2.0
    independence_group: str = "solar"
    name: str = "sun_elevation"

    @property
    def detail(self) -> str:
        return (f"sun elevation {self.observed_elevation_deg:.1f}° at "
                f"{self.when_utc.isoformat()} (±{self.tolerance_deg:.0f}°)")

    def likelihood(self, lat: float, lon: float) -> float:
        elev, _az = solar_position(lat, lon, self.when_utc)
        return _gaussian(elev - self.observed_elevation_deg, self.tolerance_deg)


@dataclass
class SunAzimuthConstraint:
    observed_azimuth_deg: float
    when_utc: datetime
    tolerance_deg: float = 4.0
    independence_group: str = "solar"
    name: str = "sun_azimuth"

    @property
    def detail(self) -> str:
        return (f"sun azimuth {self.observed_azimuth_deg:.0f}° at "
                f"{self.when_utc.isoformat()} (±{self.tolerance_deg:.0f}°)")

    def likelihood(self, lat: float, lon: float) -> float:
        elev, az = solar_position(lat, lon, self.when_utc)
        if elev <= 0:
            return 0.05  # sun below the horizon: azimuth is meaningless here
        return _gaussian(_angular_diff(az, self.observed_azimuth_deg), self.tolerance_deg)


@dataclass
class AltitudeConstraint:
    observed_alt_m: float
    dem: "SyntheticDEM"
    tolerance_m: float = 150.0
    independence_group: str = "terrain"
    name: str = "ground_elevation"

    @property
    def detail(self) -> str:
        return f"ground elevation ≈ {self.observed_alt_m:.0f} m (±{self.tolerance_m:.0f} m)"

    def likelihood(self, lat: float, lon: float) -> float:
        return _gaussian(self.dem.elevation(lat, lon) - self.observed_alt_m, self.tolerance_m)


@dataclass
class BearingConstraint:
    """A bearing from a known landmark to the observer constrains the observer to a ray."""

    landmark_lat: float
    landmark_lon: float
    observed_bearing_deg: float
    tolerance_deg: float = 3.0
    independence_group: str = "landmark"
    name: str = "landmark_bearing"

    @property
    def detail(self) -> str:
        return (f"bearing {self.observed_bearing_deg:.0f}° from landmark "
                f"({self.landmark_lat:.3f},{self.landmark_lon:.3f}) (±{self.tolerance_deg:.0f}°)")

    def likelihood(self, lat: float, lon: float) -> float:
        b = initial_bearing(self.landmark_lat, self.landmark_lon, lat, lon)
        return _gaussian(_angular_diff(b, self.observed_bearing_deg), self.tolerance_deg)


@dataclass
class DistanceConstraint:
    """A distance to a mapped feature constrains the observer to an annulus."""

    feature_lat: float
    feature_lon: float
    observed_distance_km: float
    tolerance_km: float = 5.0
    independence_group: str = "distance"
    name: str = "feature_distance"

    @property
    def detail(self) -> str:
        return (f"distance {self.observed_distance_km:.0f} km to feature "
                f"({self.feature_lat:.3f},{self.feature_lon:.3f}) (±{self.tolerance_km:.0f} km)")

    def likelihood(self, lat: float, lon: float) -> float:
        d = haversine_km(self.feature_lat, self.feature_lon, lat, lon)
        return _gaussian(d - self.observed_distance_km, self.tolerance_km)


@dataclass
class RegionConstraint:
    """A coarse biome / coastline band: soft box over a lat/lon range."""

    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    softness_deg: float = 2.0
    independence_group: str = "biome"
    name: str = "biome_region"
    label: str = "temperate band"

    @property
    def detail(self) -> str:
        return (f"{self.label}: lat [{self.min_lat:.0f},{self.max_lat:.0f}], "
                f"lon [{self.min_lon:.0f},{self.max_lon:.0f}]")

    def likelihood(self, lat: float, lon: float) -> float:
        dlat = max(0.0, self.min_lat - lat, lat - self.max_lat)
        dlon = max(0.0, self.min_lon - lon, lon - self.max_lon)
        return _gaussian(math.hypot(dlat, dlon), self.softness_deg)


class SyntheticDEM:
    """A fixed, deterministic stand-in for a real elevation model (SRTM/Copernicus).

    Sea level by default with a handful of fixed mountain features, so altitude reads carve a
    genuine contour over the map — independent of the solar and landmark constraints."""

    _FEATURES = [  # (lat, lon, peak_m, spread_deg)
        (51.0, -1.3, 180.0, 0.6),     # chalk downs (southern England)
        (46.0, 8.0, 3200.0, 1.2),     # alpine massif
        (39.5, -105.5, 3800.0, 1.5),  # rockies
        (-3.1, 37.35, 4500.0, 1.0),   # kilimanjaro-ish
    ]

    def elevation(self, lat: float, lon: float) -> float:
        h = 0.0
        for flat, flon, peak, spread in self._FEATURES:
            d2 = ((lat - flat) ** 2 + (lon - flon) ** 2) / (2 * spread ** 2)
            h += peak * math.exp(-d2)
        return h


# --------------------------------------------------------------------------- estimate
@dataclass
class ConstraintContribution:
    name: str
    independence_group: str
    detail: str
    map_likelihood: float


@dataclass
class LocationEstimate:
    lat: float
    lon: float
    radius_km: float
    confidence: float
    n_independent: int
    map_likelihood: float
    constraints: list[ConstraintContribution] = field(default_factory=list)

    @property
    def independence_groups(self) -> set[str]:
        return {c.independence_group for c in self.constraints}

    def to_location(self, *, label: str | None = None,
                    provenance: Provenance | None = None) -> Location:
        klass = EpistemicClass.INSIGHT if (self.confidence >= 0.7 and self.n_independent >= 3) \
            else EpistemicClass.HYPOTHESIS
        return Location(
            epistemic_class=klass, lat=round(self.lat, 6), lon=round(self.lon, 6),
            confidence_radius_km=round(self.radius_km, 3), confidence=round(self.confidence, 4),
            label=label, constraint_refs=[c.name for c in self.constraints],
            provenance=provenance)


# --------------------------------------------------------------------------- solver
class GeospatialReasoner:
    def __init__(self, *, coarse_step_deg: float = 2.0) -> None:
        self.coarse_step = coarse_step_deg

    def solve(self, constraints: list[GeoConstraint]) -> LocationEstimate:
        if not constraints:
            raise ValueError("at least one constraint is required")

        def posterior(lat: float, lon: float) -> float:
            p = 1.0
            for c in constraints:
                p *= c.likelihood(lat, lon)
            return p

        # 1) coarse global pass → MAP basin
        clat, clon = self._coarse_global(posterior)
        # 2) adaptive pass sized to hold ~95% of the mass → centroid, radius, confidence
        return self._adaptive_estimate(posterior, constraints, clat, clon)

    def _coarse_global(self, posterior) -> tuple[float, float]:
        best, best_p = (0.0, 0.0), -1.0
        lat = -80.0
        while lat <= 80.0:
            lon = -180.0
            while lon < 180.0:
                p = posterior(lat, lon)
                if p > best_p:
                    best_p, best = p, (lat, lon)
                lon += self.coarse_step
            lat += self.coarse_step
        return best

    def _grid(self, posterior, clat, clon, span, n=21):
        step = 2 * span / (n - 1)
        pts, weights = [], []
        for i in range(n):
            lat = clat - span + i * step
            for j in range(n):
                lon = clon - span + j * step
                pts.append((lat, lon))
                weights.append(posterior(lat, lon))
        return pts, weights, step

    def _adaptive_estimate(self, posterior, constraints, clat, clon) -> LocationEstimate:
        # 1) DESCENT: home in on the peak, re-centering on the MAP each step.
        span = self.coarse_step
        for _ in range(6):
            pts, weights, _step = self._grid(posterior, clat, clon, span, n=15)
            clat, clon = max(zip(pts, weights), key=lambda t: t[1])[0]
            span /= 2

        # 2) SIZING: grow the window until ~95% of the mass sits inside it, so the radius
        #    reflects the true posterior spread (the constraint tolerances), not grid resolution.
        span = max(span, 0.02)
        pts, weights, step = self._grid(posterior, clat, clon, span, n=25)
        for _ in range(12):
            total = sum(weights) or 1.0
            ring = sum(w for (la, lo), w in zip(pts, weights)
                       if abs(la - clat) > span * 0.85 or abs(lo - clon) > span * 0.85)
            if ring / total > 0.02 and span < 90:
                span *= 1.7
                pts, weights, step = self._grid(posterior, clat, clon, span, n=25)
            else:
                break

        total = sum(weights) or 1.0
        w = [x / total for x in weights]
        # weighted centroid (circular-safe in lon)
        clat2 = sum(p[0] * wi for p, wi in zip(pts, w))
        sx = sum(math.sin(math.radians(p[1])) * wi for p, wi in zip(pts, w))
        cx = sum(math.cos(math.radians(p[1])) * wi for p, wi in zip(pts, w))
        clon2 = math.degrees(math.atan2(sx, cx))

        # 95%-mass radius
        dists = sorted(((haversine_km(clat2, clon2, p[0], p[1]), wi)
                        for p, wi in zip(pts, w)), key=lambda t: t[0])
        acc, radius = 0.0, dists[-1][0]
        for d, wi in dists:
            acc += wi
            if acc >= 0.95:
                radius = d
                break
        # honest floor: never claim sub-grid precision (a point estimate has finite resolution)
        radius = max(radius, step * 111.0)

        # confidence: constraint agreement at the MAP point × independence factor
        map_pt = max(zip(pts, weights), key=lambda t: t[1])[0]
        contribs = [ConstraintContribution(c.name, c.independence_group, c.detail,
                                           round(c.likelihood(*map_pt), 4)) for c in constraints]
        agreement = 1.0
        for c in contribs:
            agreement *= max(c.map_likelihood, 1e-6)
        agreement **= (1 / len(contribs))
        n_independent = len({c.independence_group for c in contribs})
        independence_factor = 1 - 0.5 ** n_independent
        confidence = round(agreement * independence_factor, 4)

        return LocationEstimate(
            lat=round(clat2, 6), lon=round(clon2, 6), radius_km=round(radius, 3),
            confidence=confidence, n_independent=n_independent,
            map_likelihood=round(max(weights), 6), constraints=contribs)
