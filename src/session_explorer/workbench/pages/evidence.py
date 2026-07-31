"""Evidence page: the focused bundle's deduplicated provenance store as a
table, plus the adapter's recorded warnings and failures.

Extracted verbatim from the app entry point so the Evidence view is a page
module like every other surface (and can become an ``st.Page`` body in the
navigation migration). Read-only, like the whole workbench.
"""

from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from session_explorer.loaders import SnapshotBundle
from session_explorer.workbench.ui import pick_bundle, require_bundle


def render(bundles: List[SnapshotBundle]) -> None:
    """The Evidence view over the focused bundle."""
    st.header("Evidence — the provenance store")
    if not require_bundle(bundles):
        return
    bundle = pick_bundle(bundles, "bundle_for_evidence")

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
