"""Shared visual language for the session graph.

Two colour channels coexist, and their precedence is the core
interpretability affordance of the tool:

1. **Observability** (Logic lineage): nodes carrying an ``observability``
   attribute are coloured by epistemic class — observed evidence, inferred
   state, user annotations, hidden-state markers and derived analyses are
   visually distinct.
2. **Node type** (REAPER/Ableton lineage): nodes without an observability
   attribute fall back to their node-type colour from the style registry.

The registry is parameterizable: dialects and graph builders may register
additional node types (or override the defaults) without touching core. The
defaults shipped here are the union of the three prototypes' node styles.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Observability colour scheme (Logic lineage)
# ---------------------------------------------------------------------------

# Colour per observability class (used by both backends and the UI legend).
OBSERVABILITY_COLORS: Dict[str, str] = {
    "observed": "#2E86DE",     # blue
    "inferred": "#27AE60",     # green
    "annotation": "#F39C12",   # orange
    "hidden": "#C0392B",       # red
    "derived": "#8E44AD",      # purple
    "unknown": "#7F8C8D",      # grey
}

# Left-to-right column order for the layered layout.
OBSERVABILITY_ORDER: List[str] = ["observed", "inferred", "annotation", "hidden", "derived"]

# Renderer chrome tokens, shared by the PyVis and Plotly renderers so the
# fallback cannot drift from the primary.
GRAPH_CHROME: Dict[str, str] = {
    "background": "#ffffff",
    "font": "#222222",
    "edge": "#bbbbbb",
    "node_outline": "#333333",
    # A routing edge that participates in a feedback cycle (``in_cycle``): the
    # same red as the "hidden" observability class, reused as the "this is the
    # feedback ring" signal so the finding reads at a glance in both backends.
    "cycle_edge": "#C0392B",
}

# Unicode glyphs matching each node shape, so the legend preserves the
# shape channel of the color+shape dual encoding.
SHAPE_GLYPH: Dict[str, str] = {
    "star": "★",
    "diamond": "◆",
    "dot": "●",
    "square": "■",
    "triangle": "▲",
    "triangleDown": "▼",
    "box": "▬",
    "hexagon": "⬢",
    "ellipse": "⬭",
    "database": "▤",
}


# ---------------------------------------------------------------------------
# Node-type style registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeStyle:
    """Visual style for one node type.

    ``color=None`` means "no type colour of its own": the node is coloured by
    its observability class (Logic's evidence-graph node types work this way).
    ``font_color`` overrides the default dark label colour — needed for shapes
    that draw the label *inside* a dark fill.
    """

    color: Optional[str] = None
    shape: str = "dot"
    size: int = 16
    legend: Optional[str] = None
    font_color: Optional[str] = None


DEFAULT_STYLE = NodeStyle(color="#999999", shape="dot", size=12, legend="Other")

# Union of the three prototypes' node styles.
#
# - Structural types (project/track/clip/device/...) keep the Ableton and
#   REAPER type colours.
# - Logic's evidence-graph types ship with ``color=None``: they are coloured
#   by observability, exactly as the Logic prototype rendered them.
_DEFAULT_NODE_STYLES: Dict[str, NodeStyle] = {
    # -- structural (Ableton / REAPER lineage) --------------------------------
    "project": NodeStyle(color="#F2C14E", shape="star", size=34, legend="Project"),
    "session": NodeStyle(color="#F2C14E", shape="star", size=34, legend="Session"),
    "scene": NodeStyle(color="#9B8ADE", shape="diamond", size=18, legend="Scene"),
    "track": NodeStyle(color="#4EA8DE", shape="dot", size=24, legend="Track"),
    "return_track": NodeStyle(color="#2A9D8F", shape="dot", size=22, legend="Return track"),
    "master_track": NodeStyle(color="#264653", shape="dot", size=28, legend="Master"),
    "clip": NodeStyle(color="#80CED7", shape="square", size=14, legend="Clip"),
    "midi_clip": NodeStyle(color="#F49CBB", shape="square", size=14, legend="MIDI clip"),
    "media_item": NodeStyle(color="#f58518", shape="square", size=16, legend="Media item"),
    "audio_file": NodeStyle(color="#B7E4C7", shape="triangle", size=12, legend="Audio file"),
    "device": NodeStyle(color="#E76F51", shape="box", size=16, legend="Device"),
    "fx": NodeStyle(color="#b279a2", shape="diamond", size=16, legend="FX"),
    # Canonical vocabulary: one type for device/FX/plug-in across dialects.
    "processor": NodeStyle(color="#E76F51", shape="box", size=16, legend="Processor"),
    "unresolved_route": NodeStyle(shape="hexagon", size=14, legend="Unresolved route"),
    "parameter": NodeStyle(color="#CCCCCC", shape="dot", size=8, legend="Parameter"),
    "send": NodeStyle(color="#F4A261", shape="triangleDown", size=12, legend="Send"),
    "bus_or_target": NodeStyle(color="#9d755d", shape="hexagon", size=16, legend="Route / bus"),
    "route": NodeStyle(color="#9d755d", shape="hexagon", size=14, legend="Route"),
    # -- evidence graph (Logic lineage; coloured by observability) ------------
    "audio_evidence": NodeStyle(shape="dot"),
    "mixdown": NodeStyle(shape="square"),
    "reference_track": NodeStyle(shape="triangle"),
    "inferred_track": NodeStyle(shape="dot"),
    "midi_file": NodeStyle(shape="diamond"),
    "midi_track": NodeStyle(shape="diamond"),
    "musicxml_file": NodeStyle(shape="diamond"),
    "musicxml_part": NodeStyle(shape="diamond"),
    "channel_strip_note": NodeStyle(shape="box"),
    "plugin_note": NodeStyle(shape="box"),
    "send_note": NodeStyle(shape="box"),
    "bus_note": NodeStyle(shape="box"),
    # Shapes that draw the label INSIDE the node need a light font on the
    # dark (purple, derived) fills to stay readable.
    "descriptor_set": NodeStyle(shape="ellipse", font_color="#ffffff"),
    "stem_sum_reconciliation": NodeStyle(shape="database", font_color="#ffffff"),
    "reference_comparison": NodeStyle(shape="database", font_color="#ffffff"),
    "hidden_state_marker": NodeStyle(shape="triangleDown"),
    "recommendation": NodeStyle(shape="hexagon"),
}

_node_styles: Dict[str, NodeStyle] = dict(_DEFAULT_NODE_STYLES)


def register_node_style(
    node_type: str,
    *,
    color: Optional[str] = None,
    shape: str = "dot",
    size: int = 16,
    legend: Optional[str] = None,
    font_color: Optional[str] = None,
) -> NodeStyle:
    """Register (or override) the style for a node type.

    Dialects and graph builders call this to teach the renderers about their
    own node vocabulary without touching core tables.
    """

    style = NodeStyle(color=color, shape=shape, size=size, legend=legend, font_color=font_color)
    _node_styles[node_type] = style
    return style


def unregister_node_style(node_type: str) -> None:
    """Remove a registered style; shipped defaults are restored, extras dropped."""

    if node_type in _DEFAULT_NODE_STYLES:
        _node_styles[node_type] = _DEFAULT_NODE_STYLES[node_type]
    else:
        _node_styles.pop(node_type, None)


def get_node_style(node_type: Optional[str]) -> NodeStyle:
    """Style for a node type; the neutral default when the type is unknown."""

    return _node_styles.get(node_type or "", DEFAULT_STYLE)


def registered_node_types() -> List[str]:
    return list(_node_styles)


def node_color(data: dict) -> str:
    """Resolve a node's fill colour.

    A node whose epistemic class *deviates* from plain observation (inferred /
    annotation / hidden / derived) is coloured by that class — the Logic
    affordance, and the signal that matters. Observed nodes keep their type
    colour (the REAPER/Ableton affordance); observed nodes of colourless
    evidence types fall back to the observed colour; grey when nothing is
    known.
    """

    observability = data.get("observability")
    if observability and observability != "observed":
        return OBSERVABILITY_COLORS.get(observability, OBSERVABILITY_COLORS["unknown"])
    style = get_node_style(data.get("type"))
    if style.color:
        return style.color
    if observability:
        return OBSERVABILITY_COLORS.get(observability, OBSERVABILITY_COLORS["unknown"])
    return OBSERVABILITY_COLORS["unknown"]


def node_font_color(data: dict) -> str:
    """Label colour for a node (light on dark inside-label fills)."""

    style = get_node_style(data.get("type"))
    return style.font_color or GRAPH_CHROME["font"]


# ---------------------------------------------------------------------------
# Legends
# ---------------------------------------------------------------------------


def legend_entries() -> List[Tuple[str, str, str]]:
    """(label, color, shape glyph) triples for the node-type legend.

    Only types with their own colour and legend label appear; observability-
    coloured types are covered by :func:`observability_legend` instead.
    """

    entries: List[Tuple[str, str, str]] = []
    for style in _node_styles.values():
        if style.legend and style.color:
            entry = (style.legend, style.color, SHAPE_GLYPH.get(style.shape, "●"))
            if entry not in entries:
                entries.append(entry)
    return entries


def observability_legend() -> List[Tuple[str, str]]:
    """(label, color) pairs for the observability-class legend."""

    return [(key, OBSERVABILITY_COLORS[key]) for key in OBSERVABILITY_ORDER]
