"""Snapshot → layered ``networkx`` graph (the snapshot-era graph builder).

The sibling of ``core.graph.build_session_graph`` for the flat v0.2 wire
format: entities become nodes as-is (UPPERCASE ``entity_type`` preserved),
relationships become typed edges, and every node carries an ``observability``
tag derived from its entity-level provenance record so the existing viz
colour channels apply unchanged.

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
) -> nx.DiGraph:
    """One snapshot, one layer, one typed observability-tagged digraph.

    A node is included when an in-layer relationship touches it, or when its
    entity type is layer-relevant (see :class:`~.layers.LayerSpec`). Edges
    carry ``type`` (the rel_type, as-is) plus the relationship's properties.
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

    graph = nx.DiGraph()

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
        graph.add_edge(rel.source, rel.target, **edge_attrs)

    graph.graph.update(_graph_metadata(graph, snapshot, spec))
    return graph


def build_multi(
    snapshots: Iterable[CanonicalDAWSnapshot], layer: str = "all"
) -> nx.DiGraph:
    """Several snapshots side by side in one graph, no cross-edges.

    Id namespaces keep the DAWs disjoint; the composed graph's metadata
    aggregates counts and records the per-snapshot metadata under
    ``"snapshots"`` so the caller can still tell who brought what.
    """
    spec = get_layer(layer)  # validate the layer name once, loudly
    combined = nx.DiGraph()
    per_snapshot_meta = []
    entity_counts: Counter = Counter()
    n_relationships = 0

    for snapshot in snapshots:
        graph = build_graph(snapshot, layer=spec.name)
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
    graph: nx.DiGraph, snapshot: CanonicalDAWSnapshot, spec: LayerSpec
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
