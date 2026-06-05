"""Unit tests for canonical schemas (doc 09 §2): round-trip, validation, class derivation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from osinetenal.core.schemas import (
    AcquisitionMethod,
    AgentName,
    EpistemicClass,
    Observation,
    Provenance,
    class_for_confidence,
)


def _prov(conf: float = 1.0) -> Provenance:
    return Provenance(
        source="seed",
        acquisition_method=AcquisitionMethod.HUMAN_PROVIDED,
        agent_responsible=AgentName.AGGREGATION,
        confidence=conf,
        investigation_id="inv1",
    )


def test_observation_roundtrip():
    obs = Observation(source="s", type="note", content="x", provenance=_prov())
    again = Observation.model_validate_json(obs.model_dump_json())
    assert again.observation_id == obs.observation_id
    assert again.epistemic_class is EpistemicClass.INFORMATION


def test_confidence_bounds_enforced():
    with pytest.raises(ValidationError):
        _prov(conf=1.5)


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        Observation(source="s", type="n", content="x", provenance=_prov(), bogus=1)


@pytest.mark.parametrize(
    "conf,expected",
    [(0.95, EpistemicClass.EXTRAPOLATION),
     (0.50, EpistemicClass.HYPOTHESIS),
     (0.10, EpistemicClass.SPECULATION)],
)
def test_class_for_confidence(conf, expected):
    assert class_for_confidence(conf) is expected
