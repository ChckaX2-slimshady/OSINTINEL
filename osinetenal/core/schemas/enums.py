"""Shared enums (doc 03 §0). Field names are normative."""

from __future__ import annotations

from enum import Enum


class EpistemicClass(str, Enum):
    """The epistemic ladder. Every output is classified as exactly one of these."""

    INFORMATION = "INFORMATION"
    CONNECTION = "CONNECTION"
    HYPOTHESIS = "HYPOTHESIS"
    SPECULATION = "SPECULATION"
    EXTRAPOLATION = "EXTRAPOLATION"
    INSIGHT = "INSIGHT"


class KnowledgeState(str, Enum):
    KNOWN = "KNOWN"
    KNOWN_UNKNOWN = "KNOWN_UNKNOWN"
    UNKNOWN_UNKNOWN_INDICATOR = "UNKNOWN_UNKNOWN_INDICATOR"


class AcquisitionMethod(str, Enum):
    API = "api"
    SCRAPE = "scrape"
    FILE_UPLOAD = "file_upload"
    ARCHIVE_FETCH = "archive_fetch"
    REVERSE_IMAGE = "reverse_image"
    COMPUTATION = "computation"
    HUMAN_PROVIDED = "human_provided"
    DERIVED = "derived"


class AgentName(str, Enum):
    AGGREGATION = "aggregation"
    CONNECTIONS = "connections"
    EVIDENCE_PLANNING = "evidence_planning"
    TOOL_SELECTION = "tool_selection"
    ACQUISITION = "acquisition"
    SYNTHESIS = "synthesis"
    SKEPTIC = "skeptic"
    CONFIDENCE = "confidence"
    EPISTEMOLOGY = "epistemology"
    SPECULATION = "speculation"
    RUNTIME = "runtime"


# Confidence bands → derived epistemic class for hypotheses (doc 02 §8).
SPECULATION_CEILING = 0.25
EXTRAPOLATION_FLOOR = 0.75


def class_for_confidence(confidence: float) -> EpistemicClass:
    """Derive a hypothesis' epistemic class from its calibrated confidence band."""
    if confidence >= EXTRAPOLATION_FLOOR:
        return EpistemicClass.EXTRAPOLATION
    if confidence <= SPECULATION_CEILING:
        return EpistemicClass.SPECULATION
    return EpistemicClass.HYPOTHESIS
