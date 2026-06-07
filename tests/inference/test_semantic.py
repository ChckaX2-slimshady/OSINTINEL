"""Phase M embed tier — semantic source-independence / near-duplicate detection (doc 11 §6)."""

from __future__ import annotations

from osintenal.agents.semantic import analyze_independence, cosine
from osintenal.inference import build_gateway


def _embed():
    return build_gateway().embed  # deterministic bag-of-words embedder


# -- geometry ----------------------------------------------------------------
def test_cosine_basics():
    assert cosine([1, 0], [1, 0]) == 1.0
    assert cosine([1, 0], [0, 1]) == 0.0
    assert cosine([], [1.0]) == 0.0


# -- independence collapse ---------------------------------------------------
def test_identical_text_across_groups_collapses():
    text = "Telecom mast confirmed on the ridge near Bullington."
    rep = analyze_independence(["osm", "newswire"], [text, text], _embed())
    assert rep.declared == {"osm", "newswire"}
    assert rep.effective == {"osm"} or rep.effective == {"newswire"}  # merged to one
    assert len(rep.effective) == 1 and rep.illusory is True
    assert rep.merged == [["newswire", "osm"]]


def test_distinct_text_stays_independent():
    rep = analyze_independence(
        ["osm", "wikidata"],
        ["Telecom mast on the ridge near Bullington.",
         "Wikidata radio relay station entity at this coordinate."],
        _embed())
    assert len(rep.effective) == 2 and rep.illusory is False and rep.merged == []


def test_three_sources_two_syndicated_collapse_to_two():
    dup = "Telecom mast confirmed on the ridge near Bullington."
    rep = analyze_independence(
        ["osm", "newswire", "wikidata"],
        [dup, dup, "Wikidata radio relay station entity recorded at this ridgeline."],
        _embed())
    assert len(rep.effective) == 2  # the two syndicated copies merge; wikidata stands alone


def test_single_group_is_noop():
    rep = analyze_independence(["osm"], ["anything"], _embed())
    assert rep.effective == {"osm"} and rep.illusory is False


# -- Skeptic integration (gated on an embedder) ------------------------------
def test_skeptic_raises_illusory_independence_with_embedder():
    from osintenal.scenarios.independence_demo import run_independence_demo
    r = run_independence_demo()
    assert r.declared_before == 2 and r.effective_before == 1   # syndicated pair collapses
    assert r.finding_raised is True                            # blocking finding holds promotion
    assert r.effective_after == 2 and r.finding_resolved is True  # distinct source clears it


def test_skeptic_skips_semantic_check_without_embedder(demo_result):
    # the normal demo runs with no gateway → no embed tier → no illusory-independence findings,
    # and the existing invariants/behaviour are untouched.
    cats = {f.category for f in demo_result.state.findings.values()}
    assert "illusory_independence" not in cats
