"""Session State Explorer — the unified cross-DAW Streamlit app.

One product, one shell, every wired dialect. The source selector is driven by
the driver registry: Ableton (Extensions SDK / session JSON), Cubase
(session JSON + Track Archive inspector), and REAPER (``.rpp`` parsing) all
render through the same canonical graph, tables, recommendations, and native
view. The **Cross-DAW compare** mode aligns two dialects' sessions
semantically (see :mod:`session_explorer.core.compare`), showing what is
equivalent, what is native-only, and what is not even applicable.

Run:
    streamlit run src/session_explorer/app/main.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow `streamlit run src/session_explorer/app/main.py` without installing.
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd
import streamlit as st

import session_explorer.drivers  # noqa: F401 — registers all wired drivers
from session_explorer.core import driver as registry
from session_explorer.core.compare import compare_sessions
from session_explorer.core.graph import build_session_graph, compute_graph_metadata
from session_explorer.core.models import CanonicalSession, to_dict
from session_explorer.core.recommend import run_rules
from session_explorer.core.viz import GraphFilters, build_pyvis_html
from session_explorer.core.viz.graph_viz import PYVIS_AVAILABLE, build_plotly_figure

st.set_page_config(page_title="Session State Explorer", page_icon="🎚️", layout="wide")

EQUIVALENCE_BADGE = {
    "exact": "🟢 exact",
    "close": "🟢 close",
    "functional": "🟡 functional",
    "partial": "🟠 partial",
    "none": "⚪ native-only",
    "unknown": "⚪ unknown",
}
SEVERITY_ICON = {"info": "ℹ️", "suggestion": "💡", "warning": "⚠️"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _drivers() -> dict[str, "registry.SessionDriver"]:
    return {d.display_name: d for d in registry.all_drivers()}


def _render_graph(session: CanonicalSession, *, hide_params: bool, key: str) -> None:
    graph = build_session_graph(session)
    meta = compute_graph_metadata(graph, session)
    st.caption(
        f"{meta.get('num_nodes', graph.number_of_nodes())} nodes · "
        f"{meta.get('num_edges', graph.number_of_edges())} edges"
    )
    filters = GraphFilters(hidden_types={"parameter"} if hide_params else set())
    if PYVIS_AVAILABLE:
        try:
            html = build_pyvis_html(graph, height="620px", filters=filters)
            _embed_html(html, height=640)
            return
        except Exception as exc:  # pragma: no cover - render fallback
            st.warning(f"PyVis rendering failed ({exc}); using Plotly.")
    st.plotly_chart(build_plotly_figure(graph), width="stretch")


def _embed_html(html: str, *, height: int) -> None:
    # st.iframe (Streamlit ≥1.50) supersedes the deprecated
    # st.components.v1.html; both embed a script-executing iframe.
    if hasattr(st, "iframe"):
        st.iframe(html, height=height, width="stretch")
    else:  # pragma: no cover - older Streamlit
        st.components.v1.html(html, height=height, scrolling=False)


def _summary_metrics(session: CanonicalSession) -> None:
    cols = st.columns(7)
    cols[0].metric("Tempo", f"{session.tempo:g} BPM" if session.tempo else "—")
    cols[1].metric("Tracks", len(session.tracks))
    cols[2].metric("Clips", len(session.all_clips()))
    cols[3].metric("Scenes", len(session.scenes))
    cols[4].metric("Processors", len(session.all_processors()))
    cols[5].metric("Routes", len(session.routes))
    cols[6].metric("Warnings", len(session.warnings))


def _tracks_table(session: CanonicalSession) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "name": t.name,
                "kind": t.kind,
                "role": t.role or "—",
                "volume_db": t.volume_db,
                "pan": t.pan,
                "processors": ", ".join(p.name for p in t.processors) or "—",
                "provenance": t.provenance.observability,
            }
            for t in session.tracks
        ]
    )


# ---------------------------------------------------------------------------
# Header + sidebar
# ---------------------------------------------------------------------------

st.title("Session State Explorer")
st.caption(
    "Interpretable, cross-DAW session-state graphs — one canonical model, "
    "native semantics preserved, observability made explicit."
)

drivers = _drivers()

with st.sidebar:
    st.header("Mode")
    compare_mode = st.toggle(
        "Cross-DAW compare", value=False,
        help="Align two dialects' sessions semantically, side by side.",
    )
    st.divider()
    hide_params = st.checkbox("Hide parameters in graph", value=True)


# ---------------------------------------------------------------------------
# Single-session view
# ---------------------------------------------------------------------------

def _load_for(driver, key_prefix: str, default_upload=True) -> CanonicalSession | None:
    input_mode = st.radio(
        "Input",
        ["Built-in demo", "Upload session"],
        horizontal=True,
        key=f"{key_prefix}-mode",
    )
    if input_mode == "Built-in demo":
        try:
            return driver.demo()
        except NotImplementedError:
            st.info(f"{driver.display_name} has no built-in demo session yet.")
            return None
    uploaded = st.file_uploader(
        f"Upload a {driver.display_name} session",
        type=[e.lstrip(".") for e in driver.extensions],
        key=f"{key_prefix}-upload",
    )
    if uploaded is None:
        return None
    from session_explorer.core.driver import DriverInputs, UploadedFile

    inputs = DriverInputs(files=[UploadedFile(name=uploaded.name, data=uploaded.getvalue())])
    try:
        return driver.load(inputs)
    except Exception as exc:
        st.error(f"Could not load: {exc}")
        return None


def render_single() -> None:
    st.header("1 · Source")
    source = st.selectbox("DAW dialect", list(drivers), key="single-source")
    driver = drivers[source]
    session = _load_for(driver, "single")
    if session is None:
        st.stop()

    st.header("2 · Session summary")
    st.markdown(f"**{session.name}** · dialect `{session.dialect}`")
    _summary_metrics(session)
    if session.warnings:
        with st.expander(f"Session warnings ({len(session.warnings)})"):
            for w in session.warnings:
                st.caption(f"⚠️ {w}")

    st.header("3 · Canonical DAW-state graph")
    _render_graph(session, hide_params=hide_params, key="single")

    st.header("4 · Tables")
    view = st.radio("View", ["Canonical", "Native"], horizontal=True, key="single-view")
    if view == "Canonical":
        st.dataframe(_tracks_table(session), width="stretch")
    else:
        native = session.native
        if native is None:
            st.info("This session carries no native payload.")
        else:
            st.caption(
                f"Native model: `{native.model_name}` (dialect `{native.dialect}`) — "
                "the verbatim source model, reconstructable losslessly."
            )
            st.json(native.model, expanded=False)

    st.header("5 · Recommendations")
    recs = run_rules(session, driver.rules())
    if not recs:
        st.info("No heuristic rules triggered on this session.")
    for rec in recs:
        icon = SEVERITY_ICON.get(rec.severity, "💡")
        with st.expander(f"{icon} {rec.title}", expanded=False):
            st.markdown(f"**Severity:** {rec.severity} · **Confidence:** {rec.confidence:.0%}")
            st.write(rec.explanation)
            if rec.suggested_action:
                st.markdown(f"**Suggested action:** {rec.suggested_action}")
            st.caption(f"Caveat: {rec.caveat}")

    st.header("6 · Observability")
    matrix = driver.observation_matrix()
    if matrix:
        rows = []
        for artifact, obs in matrix.items():
            rows.append(
                {
                    "artifact": artifact,
                    "reveals": ", ".join(obs.get("reveals", [])) or "—",
                    "constrains": ", ".join(obs.get("constrains", [])) or "—",
                    "hides": ", ".join(obs.get("hides", [])) or "—",
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch")
    else:
        st.caption("No observation matrix registered for this dialect.")


# ---------------------------------------------------------------------------
# Cross-DAW compare view (the flagship)
# ---------------------------------------------------------------------------

def render_compare() -> None:
    st.header("Cross-DAW compare")
    st.caption(
        "The same production concepts across two DAWs: matched where "
        "semantically related, native-only where not, not-applicable where a "
        "dialect lacks the concept entirely."
    )
    names = list(drivers)
    left_default = names.index("Ableton Live") if "Ableton Live" in names else 0
    right_default = names.index("Cubase") if "Cubase" in names else min(1, len(names) - 1)

    col_l, col_r = st.columns(2)
    left_name = col_l.selectbox("Left dialect", names, index=left_default)
    right_name = col_r.selectbox("Right dialect", names, index=right_default)

    left = _load_for(drivers[left_name], "cmp-left")
    right = _load_for(drivers[right_name], "cmp-right")
    if left is None or right is None:
        st.stop()

    result = compare_sessions(left, right)
    summary = result.summary()

    m = st.columns(4)
    m[0].metric("Matched", summary["matched"])
    m[1].metric(f"{left.dialect}-only", summary["left_only"])
    m[2].metric(f"{right.dialect}-only", summary["right_only"])
    m[3].metric("Concepts", len({a.concept for a in result.alignments}))

    show = st.multiselect(
        "Show",
        ["exact", "close", "functional", "partial", "none"],
        default=["exact", "close", "functional", "partial", "none"],
    )

    st.subheader("Semantic alignment")
    st.caption(f"**{left.name}** ({left.dialect})  ⟷  **{right.name}** ({right.dialect})")
    for a in result.alignments:
        if a.equivalence not in show:
            continue
        badge = EQUIVALENCE_BADGE.get(a.equivalence, a.equivalence)
        left_cell = f"`{a.left_label}`" if a.left_label else "—"
        right_cell = f"`{a.right_label}`" if a.right_label else "—"
        c1, c2, c3 = st.columns([4, 3, 4])
        c1.markdown(f"{left_cell}")
        c2.markdown(f"<div style='text-align:center'>{badge}<br><span style='color:#888;font-size:0.8em'>{a.concept}</span></div>", unsafe_allow_html=True)
        c3.markdown(f"{right_cell}")
        with st.expander(f"why · {a.concept} · conf {a.confidence:.0%}", expanded=False):
            for b in a.basis:
                st.caption(f"• {b}")

    st.subheader("Applicability")
    st.caption(
        "A concept can be *not applicable* to a dialect (a native difference) — "
        "distinct from *applicable but unobserved* (an observability gap)."
    )
    app_rows = []
    for concept, sides in result.applicability.items():
        app_rows.append(
            {
                "concept": concept,
                f"{left.dialect}": sides.get("left", "unknown"),
                f"{right.dialect}": sides.get("right", "unknown"),
            }
        )
    st.dataframe(pd.DataFrame(app_rows), width="stretch")

    st.subheader("Graphs")
    gl, gr = st.columns(2)
    with gl:
        st.caption(f"{left.dialect} · {left.name}")
        _render_graph(left, hide_params=hide_params, key="cmp-left-graph")
    with gr:
        st.caption(f"{right.dialect} · {right.name}")
        _render_graph(right, hide_params=hide_params, key="cmp-right-graph")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if compare_mode:
    render_compare()
else:
    render_single()

st.divider()
st.caption(
    "Session State Explorer — a research instrument for representing DAW state "
    "across ecosystems while preserving native semantics, provenance, and "
    "observability. Recommendations are graph heuristics, not objective rules."
)
