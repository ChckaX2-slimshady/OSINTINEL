"""A deterministic demonstration investigation (the "circled structure" case, doc 02 §2).

Three competing explanations for a circled structure on a ridgeline. The replayable world is
arranged so the leader ("communications structure") first rises *past the confidence
threshold on a single source* (OpenStreetMap) — at which point the Skeptic raises a BLOCKING
source-dependency finding that holds it at HYPOTHESIS despite the high confidence. Its backing
explanation is re-typed SPECULATION -> EXTRAPOLATION as confidence climbs, but the hypothesis
is promoted to INSIGHT (the backed conclusion) only once an independent source (Wikidata)
corroborates it and the gate clears. This exercises the full quorum, the explanation tier, the
hypothesis-preservation rule, and the Skeptic gate, with no network or model dependency.
"""

from __future__ import annotations

from ..adapters import AdapterRegistry, StubEvidenceAdapter
from ..core.schemas import Budgets, Investigation, InvestigationConfig

QUESTION = "What is the circled structure on the ridgeline?"


def build_demo_investigation() -> tuple[Investigation, AdapterRegistry]:
    inputs = [
        {"kind": "observation", "type": "image_note", "modality": "image",
         "source": "uploaded_image",
         "content": "A small white structure sits on an exposed ridgeline; thin vertical "
                    "element visible against the sky."},
        {"kind": "observation", "type": "exif", "modality": "image",
         "source": "uploaded_image",
         "content": {"GPSAltitude": "2100m", "Make": "unknown"}},
        {"kind": "question", "question": QUESTION,
         "candidates": ["summit marker", "communications structure", "image artifact"]},
    ]

    world = [
        {"id": "e1", "set_tag": QUESTION, "capabilities": ["stub.evidence"],
         "source": "OpenStreetMap", "independence_group": "osm", "kind": "map",
         "license_note": "ODbL",
         "summary": "OSM feature at the coordinates tagged man_made=mast / tower.",
         "weights": {"communications structure": 0.8, "summit marker": -0.1,
                     "image artifact": -0.2}},
        {"id": "e2", "set_tag": QUESTION, "capabilities": ["stub.evidence"],
         "source": "OpenStreetMap", "independence_group": "osm", "kind": "map",
         "license_note": "ODbL",
         "summary": "Adjacent OSM way tagged as an access track to a telecom installation.",
         "weights": {"communications structure": 0.6, "summit marker": -0.1}},
        {"id": "e3", "set_tag": QUESTION, "capabilities": ["stub.evidence"],
         "source": "Wikidata", "independence_group": "wikidata", "kind": "reference",
         "license_note": "CC0",
         "summary": "Wikidata entity: a radio relay station recorded near this ridgeline.",
         "weights": {"communications structure": 0.5, "summit marker": -0.2}},
        {"id": "e4", "set_tag": QUESTION, "capabilities": ["stub.evidence"],
         "source": "Wikimedia Commons", "independence_group": "wikimedia", "kind": "archive",
         "license_note": "CC BY-SA",
         "summary": "Archived photo of a lattice mast on the ridge, matching the silhouette.",
         "weights": {"communications structure": 0.5, "image artifact": -0.3}},
    ]

    investigation = Investigation(
        title="Circled structure on the ridgeline",
        objective="Identify the most likely nature of the circled structure.",
        domain="geolocation",
        inputs=inputs,
        config=InvestigationConfig(
            confidence_threshold=0.85,
            probability_separation_threshold=0.5,
            no_improvement_patience=3,
            max_iterations=25,
            budgets=Budgets(tokens=200_000, money_usd=10.0, seconds=600.0, requests=200),
        ),
    )

    registry = AdapterRegistry()
    registry.register(StubEvidenceAdapter(world), effectiveness=0.7)
    return investigation, registry
