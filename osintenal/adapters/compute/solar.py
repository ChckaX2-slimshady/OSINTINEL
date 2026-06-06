"""Solar geometry (doc 05 §4 ``compute.symbolic``) — deterministic shadow/sun-angle reasoning.

Given a coordinate and a capture time, ``solar_position`` returns the sun's elevation and
azimuth using the NOAA solar-position approximation (accurate to ~0.1°, pure math, no deps).
The adapter turns that into evidence: it predicts where the sun was when a photo was taken and
checks the prediction against an *observed* shadow direction in the image, yielding support for
geographically consistent location hypotheses and **contradiction** for inconsistent ones — the
shadow/sun-angle reasoning the Phase 5 exit criteria call for, fully provenanced.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter

SOURCE = "compute.symbolic (solar geometry)"


def _julian_day(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    day = (dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24)
    return (int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day + b - 1524.5)


def solar_position(lat: float, lon: float, when_utc: datetime) -> tuple[float, float]:
    """Return (elevation_deg, azimuth_deg) of the sun. Azimuth is clockwise from true north."""
    jd = _julian_day(when_utc)
    t = (jd - 2451545.0) / 36525.0

    l0 = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    mrad = math.radians(m)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    c = (math.sin(mrad) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * mrad) * (0.019993 - 0.000101 * t)
         + math.sin(3 * mrad) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app_long))))

    y = math.tan(math.radians(eps / 2)) ** 2
    l0r = math.radians(l0)
    eot = 4 * math.degrees(
        y * math.sin(2 * l0r) - 2 * e * math.sin(mrad)
        + 4 * e * y * math.sin(mrad) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mrad))

    u = when_utc.astimezone(timezone.utc)
    minutes = u.hour * 60 + u.minute + u.second / 60
    true_solar_time = (minutes + eot + 4 * lon) % 1440
    hour_angle = true_solar_time / 4 - 180

    latr, declr, har = math.radians(lat), math.radians(decl), math.radians(hour_angle)
    cos_zenith = (math.sin(latr) * math.sin(declr)
                  + math.cos(latr) * math.cos(declr) * math.cos(har))
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith = math.degrees(math.acos(cos_zenith))
    elevation = 90 - zenith

    # Azimuth (clockwise from north)
    denom = math.cos(latr) * math.sin(math.radians(zenith))
    if abs(denom) < 1e-9:
        azimuth = 0.0
    else:
        cos_az = (math.sin(declr) - math.sin(latr) * math.cos(math.radians(zenith))) / denom
        cos_az = max(-1.0, min(1.0, cos_az))
        azimuth = math.degrees(math.acos(cos_az))
        if hour_angle > 0:
            azimuth = 360 - azimuth
    return round(elevation, 3), round(azimuth, 3)


def _shadow_azimuth(sun_azimuth: float) -> float:
    """A shadow points away from the sun."""
    return (sun_azimuth + 180) % 360


def _angular_diff(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


class SolarGeometryAdapter(ReferenceAdapter):
    id = "compute.solar"
    capabilities = ["compute.symbolic"]
    license_note = "computed (NOAA solar-position approximation); no external source"

    # tolerance (degrees) within which an observed shadow corroborates a location
    CONSISTENCY_TOLERANCE = 20.0

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        return [RawHit(hit_id="solar", capability=capability, payload=arguments)]

    def collect(self, target: CollectTarget) -> RawArtifact:
        a = target.arguments["record"] if "record" in target.arguments else target.arguments
        when = a["when_utc"]
        if isinstance(when, str):
            when = datetime.fromisoformat(when)
        elevation, azimuth = solar_position(a["lat"], a["lon"], when)
        predicted_shadow = _shadow_azimuth(azimuth)
        observed = a.get("observed_shadow_azimuth")
        consistent = None
        diff = None
        if observed is not None and elevation > 0:
            diff = round(_angular_diff(predicted_shadow, observed), 2)
            consistent = diff <= self.CONSISTENCY_TOLERANCE
        return RawArtifact(
            capability="compute.symbolic", source=SOURCE, url=None,
            structured={
                "lat": a["lat"], "lon": a["lon"], "when_utc": when.isoformat(),
                "candidate": a.get("candidate"),
                "sun_elevation": elevation, "sun_azimuth": azimuth,
                "predicted_shadow_azimuth": predicted_shadow,
                "observed_shadow_azimuth": observed,
                "shadow_diff_deg": diff, "consistent": consistent,
            },
            license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        return [raw.structured]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, method=AcquisitionMethod.COMPUTATION)
        cand = parsed.get("candidate") or f"({parsed['lat']:.3f},{parsed['lon']:.3f})"
        if parsed["consistent"] is True:
            verdict = (f"sun azimuth {parsed['sun_azimuth']:.0f}° / elevation "
                       f"{parsed['sun_elevation']:.0f}° → predicted shadow "
                       f"{parsed['predicted_shadow_azimuth']:.0f}° matches the observed "
                       f"shadow (Δ{parsed['shadow_diff_deg']:.0f}°): consistent with {cand}.")
        elif parsed["consistent"] is False:
            verdict = (f"predicted shadow {parsed['predicted_shadow_azimuth']:.0f}° contradicts "
                       f"the observed shadow (Δ{parsed['shadow_diff_deg']:.0f}°): inconsistent "
                       f"with {cand}.")
        else:
            verdict = (f"sun elevation {parsed['sun_elevation']:.0f}°, azimuth "
                       f"{parsed['sun_azimuth']:.0f}° at {cand} (no shadow comparison).")
        return EvidenceObject(
            kind="solar_geometry",
            summary=verdict,
            structured={**parsed, "independence_group": "solar"},
            provenance=provenance,
        )

    def assess(self, *, lat: float, lon: float, when_utc, candidate: str | None = None,
               observed_shadow_azimuth: float | None = None,
               provenance: Provenance) -> EvidenceObject:
        """Convenience: compute one solar-geometry evidence object for a candidate location."""
        self.last_artifact = self.collect(CollectTarget(hit_id="solar", arguments={
            "lat": lat, "lon": lon, "when_utc": when_utc, "candidate": candidate,
            "observed_shadow_azimuth": observed_shadow_azimuth}))
        return self._emit(provenance)[0]
