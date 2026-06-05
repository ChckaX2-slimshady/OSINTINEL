"""Shared fixtures for the OSINETENAL test suite (doc 09)."""

from __future__ import annotations

import pytest

from osinetenal.core.runtime import InvestigationController
from osinetenal.scenarios import build_demo_investigation


@pytest.fixture
def demo_result():
    investigation, registry = build_demo_investigation()
    controller = InvestigationController(registry)
    return controller.run(investigation)
