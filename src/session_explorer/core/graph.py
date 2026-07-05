"""Build an interpretable directed graph from a canonical session.

One builder for every dialect: the superset of the three prototypes' node and
edge vocabularies, with the Logic prototype's observability tag on every node.

Node types (state graph):
    project, scene, track, return_track, master_track, clip, midi_clip,
    audio_file, processor, parameter, unresolved_route

Node types (evidence graph, when ``session.evidence`` is present):
    audio_evidence, mixdown, reference_track, midi_file, midi_track,
    musicxml_file, musicxml_part, channel_strip_note, plugin_note, send_note,
    bus_note, stem_sum_reconciliation, reference_comparison

Node types (derived layers):
    descriptor_set, hidden_state_marker, recommendation

Edge types:
    contains_scene, contains_track, has_return, has_master, contains_clip,
    clip_in_scene, uses_audio_file, has_processor, has_parameter, sends_to,
    has_unresolved_route, routes_to_master, group_contains, contains_audio,
    infers_track, has_descriptor, annotated_by, mentions_plugin,
    mentions_send, mentions_bus, compared_to_reference,
    part_of_reconciliation, has_hidden_state, supports_recommendation
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

import networkx as nx

from .models import CanonicalSession, Processor, Track

PROJECT_NODE_ID = "project"

STATE_NODE_TYPES = [
    "project",
    "scene",
    "track",
    "return_track",
    "master_track",
    "clip",
    "midi_clip",
    "audio_file",
    "processor",
    "parameter",
    "unresolved_route",
]

EVIDENCE_NODE_TYPES = [
    "audio_evidence",
    "mixdown",
    "reference_track",
    "midi_file",
    "midi_track",
    "musicxml_file",
    "musicxml_part",
    "channel_strip_note",
    "plugin_note",
    "send_note",
    "bus_note",
    "stem_sum_reconciliation",
    "reference_comparison",
]

DERIVED_NODE_TYPES = ["descriptor_set", "hidden_state_marker", "recommendation"]

NODE_TYPES = STATE_NODE_TYPES + EVIDENCE_NODE_TYPES + DERIVED_NODE_TYPES


def _track_node_type(track: Track) -> str:
    if track.kind == "return":
        return "return_track"
    if track.kind == "master":
        return "master_track"
    return "track"


def _observability(entity) -> str:
    provenance = getattr(entity, "provenance", None)
    if provenance is None:
        return "observed"
    return provenance.observability


def _add_processor_nodes(
    graph: nx.DiGraph, owner_node_id: str, processors: Iterable[Processor]
) -> None:
    for proc in processors:
        graph.add_node(
            proc.id,
            label=proc.name,
            type="processor",
            family=proc.family,
            processor_kind=proc.kind,
            enabled=proc.enabled,
            offline=proc.offline,
            chain=proc.chain,
            owner_id=owner_node_id,
            observability=_observability(proc),
        )
        graph.add_edge(owner_node_id, proc.id, type="has_processor")
        for param in proc.parameters:
            graph.add_node(
                param.id,
                label=param.name,
                type="parameter",
                value=param.value,
                unit=param.unit,
                is_automated=param.is_automated,
                observability=_observability(proc),
            )
            graph.add_edge(proc.id, param.id, type="has_parameter")


def build_session_graph(session: CanonicalSession) -> nx.DiGraph:
    """Convert a CanonicalSession into a typed, observability-tagged digraph."""
    graph = nx.DiGraph()

    graph.add_node(
        PROJECT_NODE_ID,
        label=session.name,
        type="project",
        dialect=session.dialect,
        tempo=session.tempo,
        time_signature=session.time_signature,
        observability="observed",
    )

    # Scenes -----------------------------------------------------------------
    for scene in session.scenes:
        graph.add_node(
            scene.id,
            label=scene.name or f"Scene {scene.index + 1}",
            type="scene",
            index=scene.index,
            observability=_observability(scene),
        )
        graph.add_edge(PROJECT_NODE_ID, scene.id, type="contains_scene")

    # Tracks (all kinds; return/master keep their own node types) ------------
    master_tracks = session.tracks_of_kind("master")
    master_id = master_tracks[0].id if master_tracks else None

    for track in session.tracks:
        node_type = _track_node_type(track)
        edge_type = {
            "return_track": "has_return",
            "master_track": "has_master",
        }.get(node_type, "contains_track")
        graph.add_node(
            track.id,
            label=track.name or f"Track {track.index + 1}",
            type=node_type,
            kind=track.kind,
            role=track.role,
            index=track.index,
            volume_db=track.volume_db,
            pan=track.pan,
            mute=track.mute,
            solo=track.solo,
            track_color=track.color,
            confidence=track.confidence,
            observability=_observability(track),
        )
        graph.add_edge(PROJECT_NODE_ID, track.id, type=edge_type)

        if track.group_id:
            graph.add_edge(track.group_id, track.id, type="group_contains")

        if master_id and track.kind not in ("master",):
            graph.add_edge(track.id, master_id, type="routes_to_master")

        # Clips ---------------------------------------------------------------
        for clip in track.clips:
            node_type_clip = "midi_clip" if clip.clip_type == "midi" else "clip"
            graph.add_node(
                clip.id,
                label=clip.name or clip.id,
                type=node_type_clip,
                clip_type=clip.clip_type,
                length_beats=clip.length_beats,
                position_seconds=clip.position_seconds,
                length_seconds=clip.length_seconds,
                warp_enabled=clip.warp_enabled,
                midi_note_count=clip.midi_note_count,
                observability=_observability(clip),
            )
            graph.add_edge(track.id, clip.id, type="contains_clip")
            if clip.scene_id and graph.has_node(clip.scene_id):
                graph.add_edge(clip.id, clip.scene_id, type="clip_in_scene")
            if clip.audio_file:
                file_node_id = f"file:{clip.audio_file}"
                if not graph.has_node(file_node_id):
                    graph.add_node(
                        file_node_id,
                        label=clip.audio_file.replace("\\", "/").split("/")[-1],
                        type="audio_file",
                        path=clip.audio_file,
                        observability="observed",
                    )
                graph.add_edge(clip.id, file_node_id, type="uses_audio_file")

        # Processors ------------------------------------------------------------
        _add_processor_nodes(graph, track.id, track.processors)

    # Routes -------------------------------------------------------------------
    for route in session.routes:
        attrs = {
            "route_type": route.route_type,
            "volume_db": route.volume_db,
            "pan": route.pan,
            "mute": route.mute,
            "enabled": route.enabled,
            "send_mode": route.send_mode,
        }
        if (
            route.source_track_id
            and route.target_track_id
            and graph.has_node(route.source_track_id)
            and graph.has_node(route.target_track_id)
        ):
            graph.add_edge(
                route.source_track_id, route.target_track_id, type="sends_to", **attrs
            )
        elif route.target_track_id and graph.has_node(route.target_track_id):
            # Target known, source not confidently resolvable: keep the gap
            # visible as an explicit node instead of dropping the route.
            graph.add_node(
                route.id,
                label=route.source_name or "Unresolved source",
                type="unresolved_route",
                observability="hidden",
            )
            graph.add_edge(
                route.id, route.target_track_id, type="has_unresolved_route", **attrs
            )

    # Evidence -------------------------------------------------------------------
    if session.evidence is not None:
        _add_evidence_nodes(graph, session)

    # Derived layers ---------------------------------------------------------------
    for descriptor in session.descriptors:
        node_id = descriptor.id or descriptor.node_id
        if not node_id:
            continue
        graph.add_node(
            node_id,
            label=descriptor.file_name or descriptor.file_path or node_id,
            type="descriptor_set",
            available=descriptor.available,
            observability="derived",
        )
        anchor = descriptor.source_id or descriptor.node_id
        if anchor and anchor != node_id and graph.has_node(anchor):
            graph.add_edge(anchor, node_id, type="has_descriptor")

    for marker in session.hidden_state_markers:
        graph.add_node(
            marker.id,
            label=marker.hidden_state_type,
            type="hidden_state_marker",
            observability="hidden",
        )
        target = marker.target_id if graph.has_node(marker.target_id) else PROJECT_NODE_ID
        graph.add_edge(target, marker.id, type="has_hidden_state")

    for rec in session.recommendations:
        graph.add_node(
            rec.id,
            label=rec.title,
            type="recommendation",
            severity=rec.severity,
            confidence=rec.confidence,
            observability="derived",
        )
        for related in rec.related_node_ids:
            if graph.has_node(related):
                graph.add_edge(related, rec.id, type="supports_recommendation")

    graph.graph.update(compute_graph_metadata(graph, session))
    return graph


def _add_evidence_nodes(graph: nx.DiGraph, session: CanonicalSession) -> None:
    evidence = session.evidence
    assert evidence is not None

    tracks_by_audio_id = {
        track.extras.get("source_audio_id"): track
        for track in session.tracks
        if track.extras.get("source_audio_id")
    }

    for audio in evidence.audio_files:
        node_type = "mixdown" if audio.is_mixdown else (
            "reference_track" if audio.is_reference else "audio_evidence"
        )
        graph.add_node(
            audio.id,
            label=audio.file_name,
            type=node_type,
            inferred_role=audio.inferred_role,
            confidence=audio.confidence,
            observability="observed",
        )
        graph.add_edge(PROJECT_NODE_ID, audio.id, type="contains_audio")
        linked_track = tracks_by_audio_id.get(audio.id)
        if linked_track is not None and graph.has_node(linked_track.id):
            graph.add_edge(audio.id, linked_track.id, type="infers_track")

    if evidence.midi_evidence is not None:
        midi = evidence.midi_evidence
        graph.add_node(
            midi.id, label=midi.file_name, type="midi_file", observability="observed"
        )
        graph.add_edge(PROJECT_NODE_ID, midi.id, type="contains_audio")
        for name in midi.track_names:
            node_id = f"{midi.id}:track:{name}"
            graph.add_node(node_id, label=name, type="midi_track", observability="observed")
            graph.add_edge(midi.id, node_id, type="infers_track")

    if evidence.musicxml_evidence is not None:
        xml = evidence.musicxml_evidence
        graph.add_node(
            xml.id, label=xml.file_name, type="musicxml_file", observability="observed"
        )
        graph.add_edge(PROJECT_NODE_ID, xml.id, type="contains_audio")
        for name in xml.part_names:
            node_id = f"{xml.id}:part:{name}"
            graph.add_node(node_id, label=name, type="musicxml_part", observability="observed")
            graph.add_edge(xml.id, node_id, type="infers_track")

    for note in evidence.channel_strip_notes:
        graph.add_node(
            note.id,
            label=f"Note: {note.track_name}",
            type="channel_strip_note",
            observability="annotation",
        )
        target = next(
            (t for t in session.tracks if (t.name or "").lower() == note.track_name.lower()),
            None,
        )
        if target is not None:
            graph.add_edge(note.id, target.id, type="annotated_by")
        for plugin in note.plugins:
            node_id = f"{note.id}:plugin:{plugin}"
            graph.add_node(node_id, label=plugin, type="plugin_note", observability="annotation")
            graph.add_edge(note.id, node_id, type="mentions_plugin")
        for send in note.sends:
            node_id = f"{note.id}:send:{send}"
            graph.add_node(node_id, label=send, type="send_note", observability="annotation")
            graph.add_edge(note.id, node_id, type="mentions_send")
        if note.bus:
            node_id = f"{note.id}:bus:{note.bus}"
            graph.add_node(node_id, label=note.bus, type="bus_note", observability="annotation")
            graph.add_edge(note.id, node_id, type="mentions_bus")

    recon = evidence.stem_sum_reconciliation
    if recon is not None:
        graph.add_node(
            recon.id,
            label="Stem-sum reconciliation",
            type="stem_sum_reconciliation",
            residual_db=recon.residual_db,
            observability="derived",
        )
        for stem_id in recon.stem_audio_ids + [recon.mixdown_audio_id]:
            if graph.has_node(stem_id):
                graph.add_edge(stem_id, recon.id, type="part_of_reconciliation")

    for comparison in evidence.reference_comparisons:
        graph.add_node(
            comparison.id,
            label="Reference comparison",
            type="reference_comparison",
            observability="derived",
        )
        for anchor in (comparison.mixdown_audio_id, comparison.reference_id):
            if graph.has_node(anchor):
                graph.add_edge(anchor, comparison.id, type="compared_to_reference")


def compute_graph_metadata(
    graph: nx.DiGraph, session: Optional[CanonicalSession] = None
) -> dict[str, Any]:
    """Compute graph-level summary metadata."""

    def _count(*node_types: str) -> int:
        return sum(
            1 for _, data in graph.nodes(data=True) if data.get("type") in node_types
        )

    metadata = {
        "dialect": session.dialect if session is not None else None,
        "n_tracks": _count("track"),
        "n_return_tracks": _count("return_track"),
        "n_clips": _count("clip", "midi_clip"),
        "n_processors": _count("processor"),
        "n_parameters": _count("parameter"),
        "n_routes": sum(
            1 for _, _, data in graph.edges(data=True) if data.get("type") == "sends_to"
        ),
        "n_unresolved": _count("unresolved_route"),
        "n_hidden_state_markers": _count("hidden_state_marker"),
        "graph_density": round(nx.density(graph), 5) if graph.number_of_nodes() > 1 else 0.0,
    }
    if session is not None:
        metadata["n_warnings"] = len(session.warnings)
    return metadata


def graph_to_dict(graph: nx.DiGraph) -> dict[str, Any]:
    """Serialize the graph to a JSON-friendly dict of nodes, edges, metadata."""
    nodes = []
    for node_id, data in graph.nodes(data=True):
        node = {"id": node_id, "label": data.get("label", node_id), "type": data.get("type")}
        node.update(
            {k: v for k, v in data.items() if k not in ("label", "type") and v is not None}
        )
        nodes.append(node)

    edges = []
    for source, target, data in graph.edges(data=True):
        edge = {"source": source, "target": target, "type": data.get("type")}
        edge.update({k: v for k, v in data.items() if k != "type" and v is not None})
        edges.append(edge)

    return {"nodes": nodes, "edges": edges, "metadata": dict(graph.graph)}


def filter_graph(
    graph: nx.DiGraph,
    hidden_types: Optional[set[str]] = None,
    observability: Optional[set[str]] = None,
    only_track_id: Optional[str] = None,
) -> nx.DiGraph:
    """Return a filtered copy of the graph for display purposes.

    ``hidden_types`` removes node types; ``observability`` keeps only nodes
    whose tag is in the set; ``only_track_id`` restricts to one track and its
    reachable subgraph plus project/master context.
    """
    hidden_types = hidden_types or set()

    def _keep(data: dict) -> bool:
        if data.get("type") in hidden_types:
            return False
        if observability is not None and data.get("observability") not in observability:
            return False
        return True

    keep_nodes = [n for n, data in graph.nodes(data=True) if _keep(data)]
    subgraph = graph.subgraph(keep_nodes).copy()

    if only_track_id and subgraph.has_node(only_track_id):
        reachable = nx.descendants(subgraph, only_track_id) | {only_track_id}
        context = {
            node_id
            for node_id, data in subgraph.nodes(data=True)
            if data.get("type") in ("project", "master_track")
        }
        subgraph = subgraph.subgraph(reachable | context).copy()

    return subgraph
