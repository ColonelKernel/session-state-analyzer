"""Viz tests: pure logic (styles, filters, positions, labels, node options)
runs without pyvis/plotly; renderer tests importorskip the optional backends."""

import networkx as nx
import pytest

from session_explorer.core.viz import (
    MAX_LABEL_CHARS,
    OBSERVABILITY_COLORS,
    OBSERVABILITY_ORDER,
    PLOTLY_AVAILABLE,
    PYVIS_AVAILABLE,
    GraphFilters,
    build_plotly_figure,
    build_pyvis_html,
    filter_graph,
    get_node_style,
    layered_positions,
    legend_entries,
    node_color,
    observability_legend,
    pyvis_node_options,
    register_node_style,
    truncate_label,
    unregister_node_style,
)


def _graph() -> nx.DiGraph:
    """A small cross-dialect graph: typed nodes, some with observability."""

    g = nx.DiGraph(session_name="VizTest", dialect="logic")
    g.add_node("session", type="session", label="VizTest", observability="observed")
    g.add_node("audio-1", type="audio_evidence", label="01_Drums.wav", observability="observed")
    g.add_node("audio-2", type="audio_evidence", label="02_Bass.wav", observability="observed")
    g.add_node("track-1", type="inferred_track", label="Track: Drums",
               observability="inferred", confidence=0.8)
    g.add_node("note-1", type="channel_strip_note", label="Note: Drums",
               observability="annotation")
    g.add_node("hidden-1", type="hidden_state_marker", label="Automation unknown",
               observability="hidden")
    g.add_node("descriptor_test", type="descriptor_set", label="01_Drums.wav descriptors",
               observability="derived")
    g.add_node("rec-1", type="recommendation",
               label="Add channel-strip notes to improve DAW-state interpretability.",
               observability="derived")
    # A structural node with no observability attribute (REAPER/Ableton style).
    g.add_node("fx-1", type="fx", label="ReaEQ", enabled=True)

    g.add_edge("session", "audio-1", type="contains_audio")
    g.add_edge("session", "audio-2", type="contains_audio")
    g.add_edge("audio-1", "track-1", type="infers_track")
    g.add_edge("track-1", "note-1", type="annotated_by")
    g.add_edge("track-1", "hidden-1", type="has_hidden_state")
    g.add_edge("audio-1", "descriptor_test", type="has_descriptor")
    g.add_edge("note-1", "rec-1", type="supports_recommendation")
    g.add_edge("track-1", "fx-1", type="has_processor")
    return g


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


def test_truncate_label_short_names_untouched():
    assert truncate_label("Lead Vocal") == "Lead Vocal"


def test_truncate_label_long_names_ellipsized():
    long = "Add channel-strip notes to improve DAW-state interpretability."
    out = truncate_label(long)
    assert len(out) <= MAX_LABEL_CHARS
    assert out.endswith("…")
    # A "Track: "-prefixed demo track name must fit untruncated.
    assert truncate_label("Track: Backing Vocals Bounce") == "Track: Backing Vocals Bounce"


# ---------------------------------------------------------------------------
# Layered layout
# ---------------------------------------------------------------------------


def test_layered_positions_column_order():
    graph = _graph()
    positions = layered_positions(graph)
    # Every node gets a position.
    assert set(positions) == set(graph.nodes)
    # Column x increases with observability order: any observed node sits
    # left of any hidden node.
    by_class: dict = {}
    for node_id, data in graph.nodes(data=True):
        key = data.get("observability")
        if key in OBSERVABILITY_ORDER:
            by_class.setdefault(key, []).append(positions[node_id][0])
    present = [k for k in OBSERVABILITY_ORDER if k in by_class]
    xs = [max(by_class[k]) for k in present]
    assert xs == sorted(xs)
    # Nodes within a class share a column.
    for column_xs in by_class.values():
        assert len(set(column_xs)) == 1


def test_layered_positions_unclassified_nodes_column_after_derived():
    graph = _graph()
    positions = layered_positions(graph)
    derived_x = positions["rec-1"][0]
    # fx-1 has no observability: it columns up after the ordered classes.
    assert positions["fx-1"][0] > derived_x


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_filter_graph_hides_node_types_and_dangling_edges():
    graph = _graph()
    filtered = filter_graph(graph, GraphFilters(hidden_types={"descriptor_set", "recommendation"}))
    assert "descriptor_test" not in filtered
    assert "rec-1" not in filtered
    # Edges touching removed nodes are gone; the rest survive with data.
    assert not any(t == "descriptor_test" for _, t in filtered.edges)
    assert filtered.has_edge("session", "audio-1")
    # Graph-level metadata is carried over.
    assert filtered.graph["session_name"] == "VizTest"


def test_filter_graph_observability_only_keeps_anchor():
    graph = _graph()
    filtered = filter_graph(graph, GraphFilters(observability_only="annotation"))
    assert set(filtered.nodes) == {"session", "note-1"}


def test_filter_graph_subtree_keeps_neighbours_and_anchor():
    graph = _graph()
    filtered = filter_graph(graph, GraphFilters(only_subtree="track-1"))
    # The subtree root, its descendants and direct neighbours survive...
    assert {"track-1", "note-1", "hidden-1", "fx-1", "rec-1", "audio-1"} <= set(filtered.nodes)
    # ...anchors always survive; unrelated evidence does not.
    assert "session" in filtered
    assert "audio-2" not in filtered


def test_filter_graph_no_filters_is_identity():
    graph = _graph()
    filtered = filter_graph(graph)
    assert set(filtered.nodes) == set(graph.nodes)
    assert set(filtered.edges) == set(graph.edges)


