"""Session State Analyzer workbench — single entry point, two modes.

Run from the repo root:

    streamlit run src/session_explorer/workbench/app.py

The sidebar's top control switches between two faces of the same data:

- **Guided** (default) — a plain-language, story-first tour across eight tabs:
  an Overview with one friendly card per session, the X04 "same idea in four
  DAWs" story, a plain-words observability atlas, the canonical graph, groups
  & feedback, what one change does to the sound, how a song evolved, and how
  the DAWs compare. All Guided copy lives in ``workbench/copy.py``.
- **Expert** — the research workbench: bundle multiselect, graph layer, and
  the Canonical / Native / Evidence views. Canonical holds nine tabs (Graph |
  Entity inspector | X04 alignment | Observability atlas | State to audio |
  Routing depth | Parameter influence | Session evolution | Adapter
  comparison).

The workbench is read-only by principle: it presents adapter exports, it
never parses a DAW artifact.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from session_explorer.loaders import SnapshotBundle
from session_explorer.workbench import copy as wcopy
from session_explorer.workbench import state
from session_explorer.workbench import ui
from session_explorer.workbench.pages import (
    alignment,
    atlas,
    canonical_graph,
    comparison,
    depth,
    entity_inspector,
    evidence,
    guided,
    intervention,
    native,
    parameter_influence,
    session_evolution,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_ROOT = REPO_ROOT / "fixtures" / "adapters"

LAYER_OPTIONS = (
    "organizational",
    "signal_flow",
    "processing",
    "automation",
    "variant",
    "all",
)
VIEW_OPTIONS = ("Canonical", "Native", "Evidence")

st.set_page_config(
    page_title="Session State Analyzer",
    page_icon="🎛️",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Sidebar top: the mode switch (Guided is the default)
# ---------------------------------------------------------------------------

bundle_dirs = state.discover_bundle_dirs(FIXTURES_ROOT)
bundle_names = [path.name for path in bundle_dirs]

# Widget keys whose widgets are not instantiated on every run (e.g. the Expert
# graph-layer radio while the Native view — or Guided mode — is showing) would
# otherwise have their state garbage-collected; keep() preserves them. Runs
# before any of these widgets exist in the current run. The navigation
# migration extends this list to every in-page widget key.
ui.keep("graph_layer_expert")

st.sidebar.title("Session State Analyzer")
mode = st.sidebar.radio(
    wcopy.COPY["mode_label"],
    (wcopy.COPY["mode_guided"], wcopy.COPY["mode_expert"]),
    key="app_mode",
    horizontal=True,
    help=wcopy.COPY["mode_help"],
)

# Shared bundle selection: Guided auto-loads every discovered bundle on first
# visit; Expert's multiselect binds to the same key, so the two modes always
# agree about what is loaded.
if "bundle_select" not in st.session_state:
    st.session_state["bundle_select"] = list(bundle_names)


def _load_bundles(names: list[str]) -> list[SnapshotBundle]:
    loaded: list[SnapshotBundle] = []
    for name in names:
        try:
            loaded.append(state.load_bundle_cached(FIXTURES_ROOT / name))
        except Exception as exc:  # noqa: BLE001 - a bad bundle must not kill the app
            st.sidebar.error(f"Failed to load bundle '{name}': {exc}")
    return loaded


# ---------------------------------------------------------------------------
# Guided mode
# ---------------------------------------------------------------------------

if mode == wcopy.COPY["mode_guided"]:
    st.sidebar.caption(wcopy.COPY["guided_tagline"])
    with st.sidebar.expander(wcopy.COPY["glossary_title"]):
        for term, definition in wcopy.GLOSSARY.items():
            st.markdown(f"**{term}** — {definition}")

    guided_bundles = _load_bundles(st.session_state.get("bundle_select", []))
    guided.render(guided_bundles, bundle_names)
    st.stop()


# ---------------------------------------------------------------------------
# Expert mode — the research workbench, unchanged below this line
# ---------------------------------------------------------------------------

st.sidebar.caption("Four observation instruments, one analysis contract.")
st.sidebar.caption(wcopy.COPY["expert_switch_hint"])

if not bundle_names:
    st.sidebar.error(f"No snapshot bundles found under {FIXTURES_ROOT}.")

selected_names = st.sidebar.multiselect(
    "Bundles", bundle_names, key="bundle_select"
)
_n_bundles = len(bundle_names)
st.sidebar.button(
    f"Load all {_n_bundles} bundles" if _n_bundles else "Load all bundles",
    on_click=lambda: st.session_state.update(bundle_select=list(bundle_names)),
    disabled=not bundle_names,
)

view = st.sidebar.radio("View", VIEW_OPTIONS, index=0)

bundles: list[SnapshotBundle] = _load_bundles(selected_names)

load_warnings = [
    f"[{bundle.dir.name}] {warning}"
    for bundle in bundles
    for warning in bundle.load_warnings
]
if load_warnings:
    with st.sidebar.expander(f"Load warnings ({len(load_warnings)})"):
        for warning in load_warnings:
            st.caption(warning)


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

if view == "Canonical":
    (
        graph_tab,
        inspector_tab,
        alignment_tab,
        atlas_tab,
        intervention_tab,
        depth_tab,
        param_tab,
        evolution_tab,
        comparison_tab,
    ) = st.tabs(
        [
            "Graph",
            "Entity inspector",
            "X04 alignment",
            "Observability atlas",
            "State to audio",
            "Routing depth",
            "Parameter influence",
            "Session evolution",
            "Adapter comparison",
        ]
    )
    with graph_tab:
        # The layer choice affects only this tab, so it lives here rather than
        # in the sidebar (where it read as a global control that ignored the
        # other eight tabs). The widget only exists under the Canonical view;
        # the ui.keep() call at the top of this script preserves its state
        # across Native/Evidence (and Guided) round trips.
        layer = st.radio(
            "Graph layer",
            LAYER_OPTIONS,
            index=LAYER_OPTIONS.index("all"),
            horizontal=True,
            key="graph_layer_expert",
        )
        canonical_graph.render(bundles, layer)
    with inspector_tab:
        entity_inspector.render(bundles)
    with alignment_tab:
        alignment.render()
    with atlas_tab:
        atlas.render(bundles)
    with intervention_tab:
        intervention.render_expert()
    with depth_tab:
        depth.render(bundles)
    with param_tab:
        parameter_influence.render(bundles)
    with evolution_tab:
        session_evolution.render(bundles)
    with comparison_tab:
        comparison.render(bundles)

elif view == "Native":
    native.render(bundles)

else:  # Evidence
    evidence.render(bundles)
