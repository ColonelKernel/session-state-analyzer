"""Routing depth page: what a native "group" really is, and insert chains.

Two Phase-1 findings, rendered:

1. **Group decomposition** — a single native "group" noun (a folder, a submix
   bus, a VCA) fuses concepts the canonical model deliberately keeps apart:
   containment (``CONTAINS``), summing (``SUMS_TO``), control (``CONTROLS``
   VCA/edit-group), and incoming routing. :func:`graph_layers.decompose_group`
   splits it back into those four facets, and ``is_multi_concept`` proves the
   point quantitatively — surfaced here as a finding badge.
2. **Processing chain** — the ``processing`` graph layer
   (``CHANNEL_PROCESSED_BY`` + ``PRECEDES``) shows, per channel, which devices
   it hosts and in what order.

Both the Expert tab and the Guided "Groups & feedback" tab reuse the same
decomposition helpers, so the two faces cannot drift.
"""

from __future__ import annotations

from typing import List, Optional

import streamlit as st

from canonical_snapshot import CanonicalDAWSnapshot
from session_explorer.core.viz import (
    GraphFilters,
    build_plotly_figure,
    build_pyvis_html,
)
from session_explorer.graph_layers import (
    decompose_group,
    find_group_entities,
)
from session_explorer.loaders import SnapshotBundle, get_presentation
from session_explorer.workbench import compute
from session_explorer.workbench import copy as wcopy

from .canonical_graph import _GRAPH_HEIGHT, _embed_html
from .intervention import _static_table

_GROUP_GRAPH_HEIGHT = 420


# ---------------------------------------------------------------------------
# Shared helpers (used by both the Expert and Guided faces)
# ---------------------------------------------------------------------------


def _bundle_label(bundle: SnapshotBundle) -> str:
    daw = bundle.snapshot.source.daw
    try:
        display = get_presentation(daw).display_name
    except Exception:  # noqa: BLE001 - unknown daw still gets a label
        display = daw
    return f"{display} ({bundle.dir.name})"


def _entity_label(snapshot: CanonicalDAWSnapshot, entity_id: str) -> str:
    entity = snapshot.entity_by_id(entity_id)
    if entity is None:
        return entity_id
    name = entity.name or entity_id
    return f"{name} · {entity.entity_type}"


def _group_option_label(snapshot: CanonicalDAWSnapshot, entity_id: str) -> str:
    entity = snapshot.entity_by_id(entity_id)
    if entity is None:
        return entity_id
    roles = ", ".join(entity.semantic_roles) if entity.semantic_roles else "—"
    return f"{entity.name or entity_id} · {entity.entity_type} · [{roles}]"


def _facet_rows(snapshot: CanonicalDAWSnapshot, ids: List[str]) -> list[dict]:
    return [{"entity": _entity_label(snapshot, i)} for i in ids]


def _embed_channel_processing(
    bundle: SnapshotBundle, channel_id: str, height: int
) -> None:
    """The processing-layer subgraph rooted at one channel (devices in order)."""
    # Memoized per bundle: switching channel filters the same processing graph,
    # so it need not be rebuilt each time the channel selector changes.
    graph = compute.processing_graph_for(bundle)
    filters = GraphFilters(only_subtree=channel_id)
    try:
        html = build_pyvis_html(
            graph, height=f"{height}px", filters=filters
        )
        _embed_html(html, height=height)
    except Exception as exc:  # noqa: BLE001 - fall back, never blank-screen
        st.warning(f"PyVis rendering failed ({exc}); falling back to Plotly.")
        st.plotly_chart(
            build_plotly_figure(graph, filters=filters), width="stretch"
        )


def _pick_bundle(bundles: List[SnapshotBundle], key: str) -> Optional[SnapshotBundle]:
    if len(bundles) == 1:
        return bundles[0]
    return st.selectbox(
        "Session", bundles, format_func=_bundle_label, key=key
    )


# ---------------------------------------------------------------------------
# Grouping decomposition (shared body, plain-vs-research labels)
# ---------------------------------------------------------------------------


