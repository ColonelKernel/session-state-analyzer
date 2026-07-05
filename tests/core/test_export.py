"""Export tests: the two-view bundle, PROV-O block, building blocks, and
the numpy-tolerant serialiser (adapted from the three prototypes' coverage)."""

import json

import networkx as nx
import pytest

from session_explorer.core.export import (
    PROV_OBSERVABILITY_TYPES,
    build_bundle,
    descriptors_export,
    graph_export,
    graph_to_dict,
    hidden_state_json,
    prov_json,
    recommendations_export,
    session_json,
    to_json_bytes,
    to_json_str,
    write_bundle,
)
from session_explorer.core.models import (
    CANONICAL_SCHEMA_VERSION,
    AudioDescriptorSet,
    CanonicalSession,
    HiddenStateMarker,
    NativePayload,
    Processor,
    Recommendation,
    Route,
    Track,
)
from session_explorer.core.provenance import Provenance, annotation


def _session(with_native: bool = True) -> CanonicalSession:
    track = Track(
        id="reaper:track-1",
        name="Drums",
        kind="audio",
        provenance=Provenance(observability="observed", source_artifact="rpp_file"),
        processors=[
            Processor(
                id="reaper:fx-1",
                track_id="reaper:track-1",
                name="ReaEQ",
                provenance=Provenance(observability="observed", source_artifact="rpp_file"),
            ),
            Processor(
                id="reaper:fx-2",
                track_id="reaper:track-1",
                name="Some noted compressor",
                provenance=annotation("from a channel-strip note"),
            ),
        ],
    )
    return CanonicalSession(
        dialect="reaper",
        name="Export Test",
        tracks=[track],
        routes=[Route(id="reaper:route-1", source_track_id="reaper:track-1",
                      target_name="Reverb Bus")],
        descriptors=[AudioDescriptorSet(id="desc-1", file_name="drums.wav",
                                        warnings=["audio backend missing"])],
        hidden_state_markers=[
            HiddenStateMarker(
                id="hidden-1",
                target_id="reaper:track-1",
                hidden_state_type="automation",
                description="Automation not recoverable from the .rpp parse.",
                consequence="Recommendations cannot account for automated moves.",
            )
        ],
        recommendations=[Recommendation(id="rec-1", title="Check reverb send level")],
        warnings=["session-level warning"],
        native=NativePayload(dialect="reaper", model_name="ProjectState",
                             model={"tracks": [{"name": "Drums"}]}) if with_native else None,
    )


def _graph() -> nx.DiGraph:
    g = nx.DiGraph(dialect="reaper", n_tracks=1)
    g.add_node("session", type="session", label="Export Test", observability="observed",
               source_artifact="rpp_file")
    g.add_node("reaper:track-1", type="track", label="Drums", observability="observed",
               source_artifact="rpp_file")
    g.add_node("note-1", type="channel_strip_note", label="Note: Drums",
               observability="annotation")
    g.add_node("hidden-1", type="hidden_state_marker", label="automation",
               observability="hidden")
    g.add_node("rec-1", type="recommendation", label="Check reverb send level",
               observability="derived")
    g.add_edge("session", "reaper:track-1", type="has_track")
    g.add_edge("reaper:track-1", "note-1", type="annotated_by")
    g.add_edge("reaper:track-1", "hidden-1", type="has_hidden_state")
    g.add_edge("note-1", "rec-1", type="supports_recommendation")
    return g


# ---------------------------------------------------------------------------
# The two-view bundle
# ---------------------------------------------------------------------------


