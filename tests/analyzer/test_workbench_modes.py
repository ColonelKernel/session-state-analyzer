"""The two-mode workbench (P6): Guided default, Expert preserved.

AppTest coverage for the mode switch: the app boots into Guided mode with the
overview cards auto-loaded, switching to Expert restores the four research
tabs exactly, the guided X04 story and guided atlas render, and the glossary
is present. Complements the expert-mode smokes in ``test_graph_layers.py``
and ``test_atlas.py`` (which switch to Expert explicitly).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

STREAMLIT_AVAILABLE = importlib.util.find_spec("streamlit") is not None

pytestmark = pytest.mark.skipif(
    not STREAMLIT_AVAILABLE, reason="streamlit not installed (ui extra)"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_PATH = REPO_ROOT / "src" / "session_explorer" / "workbench" / "app.py"
# Every discovered adapter bundle, incl. logic_real (the real captured
# session) — the workbench discovers fixtures/adapters/* dynamically.
DAWS = {"ableton", "cubase", "logic", "logic_real", "reaper"}

EXPERT_TABS = {
    "Graph",
    "Entity inspector",
    "X04 alignment",
    "Observability atlas",
    "State to audio",
    "Routing depth",
    "Parameter influence",
    "Session evolution",
    "Adapter comparison",
}

# The X06 grouping-depth fixture carries a deliberate feedback pair (a cycle),
# used to prove the cycle badge fires. It is NOT an adapter bundle, so the
# workbench does not discover it — the badge test renders the page directly.
X06_BUNDLE = (
    REPO_ROOT
    / "fixtures"
    / "cross-daw"
    / "X06_grouping_depth"
    / "bundles"
    / "synthetic"
)


def _apptest():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP_PATH), default_timeout=120)


def _markdown_text(at) -> str:
    return " ".join(str(m.value) for m in at.markdown)


def _caption_text(at) -> str:
    return " ".join(str(c.value) for c in at.caption)


def test_boots_guided_by_default_with_overview_cards():
    """Fresh boot: Guided mode, guided tabs, all four bundles auto-loaded,
    one overview card per DAW."""
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["app_mode"] == wcopy.COPY["mode_guided"]

    tab_labels = [tab.label for tab in at.tabs]
    assert tab_labels == [
        wcopy.COPY["tab_overview"],
        wcopy.COPY["tab_x04"],
        wcopy.COPY["tab_atlas"],
        wcopy.COPY["tab_graph"],
        wcopy.COPY["tab_grouping"],
        wcopy.COPY["tab_intervention"],
        wcopy.COPY["tab_evolution"],
        wcopy.COPY["tab_comparison"],
    ]

    # Auto-load on first visit: every discovered fixture bundle is selected.
    assert set(at.session_state["bundle_select"]) == DAWS

    # One card per DAW: every display name appears in the overview markdown.
    body = _markdown_text(at)
    for display_name in ("Ableton Live", "REAPER", "Cubase", "Logic Pro"):
        assert display_name in body

    # The prominent load button exists.
    button_labels = {b.label for b in at.button}
    assert wcopy.COPY["load_examples"] in button_labels


def test_mode_switch_to_expert_shows_the_four_research_tabs():
    at = _apptest()
    at.run()
    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]
    assert {tab.label for tab in at.tabs} == EXPERT_TABS
    # The expert graph rendered through one of the two backends.
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")


def test_guided_x04_story_renders_the_four_columns():
    """The four native-mechanism cards: each DAW's own noun on screen."""
    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    body = _markdown_text(at)
    for noun in ("Return Track", "FX Channel", "Aux Channel Strip"):
        assert noun in body
    assert "What Ableton Live calls it:" in body


def test_guided_atlas_renders_friendly_rows():
    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    body = _markdown_text(at)
    for label in ("Tracks & layout", "Signal routing", "Effects & processing"):
        assert label in body


def test_guided_graph_renders_with_relabeled_layers():
    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    # The guided layer radio exists with the plain labels, defaulting to
    # "Everything"; the graph rendered through one of the two backends.
    layer_radio = [r for r in at.radio if r.key == "guided_graph_layer"]
    assert len(layer_radio) == 1
    assert layer_radio[0].value == "Everything"
    assert list(layer_radio[0].options) == [
        "How things are organized",
        "How audio flows",
        "Effect chains",
        "Automation & control",
        "Session versions",
        "Everything",
    ]
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")

    layer_radio[0].set_value("How audio flows")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")

    # A newly added layer renders too (processing = the insert-chain lens).
    layer_radio[0].set_value("Effect chains")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")


def test_glossary_present_in_guided_mode():
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    expander_labels = {e.label for e in at.expander}
    assert wcopy.COPY["glossary_title"] in expander_labels
    # Glossary terms render (expander children run regardless of collapse).
    body = _markdown_text(at)
    for term in wcopy.GLOSSARY:
        assert term in body


# ---------------------------------------------------------------------------
# Phase 2 depth tabs: they render in BOTH modes without exception
# ---------------------------------------------------------------------------


def test_expert_shows_the_three_new_depth_tabs():
    """Routing depth / Parameter influence / Session evolution all render."""
    at = _apptest()
    at.run()
    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]
    labels = {tab.label for tab in at.tabs}
    assert {"Routing depth", "Parameter influence", "Session evolution"} <= labels
    # The whole tab set matches exactly (nothing dropped, nothing extra).
    assert labels == EXPERT_TABS


