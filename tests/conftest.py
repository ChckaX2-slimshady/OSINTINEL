"""Shared fixtures for the OSINTENAL test suite (doc 09)."""

from __future__ import annotations

import pytest

from osintenal.core.runtime import InvestigationController
from osintenal.scenarios import build_demo_investigation
from osintenal.scenarios.archive_slice import run_archive_slice


@pytest.fixture
def demo_result():
    investigation, registry = build_demo_investigation()
    controller = InvestigationController(registry)
    return controller.run(investigation)


@pytest.fixture
def slice_result(tmp_path):
    """The Phase 3 adapter vertical slice, replayed from committed cassettes (offline)."""
    return run_archive_slice(cas_dir=tmp_path / "cas")
