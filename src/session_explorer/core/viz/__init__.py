"""Visualization: shared theme registry + PyVis/Plotly graph renderers.

The render backends (pyvis, plotly) are optional extras; everything except
the two ``build_*`` renderers is pure and dependency-free.
"""

from .graph_viz import (
    ANCHOR_TYPES,
    MAX_LABEL_CHARS,
    PLOTLY_AVAILABLE,
    PYVIS_AVAILABLE,
    GraphFilters,
    build_plotly_figure,
    build_pyvis_html,
    filter_graph,
    layered_positions,
    node_tooltip,
    pyvis_node_options,
    spring_positions,
    truncate_label,
)
from .theme import (
    GRAPH_CHROME,
    OBSERVABILITY_COLORS,
    OBSERVABILITY_ORDER,
    SHAPE_GLYPH,
    DEFAULT_STYLE,
    NodeStyle,
    get_node_style,
    legend_entries,
    node_color,
    node_font_color,
    observability_legend,
    register_node_style,
    registered_node_types,
    unregister_node_style,
)

__all__ = [
    "ANCHOR_TYPES",
    "MAX_LABEL_CHARS",
    "PLOTLY_AVAILABLE",
    "PYVIS_AVAILABLE",
    "GraphFilters",
    "build_plotly_figure",
    "build_pyvis_html",
    "filter_graph",
    "layered_positions",
    "node_tooltip",
    "pyvis_node_options",
    "spring_positions",
    "truncate_label",
    "GRAPH_CHROME",
    "OBSERVABILITY_COLORS",
    "OBSERVABILITY_ORDER",
    "SHAPE_GLYPH",
    "DEFAULT_STYLE",
    "NodeStyle",
    "get_node_style",
    "legend_entries",
    "node_color",
    "node_font_color",
    "observability_legend",
    "register_node_style",
    "registered_node_types",
    "unregister_node_style",
]