def test_unified_bundle_shape():
    bundle = build_bundle(_session(), graph=_graph(), view="unified")
    assert set(bundle.keys()) == {
        "schema_version",
        "session",
        "graph",
        "descriptors",
        "hidden_state_markers",
        "recommendations",
        "prov",
        "warnings",
        "export_metadata",
    }
    assert bundle["schema_version"] == CANONICAL_SCHEMA_VERSION
    assert bundle["session"]["name"] == "Export Test"
    assert bundle["graph"]["nodes"] and bundle["graph"]["edges"]
    assert bundle["graph"]["metadata"]["dialect"] == "reaper"
    assert bundle["export_metadata"]["dialect"] == "reaper"
    assert bundle["export_metadata"]["view"] == "unified"
    assert bundle["export_metadata"]["native_payload_available"] is True
    # Descriptor warnings roll up alongside session warnings.
    assert "session-level warning" in bundle["warnings"]
    assert "audio backend missing" in bundle["warnings"]


def test_unified_bundle_is_default_and_works_without_graph():
    bundle = build_bundle(_session())
    assert bundle["export_metadata"]["view"] == "unified"
    assert bundle["graph"] is None
    assert bundle["export_metadata"]["graph_included"] is False
    # The PROV block still exists, built from the canonical entities.
    assert "sse:reaper:track-1" in bundle["prov"]["entity"]


def test_native_view_returns_verbatim_payload():
    bundle = build_bundle(_session(), view="native")
    assert bundle == {
        "dialect": "reaper",
        "model_name": "ProjectState",
        "model": {"tracks": [{"name": "Drums"}]},
    }


def test_native_view_without_payload_raises_clear_error():
    with pytest.raises(ValueError, match="native"):
        build_bundle(_session(with_native=False), view="native")


def test_both_view_contains_both():
    bundle = build_bundle(_session(), graph=_graph(), view="both")
    assert set(bundle.keys()) == {"unified", "native"}
    assert bundle["unified"]["session"]["dialect"] == "reaper"
    assert bundle["native"]["model_name"] == "ProjectState"


def test_unknown_view_raises():
    with pytest.raises(ValueError, match="view"):
        build_bundle(_session(), view="csv")


# ---------------------------------------------------------------------------
# PROV-O block
# ---------------------------------------------------------------------------


def test_prov_json_from_graph_grounds_observability_classes():
    prov = prov_json(_session(), _graph())
    assert set(prov.keys()) == {"prefix", "agent", "entity", "wasAttributedTo", "relations", "note"}
    entities = prov["entity"]
    assert entities["sse:reaper:track-1"]["prov:type"] == "prov:PrimarySource"
    assert entities["sse:note-1"]["prov:type"] == "sse:UserAssertion"
    assert entities["sse:hidden-1"]["prov:type"] == "sse:HiddenState"
    assert entities["sse:rec-1"]["prov:type"] == "prov:Entity"
    # has_track maps to membership; supports_recommendation to derivation.
    membership = prov["relations"]["prov:hadMember"]
    assert any(r["prov:entity"] == "sse:reaper:track-1" for r in membership)
    derivations = prov["relations"]["prov:wasDerivedFrom"]
    assert any(r["prov:entity"] == "sse:rec-1" for r in derivations)


def test_prov_json_attributes_entities_to_the_right_agents():
    prov = prov_json(_session(), _graph())
    attributions = prov["wasAttributedTo"]
    # Observed entities are attributed to their evidence artifact agent.
    artifact_agent = "sse:artifact:rpp_file"
    assert artifact_agent in prov["agent"]
    assert any(a["prov:entity"] == "sse:reaper:track-1" and a["prov:agent"] == artifact_agent
               for a in attributions)
    # Annotations belong to the producer (both via node class and the
    # annotated_by edge), tool products to the explorer agent.
    assert any(a["prov:entity"] == "sse:note-1" and a["prov:agent"] == "sse:producer"
               for a in attributions)
    assert any(a["prov:entity"] == "sse:hidden-1" and a["prov:agent"] == "sse:explorer"
               for a in attributions)
    # annotated_by never lands in "relations": it becomes an attribution.
    assert not any(r["sse:edge_type"] == "annotated_by"
                   for rel in prov["relations"].values() for r in rel)


