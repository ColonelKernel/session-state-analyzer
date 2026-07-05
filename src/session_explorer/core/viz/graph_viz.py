"""Graph visualisation helpers (PyVis primary, Plotly fallback).

The visualisation colour-codes nodes by *observability* so that observed
evidence, inferred state, user annotations and hidden-state markers are
visually distinct — the core interpretability affordance of the tool. Nodes
without an observability class fall back to their node-type colour from the
theme registry.

Both renderers operate on a ``networkx.DiGraph`` whose nodes carry a ``type``
attribute and, optionally, an ``observability`` attribute (plus ``label`` and
any tooltip-worthy data).

Two layouts are offered:

- ``force``: force-directed, with physics frozen once the layout stabilises
  so the graph holds still (important for screen recordings).
- ``layered``: nodes are columned left-to-right by observability class
  (observed → inferred → annotation → hidden → derived), making the
  evidence-to-hidden gradient readable at a glance.

PyVis and Plotly are optional: this module imports without them, and the
renderers raise a clear ``RuntimeError`` when the backend is missing. All of
the visual *logic* (styles, filters, positions, label truncation, node-option
building) is pure and testable without either dependency.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from .theme import (
    GRAPH_CHROME,
    OBSERVABILITY_ORDER,
    get_node_style,
    node_color,
    node_font_color,
)

PYVIS_AVAILABLE = importlib.util.find_spec("pyvis") is not None
PLOTLY_AVAILABLE = importlib.util.find_spec("plotly") is not None

# Sized so a "Track: "-prefixed demo track name still fits untruncated.
MAX_LABEL_CHARS = 28

# Node types that anchor the graph: kept through observability filtering so
# the session/project root never vanishes from view.
ANCHOR_TYPES = frozenset({"session", "project"})

# Injected after the vis.Network is constructed: freeze physics once the
# force layout has stabilised, so the graph does not jiggle on camera.
_FREEZE_PHYSICS_JS = (
    "network.once('stabilizationIterationsDone', function () {"
    " network.setOptions({physics: false}); });"
)
# With physics off (layered layout) there is no stabilisation event to
# trigger vis-network's auto-fit, so fit explicitly once drawn.
_FIT_VIEW_JS = "network.once('afterDrawing', function () { network.fit(); });"
_NETWORK_CTOR = "network = new vis.Network(container, data, options);"


# ---------------------------------------------------------------------------
# Pure display logic (no render dependencies)
# ---------------------------------------------------------------------------


def truncate_label(label: str, max_chars: int = MAX_LABEL_CHARS) -> str:
    """Shorten a node label for display; the full text lives in the tooltip."""

    label = label or ""
    if len(label) <= max_chars:
        return label
    return label[: max_chars - 1].rstrip() + "…"


@dataclass
class GraphFilters:
    """Display filters for the graph.

    ``hidden_types`` hides whole node-type classes (the REAPER prototype's
    show/hide toggles, generalized to the registry world: hiding descriptors
    means ``hidden_types={"descriptor_set"}``, hiding FX means
    ``hidden_types={"fx", "device"}`` and so on).

    ``observability_only`` restricts to a single observability class when set
    (``"observed"`` / ``"inferred"`` / ``"annotation"`` / ``"hidden"`` /
    ``"derived"``); anchor nodes (session/project) always survive.

    ``only_subtree`` restricts to one node's subtree (the REAPER prototype's
    ``only_track``): the node itself, its descendants, and its direct
    neighbours so routing context is not lost.
    """

    hidden_types: Set[str] = field(default_factory=set)
    observability_only: Optional[str] = None
    only_subtree: Optional[str] = None


def filter_graph(graph: nx.DiGraph, filters: Optional[GraphFilters] = None) -> nx.DiGraph:
    """Return a new graph with nodes/edges removed per the display filters."""

    if filters is None:
        filters = GraphFilters()

    subgraph = nx.DiGraph()
    subgraph.graph.update(graph.graph)

    # Restrict to a single node's subtree when requested.
    allowed_nodes = None
    if filters.only_subtree and filters.only_subtree in graph:
        allowed_nodes = {filters.only_subtree}
        allowed_nodes.update(nx.descendants(graph, filters.only_subtree))
        # Include direct neighbours so routing context is not lost.
        allowed_nodes.update(graph.successors(filters.only_subtree))
        allowed_nodes.update(graph.predecessors(filters.only_subtree))

    for node_id, data in graph.nodes(data=True):
        node_type = data.get("type")
        is_anchor = node_type in ANCHOR_TYPES
        if node_type in filters.hidden_types:
            continue
        if (
            filters.observability_only
            and data.get("observability") != filters.observability_only
            and not is_anchor
        ):
            continue
        if allowed_nodes is not None and node_id not in allowed_nodes and not is_anchor:
            continue
        subgraph.add_node(node_id, **data)

    for source, target, data in graph.edges(data=True):
        if source in subgraph and target in subgraph:
            subgraph.add_edge(source, target, **data)

    return subgraph


def layered_positions(
    graph: nx.DiGraph, *, column_gap: int = 260, row_gap: int = 90
) -> Dict[str, Tuple[int, int]]:
    """Fixed (x, y) positions columning nodes by observability class.

    Columns run observed → inferred → annotation → hidden → derived (nodes
    without an observability class column up after them); rows are vertically
    centred within each column.
    """

    columns: Dict[str, List[str]] = {k: [] for k in OBSERVABILITY_ORDER}
    for node_id, data in graph.nodes(data=True):
        key = data.get("observability") or "unknown"
        columns.setdefault(key, []).append(node_id)

    positions: Dict[str, Tuple[int, int]] = {}
    for col_index, key in enumerate(k for k in columns if columns[k]):
        members = columns[key]
        offset = (len(members) - 1) * row_gap / 2
        for row_index, node_id in enumerate(members):
            positions[node_id] = (col_index * column_gap, int(row_index * row_gap - offset))
    return positions


def spring_positions(graph: nx.DiGraph, *, seed: int = 42, k: float = 0.7) -> dict:
    """Deterministic force-directed positions (shared by the Plotly path)."""

    return nx.spring_layout(graph, seed=seed, k=k)


def node_tooltip(node_id: str, data: dict) -> str:
    """Multi-line tooltip listing the node's non-empty attributes."""

    lines = [str(data.get("label", node_id)), f"type: {data.get('type')}"]
    if data.get("observability"):
        lines.append(f"observability: {data['observability']}")
    for key, value in data.items():
        if key in ("label", "type", "observability") or value is None:
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def pyvis_node_options(
    node_id: str,
    data: dict,
    *,
    highlighted: bool = False,
    position: Optional[Tuple[int, int]] = None,
) -> dict:
    """The pyvis ``add_node`` keyword arguments for one node (pure, testable).

    ``highlighted`` enlarges and outlines the node — used to spotlight the
    evidence behind a recommendation.
    """

    style = get_node_style(data.get("type"))
    options: dict = {
        "label": truncate_label(str(data.get("label", node_id))),
        "shape": style.shape,
        "title": node_tooltip(node_id, data),
        # Per-node font dicts: no constructor-level font_color may be used
        # (see build_pyvis_html), so the colour must be carried here.
        "font": {"color": node_font_color(data)},
    }
    color = node_color(data)
    if highlighted:
        options["color"] = {"background": color, "border": "#111111"}
        options["borderWidth"] = 4
        options["size"] = 28
    else:
        options["color"] = color
        options["size"] = style.size
    if position is not None:
        options["x"], options["y"] = position
    return options


