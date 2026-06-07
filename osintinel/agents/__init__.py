"""The agent quorum (doc 02). Stateless specialists; no agent has full authority."""

from .acquisition import AcquisitionAgent
from .aggregation import AggregationAgent
from .base import AgentContext
from .confidence import ConfidenceAgent
from .connections import ConnectionsAgent
from .epistemology import EpistemologyAgent
from .planning import EvidencePlanningAgent
from .selection import ToolSelectionAgent
from .skeptic import SkepticAgent
from .speculation import SpeculationAgent
from .synthesis import SynthesisAgent

__all__ = [
    "AgentContext",
    "AggregationAgent",
    "ConnectionsAgent",
    "EvidencePlanningAgent",
    "ToolSelectionAgent",
    "AcquisitionAgent",
    "SynthesisAgent",
    "SkepticAgent",
    "ConfidenceAgent",
    "EpistemologyAgent",
    "SpeculationAgent",
]
