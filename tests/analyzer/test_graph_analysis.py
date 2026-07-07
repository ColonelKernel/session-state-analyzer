"""Routing-cycle analysis (P6): feedback is data, detected and annotated.

``detect_cycles`` runs over the signal-forwarding routing subgraph only, is
bounded so a pathological graph cannot hang the analyzer, and never raises —
a cycle is a finding, not an error.
"""

from __future__ import annotations

import networkx as nx

from session_explorer.graph_layers import (
    ROUTING_REL_TYPES,
    annotate_cycles,
    detect_cycles,
    routing_subgraph,
)


def _send(graph: nx.DiGraph, src: str, dst: str, rel: str = "CHANNEL_SENDS_TO"):
    graph.add_edge(src, dst, type=rel)


def test_feedback_pair_is_detected():
    g = nx.DiGraph()
    _send(g, "a", "b")
    _send(g, "b", "a")
    report = detect_cycles(g)
    assert report.has_cycles
    assert report.cycle_nodes == frozenset({"a", "b"})
    assert report.cycle_edges == frozenset({("a", "b"), ("b", "a")})
    assert not report.truncated


def test_dag_has_no_cycles():
    g = nx.DiGraph()
    _send(g, "a", "b")
    _send(g, "b", "c")
    _send(g, "a", "c")
    report = detect_cycles(g)
    assert not report.has_cycles
    assert report.cycles == []
    assert report.cycle_nodes == frozenset()


def test_structural_edges_are_not_routing_cycles():
    """A TRACK_USES_CHANNEL 'loop' is not a routing cycle — those edges are
    excluded from the routing subgraph."""
    g = nx.DiGraph()
    g.add_edge("t", "c", type="TRACK_USES_CHANNEL")
    g.add_edge("c", "t", type="CHANNEL_PROCESSED_BY")
    report = detect_cycles(g)
    assert not report.has_cycles
    assert "TRACK_USES_CHANNEL" not in ROUTING_REL_TYPES
    assert "CHANNEL_PROCESSED_BY" not in ROUTING_REL_TYPES


def test_routing_subgraph_filters_by_type():
    g = nx.DiGraph()
    _send(g, "a", "b")
    g.add_edge("x", "y", type="TRACK_USES_CHANNEL")
    sub = routing_subgraph(g)
    assert set(sub.edges) == {("a", "b")}
    assert "x" not in sub


def test_max_cycles_truncates():
    """Many independent 2-cycles; a low bound truncates and flags it."""
    g = nx.DiGraph()
    for i in range(10):
        _send(g, f"a{i}", f"b{i}")
        _send(g, f"b{i}", f"a{i}")
    report = detect_cycles(g, max_cycles=3)
    assert report.truncated
    assert len(report.cycles) == 3

    full = detect_cycles(g, max_cycles=256)
    assert not full.truncated
    assert len(full.cycles) == 10


def test_annotate_sets_in_cycle_on_nodes_and_edges():
    g = nx.DiGraph()
    _send(g, "a", "b")
    _send(g, "b", "a")
    _send(g, "b", "c")  # c is out of the cycle
    report = detect_cycles(g)
    annotate_cycles(g, report)
    assert g.nodes["a"]["in_cycle"] is True
    assert g.nodes["b"]["in_cycle"] is True
    assert g.nodes["c"]["in_cycle"] is False
    assert g.edges["a", "b"]["in_cycle"] is True
    assert g.edges["b", "c"]["in_cycle"] is False


def test_annotate_copy_leaves_original_untouched():
    g = nx.DiGraph()
    _send(g, "a", "b")
    _send(g, "b", "a")
    report = detect_cycles(g)
    annotated = annotate_cycles(g, report, copy=True)
    assert annotated is not g
    assert "in_cycle" not in g.nodes["a"]
    assert annotated.nodes["a"]["in_cycle"] is True
