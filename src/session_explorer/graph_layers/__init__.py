"""Snapshot → layered graph: the analyzer's graph-building layer (P3).

``build_graph`` turns one flat :class:`~canonical_snapshot.CanonicalDAWSnapshot`
into a typed, observability-tagged ``networkx.DiGraph``; ``build_multi``
places several snapshots side by side in one graph (namespaced ids, no
invented cross-edges). ``LAYERS`` is the data-driven lens registry —
organizational, signal_flow, all — designed to grow additively (temporal,
automation) without new builder code.

Importing this package registers the UPPERCASE snapshot entity-type styles
with the shared viz theme, so ``core.viz`` renders snapshot graphs without
extra setup.
"""

from .analysis import (
    ROUTING_REL_TYPES,
    CycleReport,
    annotate_cycles,
    detect_cycles,
    routing_subgraph,
)
from .build import EVIDENCE_TO_OBSERVABILITY, build_graph, build_multi
from .grouping import (
    GroupDecomposition,
    decompose_group,
    find_group_entities,
    group_channel_id,
)
from .layers import LAYERS, LayerSpec, get_layer, layer_names, register_snapshot_styles

__all__ = [
    "EVIDENCE_TO_OBSERVABILITY",
    "build_graph",
    "build_multi",
    "LAYERS",
    "LayerSpec",
    "get_layer",
    "layer_names",
    "register_snapshot_styles",
    # routing analysis (cycles)
    "ROUTING_REL_TYPES",
    "CycleReport",
    "detect_cycles",
    "annotate_cycles",
    "routing_subgraph",
    # grouping decomposition
    "GroupDecomposition",
    "decompose_group",
    "find_group_entities",
    "group_channel_id",
]
