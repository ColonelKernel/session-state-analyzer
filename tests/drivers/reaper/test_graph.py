"""Tests for canonical graph construction from parsed REAPER sessions.

Adapted from the prototype's ``test_graph_builder.py``: the same ``.rpp``
fixtures now flow through ``mapper.to_canonical`` into
``core.graph.build_session_graph``. Node vocabulary is canonical — media
items are ``clip`` nodes, FX are ``processor`` nodes, and unresolved sends
appear as ``unresolved_route`` nodes — but the semantic assertions (counts,
send resolution and direction, per-send edge attributes, record-chain FX
presence) are preserved.
"""

from __future__ import annotations

from session_explorer.core.graph import (
    PROJECT_NODE_ID,
    build_session_graph,
    graph_to_dict,
)
from session_explorer.drivers.reaper.mapper import to_canonical
from session_explorer.drivers.reaper.rpp_parser import parse_rpp

RPP = """<REAPER_PROJECT 0.1 "x" 0
  TEMPO 120 4 4
  <TRACK
    NAME "Lead Vox"
    <ITEM
      NAME "take"
      <SOURCE WAVE
        FILE "audio/vox.wav"
      >
    >
    <FXCHAIN
      BYPASS 0 0 0
      <VST "VST: ReaEQ (Cockos)" reaeq.dll 0 "" 0
      >
    >
  >
  <TRACK
    NAME "Drum Bus"
    AUXRECV 0 0 1 0 0 0 0
  >
>
"""


def _graph(rpp: str = RPP):
    return build_session_graph(to_canonical(parse_rpp(rpp)))


def _types(graph):
    return {data["type"] for _, data in graph.nodes(data=True)}


def test_project_node_exists():
    graph = _graph()
    assert PROJECT_NODE_ID in graph
    assert graph.nodes[PROJECT_NODE_ID]["type"] == "project"


def test_track_nodes_exist():
    graph = _graph()
    track_nodes = [n for n, d in graph.nodes(data=True) if d["type"] == "track"]
    assert len(track_nodes) == 2
    # Canonical node ids are namespaced.
    assert all(n.startswith("reaper:") for n in track_nodes)


def test_clip_and_audio_nodes_exist():
    graph = _graph()
    types = _types(graph)
    assert "clip" in types
    assert "audio_file" in types


def test_processor_nodes_exist():
    graph = _graph()
    fx_nodes = [n for n, d in graph.nodes(data=True) if d["type"] == "processor"]
    assert len(fx_nodes) == 1
    assert graph.nodes[fx_nodes[0]]["family"] == "EQ"


def test_expected_edges_exist():
    graph = _graph()
    edge_types = {data["type"] for _, _, data in graph.edges(data=True)}
    assert "contains_track" in edge_types
    assert "contains_clip" in edge_types
    assert "uses_audio_file" in edge_types
    assert "has_processor" in edge_types
    assert "sends_to" in edge_types


def test_graph_metadata_present():
    graph = _graph()
    meta = graph.graph
    assert meta["n_tracks"] == 2
    assert meta["n_processors"] == 1
    assert meta["n_clips"] == 1
    assert meta["n_routes"] == 1
    assert "graph_density" in meta


def test_unresolved_route_becomes_explicit_node():
    rpp = """<REAPER_PROJECT 0.1 "x" 0
  <TRACK
    NAME "Bus"
    AUXRECV 42 0 1 0 0 0 0
  >
>
"""
    graph = _graph(rpp)
    phantom_nodes = [
        n for n, d in graph.nodes(data=True) if d["type"] == "unresolved_route"
    ]
    assert len(phantom_nodes) == 1
    assert graph.graph["n_unresolved"] == 1
    unresolved = [
        (u, v, d)
        for u, v, d in graph.edges(data=True)
        if d["type"] == "has_unresolved_route"
    ]
    assert len(unresolved) == 1
    # Direction matches signal flow (phantom source -> receiving track) and the
    # edge carries the same per-send attributes as resolved sends_to edges.
    phantom, receiver, data = unresolved[0]
    assert phantom == phantom_nodes[0]
    assert graph.nodes[receiver]["type"] == "track"
    assert data["send_mode"] == 0
    assert data["volume_db"] == 0.0


def test_record_chain_fx_present_in_graph():
    rpp = """<REAPER_PROJECT 0.1 "x" 0
  <TRACK
    NAME "Vox"
    <FXCHAIN_REC
      BYPASS 0 0 0
      <VST "VST: ReaGate (Cockos)" reagate.dll 0 "" 0
      >
    >
  >
>
"""
    graph = _graph(rpp)
    rec_fx = [
        n
        for n, d in graph.nodes(data=True)
        if d["type"] == "processor" and d.get("chain") == "rec"
    ]
    assert len(rec_fx) == 1


def test_graph_to_dict_roundtrips_structure():
    payload = graph_to_dict(_graph())
    assert {"nodes", "edges", "metadata"} <= set(payload)
    assert all("id" in node for node in payload["nodes"])
    assert all({"source", "target", "type"} <= set(edge) for edge in payload["edges"])
