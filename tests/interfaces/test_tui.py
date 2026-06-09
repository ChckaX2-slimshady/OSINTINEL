"""The terminal UI: pure mascot/logic helpers + a headless boot that runs an investigation."""

from __future__ import annotations

import asyncio
import os

from osintinel.interfaces.tui.logic import (
    InferenceForm,
    format_summary,
    form_from_profile,
    is_openai_profile,
    list_installed_models,
    parse_candidates,
    parse_evidence,
    parse_model_ids,
    profile_names,
    run_summary,
    status_from_form,
    status_lines,
)
from osintinel.interfaces.tui.mascot import WORDMARK, banner, splash_frames


# -- mascot ------------------------------------------------------------------
def test_splash_frames_animate_and_carry_the_wordmark():
    frames = splash_frames()
    assert len(frames) > 5
    assert frames[0] != frames[2]                       # it actually animates
    assert all("█" in line for line in WORDMARK)        # block wordmark present
    assert WORDMARK[0] in frames[0] and "scanning" not in banner()


# -- logic -------------------------------------------------------------------
def test_form_from_profile_prefills_tier_models():
    f = form_from_profile("ollama")
    assert f.profile == "ollama" and f.reason_model == "qwen2.5:14b-instruct"
    assert "deterministic" in profile_names() and "ollama" in profile_names()


def test_parse_candidates_and_evidence():
    assert parse_candidates("mast\n  turbine \n\n") == ["mast", "turbine"]
    ev = parse_evidence("OSM | man_made=mast | 1\nbare line")
    assert (ev[0].source, ev[0].text, ev[0].supports) == ("OSM", "man_made=mast", 0)
    assert ev[1].source == "user" and ev[1].supports is None


def test_parse_model_ids_handles_openai_and_ollama_shapes():
    openai = '{"object":"list","data":[{"id":"dollamin:latest"},{"id":"nomic-embed-text"}]}'
    ollama = '{"models":[{"name":"dollamin:latest"},{"model":"nomic-embed-text"}]}'
    assert parse_model_ids(openai) == ["dollamin:latest", "nomic-embed-text"]
    assert parse_model_ids(ollama) == ["dollamin:latest", "nomic-embed-text"]
    assert parse_model_ids("not json") == []


def test_list_installed_models_uses_models_endpoint_and_swallows_errors():
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return '{"data":[{"id":"dollamin:latest"}]}'

    assert list_installed_models("http://localhost:11434/v1", fetch=fake_fetch) == \
        ["dollamin:latest"]
    assert calls == ["http://localhost:11434/v1/models"]
    assert list_installed_models(None) == []                       # no endpoint → none

    def boom(url):
        raise OSError("connection refused")
    assert list_installed_models("http://localhost:11434/v1", fetch=boom) == []  # unreachable → none


def test_is_openai_profile():
    assert is_openai_profile("ollama") and not is_openai_profile("deterministic")


def test_status_reflects_overrides_and_restores_env():
    f = InferenceForm(profile="ollama", base_url="http://localhost:8080/v1", key_env="HERMES_TOKEN")
    st = status_from_form(f)
    assert st["base_url"] == "http://localhost:8080/v1" and st["key_env"] == "HERMES_TOKEN"
    assert "http://localhost:8080/v1" in status_lines(f)
    assert "OSINTINEL_OPENAI_BASE_URL" not in os.environ   # scoped override, no leak


def test_run_summary_deterministic_and_format():
    summary = run_summary("Mast or turbine?", ["communications mast", "wind turbine"],
                          parse_evidence("OSM | man_made=mast | 1"),
                          InferenceForm(profile="deterministic"))
    assert summary.leader and summary.ranked
    out = format_summary(summary)
    assert "Leading answer" in out and "Ranked hypotheses" in out


# -- headless app boot -------------------------------------------------------
def test_tui_boots_and_runs_an_investigation_headless():
    from textual.widgets import Input, TextArea

    from osintinel.interfaces.tui.app import ConsoleScreen, OsintinelTUI

    async def scenario() -> str:
        app = OsintinelTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")          # skip the splash → console
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ConsoleScreen)
            screen.query_one("#question", Input).value = "Mast or turbine?"
            screen.query_one("#candidates", TextArea).text = "communications mast\nwind turbine"
            screen.query_one("#evidence", TextArea).text = "OSM | man_made=mast | 1"
            screen.action_run()
            await app.workers.wait_for_complete()
            await pilot.pause()
            return screen.last_summary

    text = asyncio.run(scenario())
    assert "Run failed" not in text and ("Leading answer" in text or "mast" in text.lower())


def test_tui_detect_populates_tier_dropdowns(monkeypatch):
    from textual.widgets import Select

    from osintinel.interfaces.tui.app import OsintinelTUI

    monkeypatch.setattr("osintinel.interfaces.tui.app.list_installed_models",
                        lambda base, **_: ["dollamin:latest", "nomic-embed-text"])

    async def scenario() -> None:
        app = OsintinelTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            screen = app.screen
            screen.query_one("#profile", Select).value = "ollama"   # triggers auto-detect
            await app.workers.wait_for_complete()
            await pilot.pause()
            # a detected model is now a valid choice for the reason tier
            reason = screen.query_one("#reason_model", Select)
            reason.value = "dollamin:latest"                        # raises if not an option
            assert reason.value == "dollamin:latest"

    asyncio.run(scenario())
