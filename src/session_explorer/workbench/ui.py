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
