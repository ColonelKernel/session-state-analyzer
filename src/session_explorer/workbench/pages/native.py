"""Native payload page: the bundle's verbatim ``native.json``, beside the
registry's per-DAW presentation vocabulary.

Extracted verbatim from the app entry point so the Native view is a page
module like every other surface (and can become an ``st.Page`` body in the
navigation migration). Read-only, like the whole workbench.
"""

from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from session_explorer.loaders import SnapshotBundle, get_presentation
from session_explorer.workbench.ui import pick_bundle, require_bundle


def render(bundles: List[SnapshotBundle]) -> None:
    """The Native view over the focused bundle."""
    st.header("Native payload")
    if not require_bundle(bundles):
        return
    bundle = pick_bundle(bundles, "bundle_for_native")

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
