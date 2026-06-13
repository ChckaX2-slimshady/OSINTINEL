"""First-run diagnostics (`osintinel doctor`): clear, offline, graceful preflight."""

from __future__ import annotations

from osintinel.service import diagnostics_ok, run_diagnostics
from osintinel.service.diagnostics import FAIL, OK, WARN


def _by_name(checks):
    return {c.name: c for c in checks}


def test_deterministic_floor_is_all_green():
    checks = run_diagnostics(profile="deterministic")
    assert diagnostics_ok(checks)                       # nothing hard-fails
    names = _by_name(checks)
    assert names["Python"].status == OK
    assert names["pydantic"].status == OK
    assert "deterministic" in names["Inference profile"].detail
    assert names["Models"].status == OK                 # no model needed on the floor


def test_local_profile_warns_when_no_models_reachable():
    # A local profile (has an endpoint) with nothing installed → a clear, non-fatal warning.
    checks = run_diagnostics(profile="ollama", model_lister=lambda base: [])
    names = _by_name(checks)
    assert names["Model endpoint"].status == WARN
    assert "ollama serve" in names["Model endpoint"].detail
    assert diagnostics_ok(checks)                       # warnings don't fail the preflight


def test_local_profile_ok_when_models_present():
    checks = run_diagnostics(profile="ollama",
                             model_lister=lambda base: ["qwen2.5:3b-instruct", "nomic-embed-text"])
    names = _by_name(checks)
    assert names["Model endpoint"].status == OK
    assert "2 model(s)" in names["Model endpoint"].detail


def test_persistence_check_reports_ephemeral_when_opted_out(monkeypatch):
    monkeypatch.setenv("OSINTINEL_NO_PERSIST", "1")
    names = _by_name(run_diagnostics(profile="deterministic"))
    assert names["Run history"].status == OK and "ephemeral" in names["Run history"].detail


def test_diagnostics_ok_is_false_on_a_hard_fail():
    from osintinel.service.diagnostics import Check
    assert diagnostics_ok([Check("x", OK, "")]) is True
    assert diagnostics_ok([Check("x", WARN, ""), Check("y", FAIL, "")]) is False
