"""The terminal UI: pure mascot/logic helpers + a headless boot that runs an investigation."""

from __future__ import annotations

import asyncio
import os

from osintinel.inference import list_installed_models, parse_model_ids
from osintinel.interfaces.tui.logic import (
    InferenceForm,
    format_summary,
    form_from_profile,
    is_openai_profile,
    parse_candidates,
    parse_evidence,
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


class _FakeWeb:
    """A web adapter that returns one fresh independent evidence item per search (no network)."""

    def __init__(self):
        self.queries = []

    def acquire(self, capability, arguments, provenance):
        from osintinel.core.schemas import AcquisitionMethod, AgentName, EvidenceObject, Provenance
        self.queries.append(arguments["query"])
        n = len(self.queries)
        prov = Provenance(source=f"src{n}", acquisition_method=AcquisitionMethod.SCRAPE,
                          agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                          investigation_id="t")
        prov.url = f"https://ex{n}.test/p"
        return [EvidenceObject(kind="web_page", summary=f"evidence about {arguments['query']}",
                               structured={"independence_group": f"ex{n}.test", "url": prov.url},
                               provenance=prov)]


def test_run_autoresearch_gathers_its_own_evidence():
    from osintinel.interfaces.tui.logic import run_autoresearch
    web = _FakeWeb()
    summary = run_autoresearch("Is the tower a mast?", InferenceForm(profile="deterministic"),
                               candidates=["mast", "turbine"], web_adapter=web)
    assert web.queries and web.queries[0] == "tower mast"  # natural question → keyword search
    assert summary.ranked and summary.sources  # gathered evidence and listed its sources


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


def test_tui_autonomous_toggle_routes_to_web_research(monkeypatch):
    from textual.widgets import Checkbox, Input

    from osintinel.interfaces.tui.app import OsintinelTUI
    from osintinel.service import InvestigationSummary

    used = {}

    def fake_research(question, form, **kw):
        used["question"] = question
        return InvestigationSummary(question=question, leader="a mast", leader_confidence=0.6,
                                    leader_class="HYPOTHESIS",
                                    ranked=[{"statement": "a mast", "confidence": 0.6,
                                             "class": "HYPOTHESIS"}])

    monkeypatch.setattr("osintinel.interfaces.tui.app.run_autoresearch", fake_research)

    async def scenario() -> str:
        app = OsintinelTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            s = app.screen
            s.query_one("#question", Input).value = "What is on the ridge?"
            s.query_one("#autonomous", Checkbox).value = True   # no competing answers needed
            s.action_run()
            await app.workers.wait_for_complete()
            await pilot.pause()
            return s.last_summary

    text = asyncio.run(scenario())
    assert used.get("question") == "What is on the ridge?"   # the web-research path was taken
    assert "Leading answer" in text


def test_tui_new_button_clears_the_form():
    from textual.widgets import Checkbox, Input, TextArea

    from osintinel.interfaces.tui.app import OsintinelTUI

    async def scenario() -> tuple:
        app = OsintinelTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            s = app.screen
            s.query_one("#question", Input).value = "old question"
            s.query_one("#candidates", TextArea).text = "a\nb"
            s.query_one("#autonomous", Checkbox).value = True
            s._on_new()
            await pilot.pause()
            return (s.query_one("#question", Input).value,
                    s.query_one("#candidates", TextArea).text,
                    s.query_one("#autonomous", Checkbox).value)

    q, cands, auto = asyncio.run(scenario())
    assert q == "" and cands == "" and auto is False


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


def test_photo_report_reads_geotag_and_computes_sun(tmp_path):
    from osintinel.adapters.media.exif import write_exif_jpeg
    from osintinel.interfaces.tui.logic import photo_report

    jpg = tmp_path / "shot.jpg"
    jpg.write_bytes(write_exif_jpeg(make="Canon", model="EOS 80D",
                                    datetime_original="2021:06:21 14:30:00",
                                    lat=51.0153, lon=-1.3253, altitude_m=118.0))
    out = photo_report(str(jpg))
    assert "Geotag" in out and "51.0153" in out and "Sun at capture" in out
    assert "shadows point" in out


def test_photo_report_handles_non_image(tmp_path):
    from osintinel.interfaces.tui.logic import photo_report
    f = tmp_path / "notjpg.txt"
    f.write_text("hello")
    assert "No EXIF" in photo_report(str(f))
    assert "Can't read" in photo_report(str(tmp_path / "missing.jpg"))
