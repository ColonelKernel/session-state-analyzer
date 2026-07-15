"""Routing-graph analysis: feedback cycles as data, never as errors.

A session's routing graph can legitimately contain feedback: a send from A to
B and a send from B back to A, or a longer ring. Producers build these on
purpose (and sometimes by accident — which is itself worth surfacing), so the
analyzer treats a cycle as a *finding* it can measure and annotate, never as a
validation error. :func:`detect_cycles` extracts the signal-forwarding routing
subgraph, enumerates its simple cycles under a hard bound, and returns a
:class:`CycleReport`; :func:`annotate_cycles` writes the finding back onto a
graph as ``in_cycle`` node/edge attributes the renderer can read directly.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import FrozenSet, List, Tuple

import networkx as nx

# The edge types that carry signal from one channel to another — the only
# edges a routing cycle can be built from. Structural edges (TRACK_USES_CHANNEL,
# CHANNEL_PROCESSED_BY) do not forward signal and are deliberately excluded, so
# a lane sharing a channel never registers as feedback.
ROUTING_REL_TYPES: FrozenSet[str] = frozenset(
    {"CHANNEL_SENDS_TO", "CHANNEL_ROUTES_TO", "SUMS_TO"}
)


def routing_subgraph(
    graph: nx.DiGraph, rel_types: FrozenSet[str] = ROUTING_REL_TYPES
) -> nx.DiGraph:
    """The edge-type-filtered signal-forwarding subgraph.

    Keeps only edges whose ``type`` is in ``rel_types`` (with their attributes);
    endpoints of a kept edge come along. Returns a fresh graph of the same
    class as ``graph`` (``MultiDiGraph`` in, ``MultiDiGraph`` out — parallel
    routing edges survive) — never a view — so it is safe to enumerate and
    annotate independently of ``graph``.
    """
    sub = graph.__class__()
    if graph.is_multigraph():
        for source, target, key, data in graph.edges(keys=True, data=True):
            if data.get("type") in rel_types:
                sub.add_edge(source, target, key=key, **data)
    else:
        for source, target, data in graph.edges(data=True):
            if data.get("type") in rel_types:
                sub.add_edge(source, target, **data)
    return sub


@dataclass(frozen=True)
class CycleReport:
    """The feedback finding for one routing graph.

    ``cycles`` lists the simple cycles, each a list of node ids in loop order.
    ``cycle_edges`` / ``cycle_nodes`` are the flattened participants, for
    annotation and highlighting. ``truncated`` is ``True`` when enumeration hit
    ``max_cycles`` and stopped — the report is then a lower bound, flagged
    honestly rather than silently capped.
    """

    cycles: List[List[str]] = field(default_factory=list)
    cycle_edges: FrozenSet[Tuple[str, str]] = field(default_factory=frozenset)
    cycle_nodes: FrozenSet[str] = field(default_factory=frozenset)
    truncated: bool = False

    @property
    def has_cycles(self) -> bool:
        """Whether any routing feedback was found."""
        return bool(self.cycles)


def detect_cycles(
    graph: nx.DiGraph,
    *,
    rel_types: FrozenSet[str] = ROUTING_REL_TYPES,
    max_cycles: int = 256,
) -> CycleReport:
    """Enumerate routing feedback cycles, bounded at ``max_cycles``.

    Runs ``networkx.simple_cycles`` over :func:`routing_subgraph` and takes at
    most ``max_cycles + 1`` cycles via ``itertools.islice`` — the ``+ 1`` is
    the truncation probe: if an extra cycle exists, ``truncated`` is set and the
    extra is dropped, so the flag is exact and the returned list is bounded.
    Feedback is data; this never raises.

    A cycle is a *node* loop: two parallel routing edges between the same
    channels (SUMS_TO next to CHANNEL_ROUTES_TO) are one hop, not two distinct
    cycles, so enumeration runs on the condensed simple digraph of the routing
    subgraph.
    """
    sub = routing_subgraph(graph, rel_types)
    if sub.is_multigraph():
        sub = nx.DiGraph(sub)  # condense parallel edges for node-cycle search
    found = [
        list(cycle)
        for cycle in itertools.islice(nx.simple_cycles(sub), max_cycles + 1)
    ]
    truncated = len(found) > max_cycles
    if truncated:
        found = found[:max_cycles]

    edges: set[Tuple[str, str]] = set()
    nodes: set[str] = set()
    for cycle in found:
        nodes.update(cycle)
        length = len(cycle)
        for idx in range(length):
            edges.add((cycle[idx], cycle[(idx + 1) % length]))
    return CycleReport(
        cycles=found,
        cycle_edges=frozenset(edges),
        cycle_nodes=frozenset(nodes),
        truncated=truncated,
    )


def annotate_cycles(
    graph: nx.DiGraph, report: CycleReport, *, copy: bool = False
) -> nx.DiGraph:
    """Write ``in_cycle`` onto every node/edge, ``True`` where it participates.

    Mutates ``graph`` in place and returns it; pass ``copy=True`` to annotate a
    detached copy and leave the original untouched. Every node and edge gets an
    explicit boolean ``in_cycle`` so the renderer never has to guard a missing
    attribute.
    """
    target = graph.copy() if copy else graph
    for node in target.nodes:
        target.nodes[node]["in_cycle"] = node in report.cycle_nodes
    if target.is_multigraph():
        # Every parallel edge on a cycling (source, dest) pair participates:
        # the cycle is a node loop, and each relationship on that hop carries
        # signal around it.
        for source, dest, key in target.edges(keys=True):
            target.edges[source, dest, key]["in_cycle"] = (
                source,
                dest,
            ) in report.cycle_edges
    else:
        for source, dest in target.edges:
            target.edges[source, dest]["in_cycle"] = (
                source,
                dest,
            ) in report.cycle_edges
    return target
