"""P3 gate: snapshot → layered graph over the four frozen bundles, plus a
headless workbench smoke test.

The graph builder is exercised against every real fixture bundle — the same
artifacts the conformance suite freezes — so layer semantics are asserted on
actual adapter output, not synthetic snapshots.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import networkx as nx
import pytest

from canonical_snapshot import ENTITY_TYPE_VALUES
from session_explorer.core.viz import get_node_style
from session_explorer.graph_layers import (
    LAYERS,
    build_graph,
    build_multi,
    get_layer,
)
from session_explorer.loaders.bundle import load_bundle

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "adapters"
# All discovered adapter bundles, incl. logic_real (real captured session).
DAWS = ("ableton", "cubase", "logic", "logic_real", "reaper")

OBSERVABILITY_CLASSES = {"observed", "inferred", "annotation", "hidden"}


def _bundle(daw: str):
    path = FIXTURES / daw
    if not (path / "canonical.snapshot.json").exists():
        pytest.skip(f"no frozen bundle for {daw}")
    return load_bundle(path)


@pytest.fixture(params=DAWS)
def bundle(request):
    return _bundle(request.param)


# ---------------------------------------------------------------------------
# Layer registry
# ---------------------------------------------------------------------------


def test_layer_registry_names():
    assert set(LAYERS) == {"organizational", "signal_flow", "all"}


def test_unknown_layer_is_loud():
    with pytest.raises(KeyError, match="unknown graph layer"):
        get_layer("temporal")


def test_organizational_layer_excludes_signal_rels():
    spec = get_layer("organizational")
    assert not spec.includes_rel("CHANNEL_SENDS_TO")
    assert not spec.includes_rel("CHANNEL_ROUTES_TO")
    assert not spec.includes_rel("CHANNEL_PROCESSED_BY")
    assert spec.includes_rel("CONTAINS")
    assert spec.includes_rel("TRACK_USES_CHANNEL")


def test_media_asset_relevant_only_in_organizational():
    assert get_layer("organizational").entity_is_relevant("MEDIA_ASSET")
    assert not get_layer("signal_flow").entity_is_relevant("MEDIA_ASSET")
    assert get_layer("all").entity_is_relevant("MEDIA_ASSET")


# ---------------------------------------------------------------------------
# build_graph over each of the four real bundles
# ---------------------------------------------------------------------------


def test_all_layer_node_count_equals_entity_count(bundle):
    graph = build_graph(bundle.snapshot, layer="all")
    assert graph.number_of_nodes() == len(bundle.snapshot.entities)
    assert graph.number_of_edges() == len(bundle.snapshot.relationships)


@pytest.mark.parametrize("layer", sorted(LAYERS))
def test_layer_node_membership_rule(bundle, layer):
    """Node count matches the layer rule: in-layer edge OR relevant type."""
    snapshot = bundle.snapshot
    spec = get_layer(layer)
    graph = build_graph(snapshot, layer=layer)

    touched = set()
    for rel in snapshot.relationships:
        if spec.includes_rel(rel.rel_type):
            touched.add(rel.source)
            touched.add(rel.target)
    expected = {
        e.id
        for e in snapshot.entities
        if e.id in touched or spec.entity_is_relevant(e.entity_type)
    }
    assert set(graph.nodes) == expected

    for _, _, data in graph.edges(data=True):
        assert spec.includes_rel(data["type"])


@pytest.mark.parametrize("layer", sorted(LAYERS))
def test_every_node_has_observability_and_uppercase_type(bundle, layer):
    graph = build_graph(bundle.snapshot, layer=layer)
    for node_id, data in graph.nodes(data=True):
        assert data.get("observability") in OBSERVABILITY_CLASSES, node_id
        assert data.get("type") in ENTITY_TYPE_VALUES, node_id
        assert data.get("label"), node_id
        assert isinstance(data.get("availability"), dict), node_id


def test_graph_metadata(bundle):
    snapshot = bundle.snapshot
    graph = build_graph(snapshot, layer="all")
    meta = graph.graph
    assert meta["daw"] == snapshot.source.daw
    assert meta["layer"] == "all"
    assert meta["dialect"] == snapshot.project.split(":")[0]
    assert meta["n_relationships"] == graph.number_of_edges()
    assert sum(meta["entity_counts"].values()) == graph.number_of_nodes()


def test_key_canonical_properties_copied(bundle):
    """Mixer state present on CHANNEL entities lands on the nodes."""
    snapshot = bundle.snapshot
    graph = build_graph(snapshot, layer="all")
    for entity in snapshot.entities:
        for key in ("volume_db", "pan", "mute", "solo"):
            if key in entity.properties:
                assert graph.nodes[entity.id][key] == entity.properties[key]


# ---------------------------------------------------------------------------
# REAPER signal-flow specifics (the routing showcase bundle)
# ---------------------------------------------------------------------------


def _edge_types(graph: nx.DiGraph) -> list[str]:
    return [data["type"] for _, _, data in graph.edges(data=True)]


def test_reaper_signal_flow_edges():
    snapshot = _bundle("reaper").snapshot
    graph = build_graph(snapshot, layer="signal_flow")
    types = _edge_types(graph)
    assert types.count("CHANNEL_SENDS_TO") == 3
    assert types.count("TRACK_USES_CHANNEL") == 9
    assert "REFERENCES_ASSET" not in types
    assert "TRACK_CONTAINS_TEMPORAL_OBJECT" not in types


def test_reaper_organizational_excludes_sends():
    snapshot = _bundle("reaper").snapshot
    graph = build_graph(snapshot, layer="organizational")
    types = _edge_types(graph)
    assert "CHANNEL_SENDS_TO" not in types
    assert "CHANNEL_PROCESSED_BY" not in types
    assert types.count("TRACK_USES_CHANNEL") == 9
    # No PROCESSOR strays into the organizational layer.
    assert all(
        data["type"] != "PROCESSOR" for _, data in graph.nodes(data=True)
    )


def test_logic_observability_classes_survive():
    """The Logic bundle is the INFERRED/ANNOTATED showcase."""
    snapshot = _bundle("logic").snapshot
    graph = build_graph(snapshot, layer="all")
    classes = {data["observability"] for _, data in graph.nodes(data=True)}
    assert "inferred" in classes
    assert "annotation" in classes


# ---------------------------------------------------------------------------
# build_multi: four DAWs, one graph, no invented cross-edges
# ---------------------------------------------------------------------------


def test_build_multi_four_daws():
    bundles = [_bundle(daw) for daw in DAWS]
    snapshots = [b.snapshot for b in bundles]
    combined = build_multi(snapshots, layer="all")

    assert combined.number_of_nodes() == sum(len(s.entities) for s in snapshots)
    assert combined.number_of_edges() == sum(
        len(s.relationships) for s in snapshots
    )
    # Disjoint by construction: build_multi relabels every node with a
    # per-snapshot ordinal prefix (s0:, s1:, …) because dialect namespaces
    # alone cannot separate two sessions of the same DAW (logic vs
    # logic_real share "logic:"). At least one component per snapshot,
    # never a cross-snapshot edge, and the original id survives as the
    # entity_id attribute.
    assert nx.number_weakly_connected_components(combined) >= len(DAWS)
    for source, target in combined.edges():
        assert source.split(":", 1)[0] == target.split(":", 1)[0], (
            f"cross-snapshot edge invented: {source} -> {target}"
        )
    for node, data in combined.nodes(data=True):
        ordinal, raw = node.split(":", 1)
        assert ordinal == f"s{data['snapshot_ordinal']}"
        assert data["entity_id"] == raw

    meta = combined.graph
    assert meta["layer"] == "all"
    assert len(meta["daws"]) == len(DAWS)
    assert len(meta["snapshots"]) == len(DAWS)
    assert sum(meta["entity_counts"].values()) == combined.number_of_nodes()
    assert meta["n_relationships"] == combined.number_of_edges()


def test_build_multi_respects_layer():
    bundles = [_bundle(daw) for daw in DAWS]
    combined = build_multi([b.snapshot for b in bundles], layer="signal_flow")
    spec = get_layer("signal_flow")
    for _, _, data in combined.edges(data=True):
        assert spec.includes_rel(data["type"])
    types = {data["type"] for _, data in combined.nodes(data=True)}
    assert "MEDIA_ASSET" not in types


# ---------------------------------------------------------------------------
# Viz style registration (importing graph_layers taught the theme)
# ---------------------------------------------------------------------------


def test_snapshot_styles_registered():
    channel = get_node_style("CHANNEL")
    assert channel.color == "#2A9D8F"
    assert channel.shape == "hexagon"
    assert channel.size == 20
    assert channel.legend == "Channel"
    assert get_node_style("PROJECT").shape == "star"
    assert get_node_style("ROUTING_ENDPOINT").color is None  # observability-coloured
    assert get_node_style("OBSERVATION").font_color == "#ffffff"


# ---------------------------------------------------------------------------
# Workbench headless smoke (streamlit.testing.v1.AppTest)
# ---------------------------------------------------------------------------

STREAMLIT_AVAILABLE = importlib.util.find_spec("streamlit") is not None
APP_PATH = REPO_ROOT / "src" / "session_explorer" / "workbench" / "app.py"

workbench = pytest.mark.skipif(
    not STREAMLIT_AVAILABLE, reason="streamlit not installed (ui extra)"
)


def _apptest():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP_PATH), default_timeout=120)


def _run_expert(at):
    """P6 two-mode workbench: the app now boots into Guided mode by default.

    These smokes assert the Expert views, so they flip the sidebar mode radio
    (always ``sidebar.radio[0]``) to Expert first; the Expert sidebar's layer
    radio becomes ``sidebar.radio[1]`` and the view radio ``sidebar.radio[2]``.
    """
    at.run()
    at.sidebar.radio[0].set_value("Expert").run()
    return at


@workbench
def test_workbench_boots_with_all_bundles():
    at = _run_expert(_apptest())
    assert not at.exception, [e.value for e in at.exception]
    # All discovered bundles selected by default.
    assert set(at.session_state["bundle_select"]) == set(DAWS)
    # The graph rendered: PyVis HTML was produced (or the Plotly fallback ran
    # — AppTest cannot drive the iframe embed itself, so the page records
    # which backend produced output).
    backend = at.session_state["graph_backend"]
    assert backend in ("pyvis", "plotly")
    if backend == "pyvis":
        assert at.session_state["graph_html_chars"] > 0


@workbench
def test_workbench_layer_switch():
    at = _run_expert(_apptest())
    at.sidebar.radio[1].set_value("signal_flow").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")


@workbench
def test_workbench_native_and_evidence_views():
    at = _run_expert(_apptest())
    at.sidebar.radio[2].set_value("Native").run()
    assert not at.exception, [e.value for e in at.exception]
    at.sidebar.radio[2].set_value("Evidence").run()
    assert not at.exception, [e.value for e in at.exception]
    # The provenance store dataframe is on screen.
    assert len(at.dataframe) >= 1


@workbench
def test_workbench_subset_selection():
    at = _run_expert(_apptest())
    at.sidebar.multiselect[0].set_value(["reaper"]).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")
