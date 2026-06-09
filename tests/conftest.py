"""Shared fixtures for the OSINTINEL test suite (doc 09)."""

from __future__ import annotations

import pytest

from osintinel.core.runtime import InvestigationController
from osintinel.scenarios import build_demo_investigation
from osintinel.scenarios.archive_slice import run_archive_slice


@pytest.fixture(autouse=True)
def _isolate_run_history(tmp_path_factory, monkeypatch):
    """Point persisted run history at a throwaway dir so tests never touch the real ~/.osintinel."""
    monkeypatch.setenv("OSINTINEL_HOME", str(tmp_path_factory.mktemp("osintinel_home")))


@pytest.fixture
def demo_result():
    investigation, registry = build_demo_investigation()
    controller = InvestigationController(registry)
    return controller.run(investigation)


@pytest.fixture
def slice_result(tmp_path):
    """The Phase 3 adapter vertical slice, replayed from committed cassettes (offline)."""
    return run_archive_slice(cas_dir=tmp_path / "cas")
