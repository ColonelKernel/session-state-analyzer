"""Small presentation helpers shared across the workbench pages.

Consolidates the copies that had drifted into nearly every page module — the
bundle/DAW label formatters, the "nothing selected" guard, and the evidence-mix
segment palette — so each has a single definition and cannot diverge.
"""

from __future__ import annotations

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
