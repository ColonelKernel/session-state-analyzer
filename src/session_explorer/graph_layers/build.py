"""Snapshot → layered ``networkx`` graph (the snapshot-era graph builder).

The sibling of ``core.graph.build_session_graph`` for the flat v0.2 wire
format: entities become nodes as-is (UPPERCASE ``entity_type`` preserved),
relationships become typed edges, and every node carries an ``observability``
tag derived from its entity-level provenance record so the existing viz
colour channels apply unchanged.

The graph is a ``networkx.MultiDiGraph`` keyed by relationship id: two
relationships between the same endpoints (e.g. a folder child's ``SUMS_TO``
*and* its ``CHANNEL_ROUTES_TO (via=group_sum)`` — first observed in the wild
on the ``reaper_real`` fixture) each keep their own edge. A plain ``DiGraph``
silently kept only the last one, which misrepresents the snapshot.

``build_multi`` composes several snapshots into one graph side by side —
id namespaces (``reaper:``, ``ableton:``, ...) already prevent collisions,
and no cross-snapshot edges are invented: four DAWs in one view stay four
honest components until the alignment layer (P4) has reasons to say more.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, Optional

import networkx as nx

from canonical_snapshot import CanonicalDAWSnapshot

from .layers import LayerSpec, get_layer

# Wire evidence vocabulary → the viz observability vocabulary
# (theme.OBSERVABILITY_COLORS keys). Entities with no resolvable "*" record
# default to "observed" — the adapter parsed them from the artifact.
EVIDENCE_TO_OBSERVABILITY: Dict[str, str] = {
    "OBSERVED": "observed",
    "INFERRED": "inferred",
    "ANNOTATED": "annotation",
    "HIDDEN": "hidden",
}

# Canonical mixer properties copied onto nodes when present, so tooltips and
# inspectors see them without re-resolving the entity.
_KEY_PROPERTIES = ("volume_db", "pan", "mute", "solo")


def _entity_observability(entity, prov_by_id: Dict[str, Any]) -> str:
    """The node's epistemic class, from its entity-level ("*") prov record."""
    record = prov_by_id.get(entity.prov.get("*", ""))
    if record is None:
        return "observed"
    return EVIDENCE_TO_OBSERVABILITY.get(record.evidence, "observed")


def _id_namespace(snapshot: CanonicalDAWSnapshot) -> str:
    """The snapshot's id namespace ('reaper:project' → 'reaper')."""
    anchor = snapshot.project or (
        snapshot.entities[0].id if snapshot.entities else ""
    )
    return anchor.split(":", 1)[0] if ":" in anchor else anchor


def build_graph(
    snapshot: CanonicalDAWSnapshot, layer: str = "all"
) -> nx.MultiDiGraph:
    """One snapshot, one layer, one typed observability-tagged multidigraph.

    A node is included when an in-layer relationship touches it, or when its
    entity type is layer-relevant (see :class:`~.layers.LayerSpec`). Edges
    carry ``type`` (the rel_type, as-is) plus the relationship's properties;
    the edge key is the relationship id, so parallel relationships between
    the same endpoints are preserved one-for-one.
    """
    spec: LayerSpec = get_layer(layer)
    prov_by_id = {record.id: record for record in snapshot.provenance}
    entities_by_id = {entity.id: entity for entity in snapshot.entities}

    in_layer_rels = [
        rel
        for rel in snapshot.relationships
        if spec.includes_rel(rel.rel_type)
        and rel.source in entities_by_id
        and rel.target in entities_by_id
    ]
    touched = {rel.source for rel in in_layer_rels} | {
        rel.target for rel in in_layer_rels
    }

    graph = nx.MultiDiGraph()

    for entity in snapshot.entities:
        if entity.id not in touched and not spec.entity_is_relevant(
            entity.entity_type
        ):
            continue
        attrs: Dict[str, Any] = {
            "label": entity.name or entity.id,
            "type": entity.entity_type,
            "semantic_roles": list(entity.semantic_roles),
            "observability": _entity_observability(entity, prov_by_id),
            "availability": dict(entity.availability),
        }
        if entity.native is not None and entity.native.native_type:
            attrs["native_type"] = entity.native.native_type
        for key in _KEY_PROPERTIES:
            if key in entity.properties:
                attrs[key] = entity.properties[key]
        graph.add_node(entity.id, **attrs)

    for rel in in_layer_rels:
        edge_attrs = {
            key: value for key, value in rel.properties.items() if key != "type"
        }
        edge_attrs["type"] = rel.rel_type
        graph.add_edge(rel.source, rel.target, key=rel.id, **edge_attrs)

    graph.graph.update(_graph_metadata(graph, snapshot, spec))
    return graph


def build_multi(
    snapshots: Iterable[CanonicalDAWSnapshot], layer: str = "all"
) -> nx.MultiDiGraph:
    """Several snapshots side by side in one graph, no cross-edges.

    Dialect id namespaces are NOT sufficient to keep snapshots disjoint:
    two sessions from the same DAW (the normal same-DAW comparison case,
    e.g. the synthetic ``logic`` demo next to the real ``logic_real``
    capture) legitimately share a namespace and would silently merge.
    Every node is therefore relabelled with a per-snapshot ordinal prefix
    (``s0:``, ``s1:``, …); the original entity id survives as the node
    attribute ``entity_id`` and the ordinal as ``snapshot_ordinal``. The
    composed graph's metadata aggregates counts and records per-snapshot
    metadata under ``"snapshots"`` so the caller can still tell who
    brought what.
    """
    spec = get_layer(layer)  # validate the layer name once, loudly
    combined = nx.MultiDiGraph()
    per_snapshot_meta = []
    entity_counts: Counter = Counter()
    n_relationships = 0

    for ordinal, snapshot in enumerate(snapshots):
        graph = build_graph(snapshot, layer=spec.name)
        for node, data in graph.nodes(data=True):
            data.setdefault("entity_id", node)
            data["snapshot_ordinal"] = ordinal
        graph = nx.relabel_nodes(
            graph, {n: f"s{ordinal}:{n}" for n in graph.nodes}
        )
        combined.update(graph)  # nodes + edges with attributes
        per_snapshot_meta.append(dict(graph.graph))
        entity_counts.update(graph.graph.get("entity_counts", {}))
        n_relationships += graph.graph.get("n_relationships", 0)

    combined.graph.update(
        {
            "layer": spec.name,
            "daws": [meta.get("daw") for meta in per_snapshot_meta],
            "dialects": [meta.get("dialect") for meta in per_snapshot_meta],
            "entity_counts": dict(entity_counts),
            "n_relationships": n_relationships,
            "snapshots": per_snapshot_meta,
        }
    )
    return combined


def _graph_metadata(
    graph: nx.MultiDiGraph, snapshot: CanonicalDAWSnapshot, spec: LayerSpec
) -> Dict[str, Any]:
    entity_counts = Counter(
        data.get("type") for _, data in graph.nodes(data=True)
    )
    return {
        "dialect": _id_namespace(snapshot),
        "daw": snapshot.source.daw,
        "layer": spec.name,
        "entity_counts": dict(entity_counts),
        "n_relationships": graph.number_of_edges(),
    }