# ---------------------------------------------------------------------------
# Theme: colours, registry, legends
# ---------------------------------------------------------------------------


def test_node_color_observability_wins_over_type():
    # inferred_track carries observability -> observability colour.
    assert node_color({"type": "inferred_track", "observability": "inferred"}) == \
        OBSERVABILITY_COLORS["inferred"]
    # fx has no observability -> its type colour from the registry.
    assert node_color({"type": "fx"}) == get_node_style("fx").color
    # Neither known -> the neutral default grey.
    assert node_color({}) == get_node_style(None).color


def test_registry_defaults_cover_all_three_prototypes():
    # REAPER lineage
    assert get_node_style("media_item").shape == "square"
    # Ableton lineage
    assert get_node_style("master_track").size == 28
    # Logic lineage (observability-coloured: no type colour of their own)
    assert get_node_style("hidden_state_marker").shape == "triangleDown"
    assert get_node_style("recommendation").shape == "hexagon"
    assert get_node_style("descriptor_set").color is None
    # Unknown types get the neutral default.
    assert get_node_style("no_such_type").legend == "Other"


def test_register_and_unregister_node_style():
    try:
        register_node_style("cubase_rack", color="#123456", shape="box",
                            size=20, legend="Cubase rack")
        assert get_node_style("cubase_rack").color == "#123456"
        assert ("Cubase rack", "#123456", "▬") in legend_entries()
    finally:
        unregister_node_style("cubase_rack")
    assert get_node_style("cubase_rack").legend == "Other"


def test_legend_entries_are_label_color_glyph_triples():
    entries = legend_entries()
    assert entries, "type legend must not be empty"
    for label, color, glyph in entries:
        assert label and color.startswith("#") and glyph


def test_observability_legend_matches_column_order():
    legend = observability_legend()
    assert [label for label, _ in legend] == OBSERVABILITY_ORDER
    assert dict(legend)["hidden"] == OBSERVABILITY_COLORS["hidden"]


# ---------------------------------------------------------------------------
# Node option building (pure — what the pyvis renderer feeds vis-network)
# ---------------------------------------------------------------------------


def test_pyvis_node_options_truncates_and_colors():
    graph = _graph()
    opts = pyvis_node_options("rec-1", graph.nodes["rec-1"])
    assert opts["label"].endswith("…") and len(opts["label"]) <= MAX_LABEL_CHARS
    assert opts["shape"] == "hexagon"
    assert opts["color"] == OBSERVABILITY_COLORS["derived"]
    assert "observability: derived" in opts["title"]


def test_pyvis_node_options_dark_fill_nodes_get_white_labels():
    graph = _graph()
    # pyvis silently overwrites per-node fonts when a constructor-level
    # font_color is set — the per-node font dict is what must carry it.
    assert pyvis_node_options("descriptor_test", graph.nodes["descriptor_test"])["font"]["color"] == "#ffffff"
    assert pyvis_node_options("audio-1", graph.nodes["audio-1"])["font"]["color"] == "#222222"


def test_pyvis_node_options_highlight_enlarges_and_outlines():
    graph = _graph()
    opts = pyvis_node_options("audio-1", graph.nodes["audio-1"], highlighted=True)
    assert opts["borderWidth"] == 4
    assert opts["size"] == 28
    assert opts["color"]["border"] == "#111111"
    assert opts["color"]["background"] == OBSERVABILITY_COLORS["observed"]


def test_pyvis_node_options_position_passthrough():
    opts = pyvis_node_options("n", {"type": "track", "label": "Drums"}, position=(260, -45))
    assert (opts["x"], opts["y"]) == (260, -45)


# ---------------------------------------------------------------------------
# Renderers (optional backends)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(PYVIS_AVAILABLE, reason="pyvis installed; the guard cannot trip")
def test_pyvis_missing_raises_clear_error():
    with pytest.raises(RuntimeError, match="pyvis"):
        build_pyvis_html(_graph())


@pytest.mark.skipif(PLOTLY_AVAILABLE, reason="plotly installed; the guard cannot trip")
def test_plotly_missing_raises_clear_error():
    with pytest.raises(RuntimeError, match="plotly"):
        build_plotly_figure(_graph())


def test_pyvis_html_freezes_physics_and_truncates():
    pytest.importorskip("pyvis")
    html = build_pyvis_html(_graph())
    assert "stabilizationIterationsDone" in html
    # Full recommendation titles are too long for node labels; the truncated
    # form (with ellipsis, JSON-escaped by pyvis) must be what is displayed.
    assert "…" in html or "\\u2026" in html


def test_pyvis_layered_layout_has_fixed_positions_no_physics_freeze():
    pytest.importorskip("pyvis")
    html = build_pyvis_html(_graph(), layout="layered")
    assert "stabilizationIterationsDone" not in html
    assert '"x":' in html and '"y":' in html
    # No physics means no stabilisation auto-fit: the explicit fit must be
    # injected or the default view renders zoomed-in.
    assert "network.fit()" in html


def test_pyvis_highlight_enlarges_nodes():
    pytest.importorskip("pyvis")
    html = build_pyvis_html(_graph(), highlight_ids=["audio-1"])
    assert '"borderWidth": 4' in html


def test_plotly_figure_builds_both_layouts():
    pytest.importorskip("plotly")
    fig = build_plotly_figure(_graph(), layout="layered")
    assert len(fig.data) == 2  # edge trace + node trace
    fig_force = build_plotly_figure(_graph(), filters=GraphFilters(hidden_types={"fx"}))
    assert len(fig_force.data) == 2
