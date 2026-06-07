"""Solar geometry: sun-position correctness + shadow-consistency evidence (doc 06 Phase 5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from osintinel.adapters.compute.solar import SolarGeometryAdapter, solar_position
from osintinel.core.schemas import AcquisitionMethod, AgentName, Provenance


def _prov() -> Provenance:
    return Provenance(source="x", acquisition_method=AcquisitionMethod.COMPUTATION,
                      agent_responsible=AgentName.ACQUISITION, confidence=0.9, investigation_id="i")


def test_summer_solstice_noon_elevation_and_southerly_azimuth():
    # At 51°N on the solstice, solar-noon elevation ≈ 90 - 51 + 23.4 ≈ 62.4°, sun due south.
    elev, az = solar_position(51.0, 0.0, datetime(2021, 6, 21, 12, 0, tzinfo=timezone.utc))
    assert elev == pytest.approx(62.4, abs=1.0)
    assert az == pytest.approx(180, abs=3)


def test_morning_sun_is_east_afternoon_is_west():
    _, az_am = solar_position(51.0, 0.0, datetime(2021, 6, 21, 9, 0, tzinfo=timezone.utc))
    _, az_pm = solar_position(51.0, 0.0, datetime(2021, 6, 21, 15, 0, tzinfo=timezone.utc))
    assert 90 < az_am < 150     # south-east
    assert 210 < az_pm < 290    # south-west


def test_southern_hemisphere_sun_is_northward():
    _, az = solar_position(-33.87, 151.0, datetime(2021, 6, 21, 2, 0, tzinfo=timezone.utc))
    assert az < 20 or az > 340  # near due north


def test_adapter_supports_consistent_and_contradicts_inconsistent_shadow():
    adapter = SolarGeometryAdapter()
    when = datetime(2021, 6, 21, 14, 30, tzinfo=timezone.utc)
    _, az = solar_position(51.0153, -1.3253, when)
    observed = (az + 180) % 360  # the true shadow direction at this site/time

    consistent = adapter.assess(lat=51.0153, lon=-1.3253, when_utc=when, candidate="Bullington",
                                observed_shadow_azimuth=observed, provenance=_prov())
    assert consistent.structured["consistent"] is True
    assert consistent.supports == [] and consistent.contradicts == []  # linking is the pipeline's job
    assert consistent.provenance.tool_used == "compute.solar"
    assert consistent.provenance.acquisition_method is AcquisitionMethod.COMPUTATION

    # a far-away daytime candidate (southern hemisphere, sun in the north) is inconsistent
    far = adapter.assess(lat=-34.6, lon=-58.38, when_utc=when, candidate="Buenos Aires",
                         observed_shadow_azimuth=observed, provenance=_prov())
    assert far.structured["sun_elevation"] > 0  # daylight, so a real comparison is made
    assert far.structured["consistent"] is False
