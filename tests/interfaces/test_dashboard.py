"""Phase 7 exit criteria (doc 06): explorable graph + timeline, replay, evolution viz.

The dashboard is a pure, offline projection of a run, so it is testable without a browser:
we assert the service builds the right data and the renderer emits a self-contained HTML
document (no external scripts/styles/fonts/network) that visualizes the graph, the timeline,
and hypothesis/confidence evolution.
"""

from __future__ import annotations

import pytest

from osintenal.interfaces.api import build_dashboard_data, dashboard_json, replay_iteration
from osintenal.interfaces.dashboard import render_dashboard, write_dashboard


@pytest.fixture
def data(demo_result):
    return build_dashboard_data(demo_result)


# -- service layer -----------------------------------------------------------
def test_service_builds_graph_timeline_and_evolution(data, demo_result):
    assert data.nodes and data.edges                              # explorable graph
    assert data.timeline and data.events                          # timeline
    assert len(data.events) == len(demo_result.ledger)
    # hypothesis & confidence evolution comes from confidence_history
    assert data.hypothesis_tracks
    assert any(len(t.points) >= 2 for t in data.hypothesis_tracks)
    assert any(t.is_leader for t in data.hypothesis_tracks)
    assert data.sources and data.agent_activity and data.ranked
    assert data.kpis["ledger_events"] == len(demo_result.ledger)


def test_confidence_tracks_are_monotone_in_iteration(data):
    for t in data.hypothesis_tracks:
        its = [p.iteration for p in t.points]
        assert its == sorted(its)  # evolution is ordered in time (append-only history)


def test_dashboard_data_is_json_serializable(data):
    # the REST contract a FastAPI endpoint would serve
    blob = data.model_dump_json()
    assert '"nodes"' in blob and '"hypothesis_tracks"' in blob


# -- investigation replay ----------------------------------------------------
def test_replay_reconstructs_past_iterations_from_ledger(demo_result):
    iters = sorted({e.iteration for e in demo_result.ledger.events()})
    early = replay_iteration(demo_result.ledger, iters[0])
    full = replay_iteration(demo_result.ledger, iters[-1])
    # the graph grows monotonically; a past iteration has no more nodes than the final one
    assert len(early.nodes()) <= len(full.nodes())
    # the fully-replayed graph matches the live graph
    from osintenal.graph import build_graph
    assert full.summary() == build_graph(demo_result.state).summary()


# -- renderer: self-contained, offline, deterministic ------------------------
def test_render_is_self_contained_offline_html(data):
    html = render_dashboard(data)
    assert html.startswith("<!doctype html>")
    assert "<svg" in html                       # inline graph + sparklines
    # NO external resources of any kind (air-gapped guarantee)
    assert "http://" not in html and "https://" not in html
    assert "src=" not in html                   # no <script src>/<img src>
    assert "<link" not in html and "@import" not in html
    assert "cdn" not in html.lower()


def test_render_contains_all_sections_and_ladder(data):
    html = render_dashboard(data)
    for tab in ("overview", "graph", "timeline", "confidence", "sources", "agents"):
        assert f'data-tab="{tab}"' in html
    # the epistemic ladder is visually encoded
    for tier in ("information", "connection", "hypothesis", "insight"):
        assert tier in html.lower()


def test_render_is_deterministic(data):
    assert render_dashboard(data) == render_dashboard(data)


def test_write_dashboard_emits_file(demo_result, tmp_path):
    path = write_dashboard(demo_result, tmp_path / "d.html")
    assert path.exists()
    text = path.read_text()
    assert "OSINTENAL" in text and "<svg" in text


def test_dashboard_json_helper(demo_result):
    assert dashboard_json(demo_result).startswith("{")