def test_prov_json_without_graph_flattens_canonical_entities():
    prov = prov_json(_session())
    entities = prov["entity"]
    # Session, tracks, processors, routes, descriptors, markers, recs.
    assert entities["sse:session"]["sse:node_type"] == "session"
    assert entities["sse:reaper:fx-1"]["prov:type"] == "prov:PrimarySource"
    assert entities["sse:reaper:fx-2"]["prov:type"] == "sse:UserAssertion"
    assert entities["sse:desc-1"]["sse:observability"] == "derived"
    assert entities["sse:hidden-1"]["prov:type"] == "sse:HiddenState"
    assert entities["sse:rec-1"]["sse:node_type"] == "recommendation"
    assert prov["relations"] == {}


def test_prov_observability_types_cover_all_classes():
    assert set(PROV_OBSERVABILITY_TYPES) == {"observed", "inferred", "annotation",
                                             "hidden", "derived"}


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def test_session_json_round_trips_through_json():
    payload = session_json(_session())
    assert json.loads(json.dumps(payload))["dialect"] == "reaper"


def test_graph_export_shape():
    export = graph_export(_graph())
    assert export["schema_version"] == CANONICAL_SCHEMA_VERSION
    graph = export["graph"]
    assert {n["id"] for n in graph["nodes"]} == set(_graph().nodes)
    assert all({"source", "target"} <= set(e) for e in graph["edges"])
    assert graph["metadata"]["n_tracks"] == 1


def test_graph_to_dict_preserves_node_and_edge_data():
    payload = graph_to_dict(_graph())
    by_id = {n["id"]: n for n in payload["nodes"]}
    assert by_id["reaper:track-1"]["observability"] == "observed"
    edge_types = {(e["source"], e["target"]): e["type"] for e in payload["edges"]}
    assert edge_types[("session", "reaper:track-1")] == "has_track"


def test_descriptors_and_recommendations_exports():
    session = _session()
    descriptors = descriptors_export(session.descriptors)
    assert descriptors["schema_version"] == CANONICAL_SCHEMA_VERSION
    assert descriptors["descriptors"][0]["id"] == "desc-1"
    recommendations = recommendations_export(session.recommendations)
    assert recommendations["recommendations"][0]["title"] == "Check reverb send level"


def test_hidden_state_json_is_plain_dicts():
    markers = hidden_state_json(_session())
    assert markers[0]["hidden_state_type"] == "automation"
    json.dumps(markers)  # must be serialisable as-is


# ---------------------------------------------------------------------------
# Serialisation + file writing
# ---------------------------------------------------------------------------


class _FakeNumpyScalar:
    """Mimics a numpy scalar: exposes .item() without importing numpy."""

    def item(self):
        return 0.5


def test_to_json_bytes_tolerates_numpy_scalars_and_sets():
    payload = {"rms": _FakeNumpyScalar(), "tags": {"drums"}}
    data = json.loads(to_json_bytes(payload).decode("utf-8"))
    assert data["rms"] == 0.5
    assert data["tags"] == ["drums"]


def test_to_json_str_stringifies_stragglers():
    class Odd:
        def __repr__(self):
            return "odd-object"

        def __str__(self):
            return "odd-object"

    assert "odd-object" in to_json_str({"x": Odd()})


def test_write_bundle_writes_pretty_json(tmp_path):
    path = write_bundle(_session(), tmp_path / "exports", graph=_graph(), view="both")
    assert path.exists()
    assert path.name == "export-test_both_bundle.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"unified", "native"}
    assert payload["unified"]["export_metadata"]["view"] == "unified"


def test_write_bundle_native_missing_raises_before_writing(tmp_path):
    out_dir = tmp_path / "exports"
    with pytest.raises(ValueError, match="native"):
        write_bundle(_session(with_native=False), out_dir, view="native")
    assert not out_dir.exists()
