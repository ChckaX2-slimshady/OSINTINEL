"""Shared fixtures for the OSINTENAL test suite (doc 09)."""

from __future__ import annotations

import pytest

from osintenal.core.runtime import InvestigationController
from osintenal.scenarios import build_demo_investigation


@pytest.fixture
def demo_result():
    investigation, registry = build_demo_investigation()
    controller = InvestigationController(registry)
    return controller.run(investigation)