def test_guided_shows_the_new_grouping_and_evolution_tabs():
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    labels = [tab.label for tab in at.tabs]
    assert wcopy.COPY["tab_grouping"] in labels
    assert wcopy.COPY["tab_evolution"] in labels


def test_intervention_parameter_experiment_renders_in_both_modes():
    """The generalized intervention page dispatches the Delay-feedback A/B."""
    at = _apptest()
    at.run()
    # Guided: flip the guided experiment selector to the parameter case.
    guided_sel = [r for r in at.radio if r.key == "intervention_experiment_guided"]
    assert len(guided_sel) == 1
    guided_sel[0].set_value("Delay feedback").run()
    assert not at.exception, [e.value for e in at.exception]

    # Expert: flip the expert experiment selector to the parameter case.
    at.sidebar.radio[0].set_value("Expert").run()
    expert_sel = [r for r in at.radio if r.key == "intervention_experiment_expert"]
    assert len(expert_sel) == 1
    expert_sel[0].set_value("Delay feedback").run()
    assert not at.exception, [e.value for e in at.exception]


def test_session_evolution_tab_renders_in_both_states():
    """The Session-evolution tab renders without exception whether the variants
    module/fixtures are present (a live family selector) or absent (the honest
    ``st.info`` degradation note)."""
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]  # guided mode
    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]  # expert mode
    info_text = " ".join(str(i.value) for i in at.info)
    family_selectors = [s for s in at.selectbox if s.key == "evolution_family"]
    # Exactly one of the two honest outcomes must hold — a live exhibit or the
    # graceful note — but never an exception.
    assert (wcopy.EVOLUTION["unavailable"] in info_text) or family_selectors


# ---------------------------------------------------------------------------
# Phase 3 adapter-comparison dashboard: renders in BOTH modes, ladder chips,
# and the two profile downloads — a per-DAW profile grid, never a ranking.
# ---------------------------------------------------------------------------


def _download_labels(at) -> set[str]:
    """Labels of every st.download_button in the current render."""
    return {d.label for d in at.get("download_button")}


def test_expert_adapter_comparison_tab_present():
    """The 9th Expert tab exists and the whole Expert tab-set matches exactly."""
    at = _apptest()
    at.run()
    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]
    labels = {tab.label for tab in at.tabs}
    assert "Adapter comparison" in labels
    assert labels == EXPERT_TABS


def test_guided_comparison_tab_present():
    """The Guided 'How the DAWs compare' tab exists (default boot is Guided)."""
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    labels = [tab.label for tab in at.tabs]
    assert wcopy.COPY["tab_comparison"] in labels


def test_comparison_dashboard_renders_ladder_chips_and_downloads_expert():
    """Expert mode: per-DAW ladder chips render and both downloads are exposed."""
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]

    body = _markdown_text(at)
    # Per-DAW compatibility-ladder chips render (L0..L6 rung chips as HTML).
    for rung in ("L0", "L2", "L6"):
        assert rung in body
    # The load-bearing "profiles, not a ranking" disclaimer is prominent.
    info_text = " ".join(str(i.value) for i in at.info)
    assert wcopy.COMPARISON["caption_not_ranking"] in info_text

    # Both profile downloads are exposed.
    labels = _download_labels(at)
    assert wcopy.COMPARISON["download_metrics"] in labels
    assert wcopy.COMPARISON["download_ladder"] in labels


def test_comparison_dashboard_renders_ladder_chips_and_downloads_guided():
    """Guided mode: the same grid renders with plain words — chips + downloads."""
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()  # Guided is the default mode
    assert not at.exception, [e.value for e in at.exception]

    body = _markdown_text(at)
    for rung in ("L0", "L2", "L6"):
        assert rung in body
    info_text = " ".join(str(i.value) for i in at.info)
    assert wcopy.COMPARISON["caption_not_ranking"] in info_text

    labels = _download_labels(at)
    assert wcopy.COMPARISON["download_metrics"] in labels
    assert wcopy.COMPARISON["download_ladder"] in labels


# ---------------------------------------------------------------------------
# Cycle badge: fires as a finding on a cycle-bearing bundle
# ---------------------------------------------------------------------------


def test_cycle_badge_appears_on_a_feedback_bearing_bundle():
    """Rendering the X06 grouping-depth bundle surfaces the feedback finding."""
    from streamlit.testing.v1 import AppTest

    def _script(bundle_path: str):
        from session_explorer.loaders import load_bundle
        from session_explorer.workbench.pages import canonical_graph

        bundle = load_bundle(bundle_path)
        canonical_graph.render([bundle], "all")

    at = AppTest.from_function(
        _script, args=(str(X06_BUNDLE),), default_timeout=120
    )
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["graph_has_cycles"] is True
    warnings = " ".join(str(w.value) for w in at.warning)
    assert "Feedback loop detected" in warnings


def test_no_cycle_badge_on_adapter_bundles():
    """The discovered adapter bundles carry no routing feedback: no false finding."""
    at = _apptest()
    at.run()
    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["graph_has_cycles"] is False
