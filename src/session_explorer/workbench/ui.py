"""Small presentation helpers shared across the workbench pages.

Consolidates the copies that had drifted into nearly every page module — the
bundle/DAW label formatters, the "nothing selected" guard, the evidence-mix
segment palette, and the cross-page render helpers (the HTML embed, the
static table, the value formatter) — so each has a single definition and
cannot diverge.
"""

from __future__ import annotations

import html as _html
from typing import Sequence

import streamlit as st

from session_explorer.core.viz import OBSERVABILITY_COLORS
from session_explorer.loaders import SnapshotBundle, get_presentation

# Shown by :func:`require_bundle` when an Expert page needs a loaded bundle and
# none is selected.
SELECT_BUNDLE_HINT = "Select at least one bundle in the sidebar."

# The five-bucket evidence-mix palette shared by the atlas cell bars and the
# guided overview mini-bars. ``inferred`` and ``annotated`` stay distinct; the
# grey ``absent`` tail folds unsupported / not-present / unknown. Keyed exactly
# as the mix dicts that consume it, and derived once from the shared
# observability colours so the two bar renderers cannot drift apart.
MIX_SEGMENT_COLORS = {
    "observed": OBSERVABILITY_COLORS["observed"],
    "inferred": OBSERVABILITY_COLORS["inferred"],
    "annotated": OBSERVABILITY_COLORS["annotation"],
    "hidden": OBSERVABILITY_COLORS["hidden"],
    "absent": OBSERVABILITY_COLORS["unknown"],
}


def daw_label(daw: str) -> str:
    """A DAW's presentation display name, falling back to its raw id."""
    try:
        return get_presentation(daw).display_name
    except Exception:  # noqa: BLE001 - an unknown daw still gets a label
        return daw


def bundle_label(bundle: SnapshotBundle) -> str:
    """A bundle's selectbox label, e.g. ``"Ableton Live (ableton)"``."""
    return f"{daw_label(bundle.snapshot.source.daw)} ({bundle.dir.name})"


def require_bundle(bundles: Sequence[SnapshotBundle]) -> bool:
    """Guard for the Expert per-bundle pages.

    When ``bundles`` is empty, show the standard hint and return ``False`` so the
    caller can ``return`` early; otherwise return ``True``.
    """
    if not bundles:
        st.info(SELECT_BUNDLE_HINT)
        return False
    return True


# The one bundle the user is currently focused on, shared by every per-bundle
# surface (Entity inspector, Routing depth, Parameter influence, Native,
# Evidence, and Guided's Groups & feedback). Holds a bundle directory name.
FOCUS_BUNDLE_KEY = "focus_bundle"

# Every picker carries the same label and hint so the cross-tab follow reads
# as one control, not as state leaking between unrelated widgets.
PICK_BUNDLE_LABEL = "Session"
PICK_BUNDLE_HELP = (
    "One shared choice — every per-session view follows it across tabs."
)


def pick_bundle(bundles: Sequence[SnapshotBundle], key: str) -> SnapshotBundle:
    """A bundle selectbox whose choice follows the user across tabs.

    Every per-bundle surface used to keep its own selection, so picking Cubase
    in the Entity inspector still showed Ableton in Routing depth. All surfaces
    now read and write one shared focus (:data:`FOCUS_BUNDLE_KEY`), and all
    carry the same label + hint so the follow behaviour is legible as one
    control.

    ``st.tabs`` renders every tab body each run, so the pickers coexist in one
    run and must keep **distinct widget keys** (one shared key would raise
    DuplicateWidgetID). The sync goes through session state instead: before a
    picker is instantiated its stored value is repaired to the shared focus,
    and its ``on_change`` writes the new choice back. Options are directory
    names (stable across the cached loader's copies); the label stays friendly.

    The focus is kept equal to what is actually displayed: when the focused
    bundle is unloaded, the focus itself moves to the fallback — a stale focus
    would otherwise snap every picker back the moment that bundle reloads
    (e.g. via "Load all"), mid-analysis and without warning.

    Callers guard for emptiness first (``require_bundle``); with exactly one
    bundle there is nothing to pick, so a caption naming it replaces the
    widget — every surface still states what it is showing.
    """
    by_name = {bundle.dir.name: bundle for bundle in bundles}
    if len(by_name) == 1:
        only = next(iter(by_name.values()))
        st.caption(f"{PICK_BUNDLE_LABEL}: {bundle_label(only)}")
        return only
    names = list(by_name)

    focus = st.session_state.get(FOCUS_BUNDLE_KEY)
    if focus not in by_name:
        focus = names[0]
        st.session_state[FOCUS_BUNDLE_KEY] = focus
    if st.session_state.get(key) != focus:
        st.session_state[key] = focus

    def _sync() -> None:
        st.session_state[FOCUS_BUNDLE_KEY] = st.session_state[key]

    name = st.selectbox(
        PICK_BUNDLE_LABEL,
        names,
        format_func=lambda n: bundle_label(by_name[n]),
        key=key,
        on_change=_sync,
        help=PICK_BUNDLE_HELP,
    )
    return by_name[name]


def keep(*keys: str) -> None:
    """Defeat widget-state garbage collection for the given session keys.

    A widget's state is dropped on any run where the widget is not
    instantiated — e.g. the Expert graph-layer radio on a run showing the
    Native view, or (after the pages migration) any widget on a non-active
    page. Re-assigning the value marks it programmatically-set, so Streamlit
    keeps it alive; the widget then resumes from the preserved value when it
    is next instantiated.

    Must run BEFORE any widget with these keys is created in the current run
    (call it once, early in the entry script).
    """
    for key in keys:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]


# Default embed height for PyVis graph HTML, shared by every graph surface.
GRAPH_HEIGHT = 660


def embed_html(html: str, height: int = GRAPH_HEIGHT) -> None:
    """Embed standalone PyVis HTML (st.iframe; components.html on older Streamlit)."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height, width="stretch")
    else:  # pragma: no cover - older streamlit
        st.components.v1.html(html, height=height, scrolling=False)


def static_table(rows: list[dict]) -> None:
    """Render a small fixed table as static HTML (immediate first-frame paint).

    ``st.dataframe`` draws to a lazily-painted canvas grid: for these tiny
    fixed tables it flashes an empty box for ~a second before the rows appear.
    These tables never scroll, sort, or resize, so a plain server-rendered
    ``<table>`` is both correct and instant. Cell text is escaped — entity
    names ultimately come from DAW session data.
    """
    if not rows:
        return
    cols = list(rows[0].keys())
    head = "".join(
        "<th style='text-align:left;padding:6px 10px;font-weight:600;"
        "font-size:0.78rem;opacity:0.7;"
        "border-bottom:1px solid rgba(128,128,128,0.35)'>"
        f"{_html.escape(str(c))}</th>"
        for c in cols
    )
    body = "".join(
        "<tr>"
        + "".join(
            "<td style='padding:6px 10px;font-size:0.85rem;"
            "border-bottom:1px solid rgba(128,128,128,0.15)'>"
            f"{_html.escape(str(row.get(c, '')))}</td>"
            for c in cols
        )
        + "</tr>"
        for row in rows
    )
    st.markdown(
        "<table style='width:100%;border-collapse:collapse;margin:2px 0 8px'>"
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>",
        unsafe_allow_html=True,
    )


def fmt_value(value) -> str:
    """A parameter/metric value as a short human string ("—", "on", "0.7")."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)