# ---------------------------------------------------------------------------
# Renderers (optional backends)
# ---------------------------------------------------------------------------


def build_pyvis_html(
    graph: nx.DiGraph,
    *,
    height: str = "650px",
    layout: str = "force",
    highlight_ids: Optional[List[str]] = None,
    filters: Optional[GraphFilters] = None,
) -> str:
    """Render the session graph to standalone PyVis HTML.

    ``layout`` is ``"force"`` (physics, frozen after stabilisation) or
    ``"layered"`` (fixed columns by observability class). ``highlight_ids``
    enlarges and outlines the given nodes — used to spotlight the evidence
    behind a recommendation. Raises ``RuntimeError`` if PyVis is absent.
    """

    try:
        from pyvis.network import Network
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "pyvis is not installed; install the 'ui' extra "
            "(pip install 'session-state-explorer[ui]') to render interactive HTML."
        ) from exc

    if filters is not None:
        graph = filter_graph(graph, filters)
    highlight = set(highlight_ids or [])

    # No constructor-level font_color: pyvis would silently overwrite every
    # per-node font dict with it (Node.__init__ applies font_color last).
    net = Network(height=height, width="100%", directed=True, bgcolor=GRAPH_CHROME["background"])
    positions: Dict[str, Tuple[int, int]] = {}
    if layout == "layered":
        positions = layered_positions(graph)
        net.toggle_physics(False)
    else:
        net.barnes_hut(gravity=-8000, spring_length=120)

    for node_id, data in graph.nodes(data=True):
        net.add_node(
            node_id,
            **pyvis_node_options(
                node_id,
                data,
                highlighted=node_id in highlight,
                position=positions.get(node_id),
            ),
        )
    for source, target, data in graph.edges(data=True):
        net.add_edge(
            source, target, title=data.get("type", ""), arrows="to", color=GRAPH_CHROME["edge"]
        )

    try:
        html = net.generate_html(notebook=False)
    except TypeError:  # pragma: no cover - older pyvis signatures
        html = net.generate_html()

    if _NETWORK_CTOR in html:
        inject = _FREEZE_PHYSICS_JS if layout == "force" else _FIT_VIEW_JS
        html = html.replace(_NETWORK_CTOR, _NETWORK_CTOR + "\n" + inject)
    return html


