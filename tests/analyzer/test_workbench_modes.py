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
DAWS = {"ableton", "cubase", "logic", "reaper"}

EXPERT_TABS = {"Graph", "Entity inspector", "X04 alignment", "Observability atlas"}


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
        "Everything",
    ]
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")

    layer_radio[0].set_value("How audio flows")
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
