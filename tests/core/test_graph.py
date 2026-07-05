"""Unified graph builder tests (superset node/edge types + observability tags)."""

from session_explorer.core.graph import (
    PROJECT_NODE_ID,
    build_session_graph,
    filter_graph,
    graph_to_dict,
)
from session_explorer.core.models import (
    ChannelStripNote,
    EvidenceBundle,
    HiddenStateMarker,
    Recommendation,
    Route,
)
from session_explorer.core.provenance import Provenance

from .conftest import build_demo_session


def test_node_types_and_track_kind_mapping(demo_session):
    graph = build_session_graph(demo_session)
    types = {data["type"] for _, data in graph.nodes(data=True)}
    assert {"project", "track", "return_track", "master_track", "scene",
            "clip", "midi_clip", "audio_file", "processor", "parameter"} <= types
    assert graph.nodes["test:return-1"]["type"] == "return_track"
    assert graph.nodes["test:master"]["type"] == "master_track"


def test_every_node_carries_observability(demo_session):
    graph = build_session_graph(demo_session)
    for node_id, data in graph.nodes(data=True):
        assert data.get("observability") in (
            "observed", "inferred", "annotation", "hidden", "derived",
        ), node_id


def test_inferred_track_is_tagged(demo_session):
    demo_session.tracks[0].provenance = Provenance(observability="inferred", confidence=0.7)
    graph = build_session_graph(demo_session)
    assert graph.nodes["test:track-1"]["observability"] == "inferred"


def test_routes_become_sends_to_edges(demo_session):
    graph = build_session_graph(demo_session)
    edge = graph.get_edge_data("test:track-1", "test:return-1")
    assert edge["type"] == "sends_to"
    assert edge["volume_db"] == -9.0


def test_unresolved_route_kept_visible(demo_session):
    demo_session.routes.append(
        Route(
            id="test:route-2",
            source_track_id=None,
            source_name="track index 9",
            target_track_id="test:return-1",
            route_type="unresolved",
        )
    )
    graph = build_session_graph(demo_session)
    assert graph.nodes["test:route-2"]["type"] == "unresolved_route"
    assert graph.nodes["test:route-2"]["observability"] == "hidden"
    assert graph.get_edge_data("test:route-2", "test:return-1")["type"] == "has_unresolved_route"


def test_tracks_route_to_master(demo_session):
    graph = build_session_graph(demo_session)
    assert graph.get_edge_data("test:track-1", "test:master")["type"] == "routes_to_master"
    assert graph.get_edge_data("test:return-1", "test:master")["type"] == "routes_to_master"
    assert not graph.has_edge("test:master", "test:master")


def test_evidence_and_derived_layers(demo_session):
    demo_session.evidence = EvidenceBundle(
        channel_strip_notes=[
            ChannelStripNote(
                id="note-1", track_name="Lead Vox", plugins=["DeEsser 2"], bus="Bus 1"
            )
        ]
    )
    demo_session.hidden_state_markers = [
        HiddenStateMarker(
            id="hidden-1",
            target_id="test:track-1",
            hidden_state_type="hidden_automation",
            description="d",
            consequence="c",
        )
    ]
    demo_session.recommendations = [
        Recommendation(id="rec-1", title="T", related_node_ids=["test:track-1"])
    ]
    graph = build_session_graph(demo_session)
    assert graph.nodes["note-1"]["observability"] == "annotation"
    assert graph.get_edge_data("note-1", "test:track-1")["type"] == "annotated_by"
    assert graph.nodes["note-1:plugin:DeEsser 2"]["type"] == "plugin_note"
    assert graph.nodes["hidden-1"]["observability"] == "hidden"
    assert graph.get_edge_data("test:track-1", "hidden-1")["type"] == "has_hidden_state"
    assert graph.get_edge_data("test:track-1", "rec-1")["type"] == "supports_recommendation"


def test_metadata_counts(demo_session):
    graph = build_session_graph(demo_session)
    meta = graph.graph
    assert meta["n_tracks"] == 2
    assert meta["n_return_tracks"] == 1
    assert meta["n_clips"] == 2
    assert meta["n_processors"] == 5
    assert meta["n_routes"] == 1
    assert meta["dialect"] == "test"


def test_graph_to_dict_shape(demo_session):
    payload = graph_to_dict(build_session_graph(demo_session))
    assert set(payload) == {"nodes", "edges", "metadata"}
    node = next(n for n in payload["nodes"] if n["id"] == PROJECT_NODE_ID)
    assert node["type"] == "project"
    assert all("source" in e and "target" in e and "type" in e for e in payload["edges"])


def test_filter_graph_by_type_and_observability(demo_session):
    demo_session.hidden_state_markers = [
        HiddenStateMarker(
            id="hidden-1", target_id="test:track-1",
            hidden_state_type="x", description="d", consequence="c",
        )
    ]
    graph = build_session_graph(demo_session)
    no_clips = filter_graph(graph, hidden_types={"clip", "midi_clip"})
    assert not any(d["type"] in ("clip", "midi_clip") for _, d in no_clips.nodes(data=True))
    observed_only = filter_graph(graph, observability={"observed"})
    assert not observed_only.has_node("hidden-1")
    one_track = filter_graph(graph, only_track_id="test:track-1")
    assert one_track.has_node("test:track-1")
    assert not one_track.has_node("test:track-2")
    assert one_track.has_node("test:master")  # context preserved
