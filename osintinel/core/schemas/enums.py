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


# --- The epistemic ladder (doc 00 §3) ----------------------------------------------------
# Foundational Separation, corrected model:
#   INFORMATION -> CONNECTION -> EXPLANATION{SPECULATION | EXTRAPOLATION} -> HYPOTHESIS -> INSIGHT
# An *explanation* is a possible account built from verifiable connections. There are exactly
# two types, distinguished by confidence:
#     SPECULATION   = Low-Confidence Probability
#     EXTRAPOLATION = High-Confidence Probability
# BOTH types are synthesized *into* hypotheses; competing hypotheses lead to insight.
EXPLANATION_CLASSES = frozenset({EpistemicClass.SPECULATION, EpistemicClass.EXTRAPOLATION})
HYPOTHESIS_CLASSES = frozenset({EpistemicClass.HYPOTHESIS, EpistemicClass.INSIGHT})

# The single split point separating the two explanation types by confidence.
EXPLANATION_CONFIDENCE_SPLIT = 0.5


def explanation_type_for_confidence(confidence: float) -> EpistemicClass:
    """Classify an *explanation* by its confidence (the two-types rule, doc 00 §3).

    Low-confidence probability => SPECULATION; high-confidence probability => EXTRAPOLATION.
    This classifies explanations, NOT hypotheses: a hypothesis is synthesized *from*
    explanations and is classed HYPOTHESIS (or INSIGHT once it is the backed conclusion).
    """
    if confidence >= EXPLANATION_CONFIDENCE_SPLIT:
        return EpistemicClass.EXTRAPOLATION
    return EpistemicClass.SPECULATION
