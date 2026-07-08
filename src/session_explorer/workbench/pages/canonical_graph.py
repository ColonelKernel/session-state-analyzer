"""Canonical graph page: N snapshots, one layered graph, one visual language.

Four observation instruments rendered side by side in a single canonical
view — namespaced ids keep them disjoint components; no cross-DAW edges are
invented. Nodes are coloured by observability where it deviates from plain
observation (inferred / annotation / hidden), by entity type otherwise.
"""

from __future__ import annotations

from typing import Iterable, List

import networkx as nx
import streamlit as st

from session_explorer.core.viz import (
    OBSERVABILITY_COLORS,
    SHAPE_GLYPH,
    build_plotly_figure,
    build_pyvis_html,
    get_node_style,
    legend_entries,
    observability_legend,
)
from session_explorer.graph_layers import annotate_cycles, build_multi, detect_cycles
from session_explorer.loaders import SnapshotBundle

_GRAPH_HEIGHT = 660

# Entity types the P3 snapshot builder emits, in legend order.
_SNAPSHOT_LEGEND_TYPES = (
    "PROJECT",
    "TRACK",
    "CHANNEL",
    "PROCESSOR",
    "PARAMETER",
    "TEMPORAL_OBJECT",
    "MEDIA_ASSET",
    "STRUCTURAL_CONTAINER",
)


def _filter_by_observability(graph: nx.DiGraph, keep: set[str]) -> nx.DiGraph:
    """Subgraph of nodes whose observability class is in ``keep``."""
    nodes = [
        node_id
        for node_id, data in graph.nodes(data=True)
        if data.get("observability", "observed") in keep
    ]
    filtered = graph.subgraph(nodes).copy()
    filtered.graph.update(graph.graph)
    return filtered


def _embed_html(html: str, height: int = _GRAPH_HEIGHT) -> None:
    """Embed standalone PyVis HTML (st.iframe; components.html on older Streamlit)."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height, width="stretch")
    else:  # pragma: no cover - older streamlit
        st.components.v1.html(html, height=height, scrolling=False)


def _render_legend(graph: nx.DiGraph) -> None:
    present_types = {data.get("type") for _, data in graph.nodes(data=True)}
    type_rows = []
    for entity_type in _SNAPSHOT_LEGEND_TYPES:
        style = get_node_style(entity_type)
        if style.legend and style.color and entity_type in present_types:
            glyph = SHAPE_GLYPH.get(style.shape, "●")
            type_rows.append(
                f'<span style="color:{style.color}">{glyph}</span> {style.legend}'
            )
    # Any additionally registered coloured types present in the graph.
    covered = {get_node_style(t).legend for t in _SNAPSHOT_LEGEND_TYPES}
    for label, color, glyph in legend_entries():
        if label in covered:
            continue
        for entity_type in present_types:
            style = get_node_style(entity_type)
            if style.legend == label and style.color:
                type_rows.append(f'<span style="color:{color}">{glyph}</span> {label}')
                covered.add(label)

    obs_rows = [
        f'<span style="color:{color}">■</span> {label}'
        for label, color in observability_legend()
    ]

    left, right = st.columns(2)
    with left:
        st.caption("Entity types")
        st.markdown("&nbsp;&nbsp;".join(type_rows), unsafe_allow_html=True)
    with right:
        st.caption("Observability (colour overrides type when not observed)")
        st.markdown("&nbsp;&nbsp;".join(obs_rows), unsafe_allow_html=True)


def _render_cycle_finding(graph: nx.DiGraph, report) -> None:
    """Surface routing feedback as a *finding* — a warning + the ring listing.

    Feedback is legitimate session data, not an error: the badge names how many
    rings were found and the expander spells each one out in node labels, so a
    reader sees exactly which channels close the loop.
    """
    n = len(report.cycles)
    plural = "cycle" if n == 1 else "cycles"
    suffix = " (lower bound — enumeration truncated)" if report.truncated else ""
    st.warning(
        f"Feedback loop detected: {n} {plural} in the routing graph{suffix}. "
        "This is a finding, not an error — a send path returns to where it "
        "started. The ring is highlighted below."
    )
    with st.expander(f"The feedback {plural} ({n})"):
        for cycle in report.cycles:
            labels = [str(graph.nodes[nid].get("label", nid)) for nid in cycle]
            if labels:
                ring = " → ".join(labels + [labels[0]])
                st.markdown(f"- {ring}")


def render(bundles: List[SnapshotBundle], layer: str) -> None:
    """The canonical graph over the selected bundles for the chosen layer."""
    st.session_state["graph_html_chars"] = 0
    st.session_state["graph_backend"] = None
    st.session_state["graph_has_cycles"] = False

    if not bundles:
        st.info("Select at least one bundle in the sidebar.")
        return

    graph = build_multi([bundle.snapshot for bundle in bundles], layer=layer)

    # Feedback cycles are data, never a validation error: detect them on the
    # routing subgraph, annotate the composed graph in place (so ``in_cycle``
    # rides through the observability subgraph copy into both renderers), and
    # surface the finding as a badge + highlight.
    cycle_report = detect_cycles(graph)
    annotate_cycles(graph, cycle_report)
    st.session_state["graph_has_cycles"] = cycle_report.has_cycles
    if cycle_report.has_cycles:
        _render_cycle_finding(graph, cycle_report)

    # Observability filter -------------------------------------------------
    present: Iterable[str] = sorted(
        {data.get("observability", "observed") for _, data in graph.nodes(data=True)}
    )
    st.caption("Observability filter")
    columns = st.columns(max(len(list(present)), 1))
    keep: set[str] = set()
    for column, obs_class in zip(columns, present):
        color = OBSERVABILITY_COLORS.get(obs_class, "#7F8C8D")
        with column:
            if st.checkbox(obs_class, value=True, key=f"obs_{obs_class}"):
                keep.add(obs_class)
            st.markdown(
                f'<span style="color:{color}">■</span>', unsafe_allow_html=True
            )
    display_graph = _filter_by_observability(graph, keep)

    st.caption(
        f"Layer **{graph.graph.get('layer')}** · "
        f"{display_graph.number_of_nodes()} nodes · "
        f"{display_graph.number_of_edges()} edges · "
        f"DAWs: {', '.join(str(d) for d in graph.graph.get('daws', []))}"
    )

    if display_graph.number_of_nodes() == 0:
        st.info("Nothing to show: every node is filtered out.")
        return

    highlight_ids = list(cycle_report.cycle_nodes)
    try:
        html = build_pyvis_html(
            display_graph,
            height=f"{_GRAPH_HEIGHT - 10}px",
            highlight_ids=highlight_ids,
        )
        _embed_html(html)
        st.session_state["graph_html_chars"] = len(html)
        st.session_state["graph_backend"] = "pyvis"
    except Exception as exc:  # noqa: BLE001 - fall back, never blank-screen
        st.warning(f"PyVis rendering failed ({exc}); falling back to Plotly.")
        st.plotly_chart(
            build_plotly_figure(display_graph, highlight_ids=highlight_ids),
            width="stretch",
        )
        st.session_state["graph_backend"] = "plotly"

    _render_legend(graph)