def _render_grouping(
    snapshot: CanonicalDAWSnapshot,
    *,
    key: str,
    col_labels: tuple[str, str, str, str],
    multi_template: str,
    single_note: Optional[str],
    pick_label: str,
    no_groups: str,
) -> None:
    group_ids = find_group_entities(snapshot)
    if not group_ids:
        st.info(no_groups)
        return

    group_id = st.selectbox(
        pick_label,
        group_ids,
        format_func=lambda gid: _group_option_label(snapshot, gid),
        key=key,
    )
    decomposition = decompose_group(snapshot, group_id)

    if decomposition.is_multi_concept():
        st.warning(multi_template.format(n=decomposition.concept_count()))
    elif single_note:
        st.caption(single_note)

    contains_col, sums_col, controls_col, routes_col = st.columns(4)
    facets = (
        (contains_col, col_labels[0], decomposition.contains),
        (sums_col, col_labels[1], decomposition.sums),
        (controls_col, col_labels[2], decomposition.controls),
        (routes_col, col_labels[3], decomposition.routes_in),
    )
    for column, label, ids in facets:
        with column:
            st.markdown(f"**{label}** ({len(ids)})")
            if ids:
                _static_table(_facet_rows(snapshot, ids))
            else:
                st.caption("—")


# ---------------------------------------------------------------------------
# Expert
# ---------------------------------------------------------------------------


def render(bundles: List[SnapshotBundle]) -> None:
    """Expert 'Routing depth' tab: group decomposition + per-channel chain."""
    st.header(wcopy.DEPTH["header"])
    st.caption(wcopy.DEPTH["intro"])

    if not bundles:
        st.info("Select at least one bundle in the sidebar.")
        return

    bundle = _pick_bundle(bundles, key="depth_bundle_expert")
    if bundle is None:
        return
    snapshot = bundle.snapshot

    st.subheader(wcopy.DEPTH["grouping_header"])
    st.caption(wcopy.DEPTH["grouping_caption"])
    _render_grouping(
        snapshot,
        key="depth_group_expert",
        col_labels=(
            wcopy.DEPTH["col_contains"],
            wcopy.DEPTH["col_sums"],
            wcopy.DEPTH["col_controls"],
            wcopy.DEPTH["col_routes_in"],
        ),
        multi_template=wcopy.DEPTH["grouping_multi"],
        single_note=wcopy.DEPTH["grouping_single"],
        pick_label="Group entity",
        no_groups=wcopy.DEPTH["grouping_no_groups"],
    )

    st.divider()

    st.subheader(wcopy.DEPTH["processing_header"])
    st.caption(wcopy.DEPTH["processing_caption"])
    channels = [e for e in snapshot.entities if e.entity_type == "CHANNEL"]
    if not channels:
        st.info(wcopy.DEPTH["no_channels"])
        return
    channel = st.selectbox(
        "Channel",
        channels,
        format_func=lambda e: e.name or e.id,
        key="depth_channel_expert",
    )
    _embed_channel_processing(bundle, channel.id, _GRAPH_HEIGHT - 200)


# ---------------------------------------------------------------------------
# Guided ("Groups & feedback")
# ---------------------------------------------------------------------------


def render_guided(bundles: List[SnapshotBundle]) -> None:
    """Guided tab: the same group decomposition in plain language, + feedback."""
    st.header(wcopy.DEPTH["guided_header"])
    st.markdown(wcopy.DEPTH["guided_intro"])

    if not bundles:
        st.info(wcopy.COPY["no_bundles"])
        return

    bundle = _pick_bundle(bundles, key="depth_bundle_guided")
    if bundle is None:
        return

    _render_grouping(
        bundle.snapshot,
        key="depth_group_guided",
        col_labels=(
            wcopy.DEPTH["guided_col_contains"],
            wcopy.DEPTH["guided_col_sums"],
            wcopy.DEPTH["guided_col_controls"],
            wcopy.DEPTH["guided_col_routes_in"],
        ),
        multi_template=wcopy.DEPTH["guided_multi"],
        single_note=None,
        pick_label=wcopy.DEPTH["guided_pick_group"],
        no_groups=wcopy.DEPTH["grouping_no_groups"],
    )

    st.divider()
    st.subheader(wcopy.DEPTH["guided_feedback_header"])
    st.markdown(wcopy.DEPTH["guided_feedback_body"])
