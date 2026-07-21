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

import pandas as pd
import streamlit as st

from session_explorer.loaders import SnapshotBundle, get_presentation
from session_explorer.workbench import copy as wcopy
from session_explorer.workbench import state
from session_explorer.workbench.pages import (
    alignment,
    atlas,
    canonical_graph,
    comparison,
    depth,
    entity_inspector,
    guided,
    intervention,
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


def _bundle_label(bundle: SnapshotBundle) -> str:
    daw = bundle.snapshot.source.daw
    return f"{get_presentation(daw).display_name} ({bundle.dir.name})"


# ---------------------------------------------------------------------------
# Sidebar top: the mode switch (Guided is the default)
# ---------------------------------------------------------------------------

bundle_dirs = state.discover_bundle_dirs(FIXTURES_ROOT)
bundle_names = [path.name for path in bundle_dirs]

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
st.sidebar.button(
    f"Load all {len(bundle_names) or 'the'}",
    on_click=lambda: st.session_state.update(bundle_select=list(bundle_names)),
    disabled=not bundle_names,
)

layer = st.sidebar.radio(
    "Graph layer", LAYER_OPTIONS, index=LAYER_OPTIONS.index("all")
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


def _select_bundle(label_suffix: str) -> SnapshotBundle | None:
    if not bundles:
        st.info("Select at least one bundle in the sidebar.")
        return None
    return st.selectbox(
        f"Bundle ({label_suffix})",
        bundles,
        format_func=_bundle_label,
        key=f"bundle_for_{label_suffix}",
    )


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
    st.header("Native payload")
    bundle = _select_bundle("native")
    if bundle is not None:
        daw = bundle.snapshot.source.daw
        presentation = get_presentation(daw)
        vocab_col, payload_col = st.columns([1, 2])
        with vocab_col:
            st.subheader(f"{presentation.display_name} vocabulary")
            st.caption(
                "How this DAW names the canonical concepts — presentation "
                "only, never acquisition."
            )
            st.dataframe(
                pd.DataFrame(
                    sorted(presentation.native_vocab.items()),
                    columns=["canonical concept", f"{presentation.display_name} noun"],
                ),
                hide_index=True,
                width="stretch",
            )
        with payload_col:
            st.subheader("native.json")
            native = bundle.native  # lazy: loads the sidecar on first access
            if native is None:
                st.warning(
                    "This bundle ships no native.json sidecar; native "
                    "drill-down is unavailable."
                )
            else:
                st.caption(
                    "The verbatim DAW-native payload, exactly as the adapter "
                    "exported it."
                )
                st.json(native, expanded=1)

else:  # Evidence
    st.header("Evidence — the provenance store")
    bundle = _select_bundle("evidence")
    if bundle is not None:
        snapshot = bundle.snapshot
        store = pd.DataFrame(
            [
                {
                    "id": record.id,
                    "evidence": record.evidence,
                    "capture_method": record.capture_method,
                    "source_stability": record.source_stability,
                    "confidence": record.confidence,
                    "explanation": record.explanation or "",
                }
                for record in snapshot.provenance
            ]
        )
        st.caption(
            f"{len(store)} deduplicated provenance records; every entity "
            "field resolves into this table by id."
        )
        st.dataframe(store, hide_index=True, width="stretch")

        warn_col, fail_col = st.columns(2)
        with warn_col:
            st.subheader(f"Warnings ({len(snapshot.warnings)})")
            if snapshot.warnings:
                for warning in snapshot.warnings:
                    st.warning(warning)
            else:
                st.caption("The adapter recorded no warnings.")
        with fail_col:
            st.subheader(f"Failures ({len(snapshot.failures)})")
            if snapshot.failures:
                for failure in snapshot.failures:
                    st.error(f"[{failure.stage}] {failure.message}")
                    if failure.detail:
                        st.caption(failure.detail)
            else:
                st.caption(
                    "The adapter recorded no acquisition/mapping failures."
                )
