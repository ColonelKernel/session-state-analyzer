"""The layer registry: which relationships (and lone entities) each view shows.

A *layer* is a data-driven lens over one flat snapshot: a set of relationship
types plus the entity types that belong in the lens even when no in-layer
edge touches them. Nodes earn their place either by participating in an
in-layer relationship or by being of a layer-relevant type — a MEDIA_ASSET
with no REFERENCES_ASSET edge still belongs in the organizational view,
but has no business in the signal-flow view.

The registry is deliberately additive: later layers (temporal, automation)
are new ``LayerSpec`` entries, not new builder code.

This module also registers the visual styles for the UPPERCASE snapshot
entity types with the shared viz theme, mapping the snapshot vocabulary onto
the existing visual language (project star, track dot, processor box, ...).
Types styled *colorless* are coloured by their observability class instead —
the epistemic colour channel takes over where no type colour is claimed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional

from session_explorer.core.viz import theme


@dataclass(frozen=True)
class LayerSpec:
    """One lens over a snapshot.

    ``rel_types`` — relationship types included in this layer; ``None`` means
    every relationship (the "all" layer).

    ``entity_types`` — entity types that are *layer-relevant*: included even
    with no in-layer edges. ``None`` means every entity type is relevant.
    Entities touched by an in-layer relationship are always included,
    whatever their type.
    """

    name: str
    rel_types: Optional[FrozenSet[str]]
    entity_types: Optional[FrozenSet[str]]

    def includes_rel(self, rel_type: str) -> bool:
        return self.rel_types is None or rel_type in self.rel_types

    def entity_is_relevant(self, entity_type: str) -> bool:
        return self.entity_types is None or entity_type in self.entity_types


ORGANIZATIONAL = LayerSpec(
    name="organizational",
    rel_types=frozenset(
        {
            "CONTAINS",
            "TRACK_CONTAINS_TEMPORAL_OBJECT",
            "TRACK_USES_CHANNEL",
            "REFERENCES_ASSET",
            "ALTERNATIVE_OF",
        }
    ),
    # What the session *is made of*: project structure, lanes, content,
    # assets, containers, annotations. Mixer-side types (CHANNEL, PROCESSOR,
    # ROUTING_ENDPOINT) appear here only via in-layer edges such as
    # TRACK_USES_CHANNEL — never as strays.
    entity_types=frozenset(
        {
            "PROJECT",
            "TIMELINE",
            "TRACK",
            "TEMPORAL_OBJECT",
            "MEDIA_ASSET",
            "MUSICAL_CONTENT",
            "STRUCTURAL_CONTAINER",
            "VARIANT",
            "ANNOTATION",
        }
    ),
)

SIGNAL_FLOW = LayerSpec(
    name="signal_flow",
    rel_types=frozenset(
        {
            "TRACK_USES_CHANNEL",
            "CHANNEL_SENDS_TO",
            "CHANNEL_ROUTES_TO",
            "CHANNEL_PROCESSED_BY",
            "SUMS_TO",
        }
    ),
    # Where the signal *goes*: an isolated CHANNEL or ROUTING_ENDPOINT is
    # still signal-flow (a channel with no observed routing is a finding);
    # an isolated TRACK or MEDIA_ASSET is not.
    entity_types=frozenset({"CHANNEL", "ROUTING_ENDPOINT"}),
)

ALL = LayerSpec(name="all", rel_types=None, entity_types=None)

LAYERS: Dict[str, LayerSpec] = {
    spec.name: spec for spec in (ORGANIZATIONAL, SIGNAL_FLOW, ALL)
}


def layer_names() -> List[str]:
    return list(LAYERS)


def get_layer(name: str) -> LayerSpec:
    """The named layer spec; loud KeyError listing the known layers."""
    try:
        return LAYERS[name]
    except KeyError:
        raise KeyError(
            f"unknown graph layer {name!r}; known layers: {sorted(LAYERS)}"
        ) from None


# ---------------------------------------------------------------------------
# Snapshot entity-type styles (UPPERCASE vocabulary → existing visual language)
# ---------------------------------------------------------------------------

# Types with no ``color`` are coloured by observability class (Logic lineage);
# they carry no legend entry of their own — the observability legend covers
# them. ``font_color`` is set where the shape draws its label inside a fill
# that may be dark.
_SNAPSHOT_NODE_STYLES: Dict[str, dict] = {
    "PROJECT": dict(color="#F2C14E", shape="star", size=34, legend="Project"),
    "TRACK": dict(color="#4EA8DE", shape="dot", size=24, legend="Track"),
    "CHANNEL": dict(color="#2A9D8F", shape="hexagon", size=20, legend="Channel"),
    "PROCESSOR": dict(color="#E76F51", shape="box", size=16, legend="Processor"),
    "PARAMETER": dict(color="#CCCCCC", shape="dot", size=8, legend="Parameter"),
    "TEMPORAL_OBJECT": dict(
        color="#80CED7", shape="square", size=14, legend="Temporal object"
    ),
    "MEDIA_ASSET": dict(
        color="#B7E4C7", shape="triangle", size=12, legend="Media asset"
    ),
    "STRUCTURAL_CONTAINER": dict(
        color="#9B8ADE", shape="diamond", size=18, legend="Container"
    ),
    "ROUTING_ENDPOINT": dict(shape="hexagon", size=14),
    "ANNOTATION": dict(shape="box", size=14),
    "OBSERVATION": dict(shape="ellipse", size=14, font_color="#ffffff"),
    "RENDER": dict(shape="database", size=14, font_color="#ffffff"),
    "INTERVENTION": dict(shape="database", size=14, font_color="#ffffff"),
}


def register_snapshot_styles() -> None:
    """Teach the shared theme registry the snapshot entity-type vocabulary.

    Idempotent; called at import so any consumer of ``graph_layers`` renders
    snapshot graphs in the shared visual language without extra setup.
    """
    for node_type, style in _SNAPSHOT_NODE_STYLES.items():
        theme.register_node_style(node_type, **style)


register_snapshot_styles()