def build_plotly_figure(
    graph: nx.DiGraph,
    *,
    layout: str = "force",
    highlight_ids: Optional[List[str]] = None,
    filters: Optional[GraphFilters] = None,
):
    """Render the session graph as a Plotly figure (fallback backend).

    Raises ``RuntimeError`` if Plotly is absent.
    """

    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "plotly is not installed; install the 'ui' extra "
            "(pip install 'session-state-explorer[ui]') to render the fallback figure."
        ) from exc

    if filters is not None:
        graph = filter_graph(graph, filters)
    highlight = set(highlight_ids or [])

    if graph.number_of_nodes() == 0:
        return go.Figure()

    if layout == "layered":
        pos = {nid: (x, -y) for nid, (x, y) in layered_positions(graph).items()}
    else:
        pos = spring_positions(graph)

    edge_x: List[Optional[float]] = []
    edge_y: List[Optional[float]] = []
    for source, target in graph.edges():
        if source in pos and target in pos:
            x0, y0 = pos[source]
            x1, y1 = pos[target]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=0.8, color=GRAPH_CHROME["edge"]), hoverinfo="none",
    )

    node_x, node_y, colors, texts, sizes, line_widths = [], [], [], [], [], []
    for node_id, data in graph.nodes(data=True):
        if node_id not in pos:
            continue
        x, y = pos[node_id]
        node_x.append(x)
        node_y.append(y)
        colors.append(node_color(data))
        texts.append(node_tooltip(node_id, data).replace("\n", "<br>"))
        sizes.append(22 if node_id in highlight else 14)
        line_widths.append(3 if node_id in highlight else 1)
    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers", hoverinfo="text",
        text=texts,
        marker=dict(size=sizes, color=colors, line=dict(width=line_widths, color=GRAPH_CHROME["node_outline"])),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        showlegend=False, hovermode="closest",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=650,
    )
    return fig
