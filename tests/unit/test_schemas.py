"""Unit tests for canonical schemas (doc 09 §2): round-trip, validation, class derivation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from osintenal.core.schemas import (
    AcquisitionMethod,
    AgentName,
    EpistemicClass,
    Observation,
    Provenance,
    explanation_type_for_confidence,
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
    # The two explanation types, split by confidence (doc 00 §3): high => EXTRAPOLATION,
    # low => SPECULATION. This classifies *explanations*, never hypotheses.
    [(0.95, EpistemicClass.EXTRAPOLATION),
     (0.50, EpistemicClass.EXTRAPOLATION),
     (0.49, EpistemicClass.SPECULATION),
     (0.10, EpistemicClass.SPECULATION)],
)
def test_explanation_type_for_confidence(conf, expected):
    assert explanation_type_for_confidence(conf) is expected
