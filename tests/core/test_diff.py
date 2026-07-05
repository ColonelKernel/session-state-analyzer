"""Canonical session diff tests (adapted from the Ableton prototype's suite)."""

from session_explorer.core.diff import diff_sessions
from session_explorer.core.models import Route, Track

from .conftest import build_demo_session, make_processor


def test_no_changes(demo_session):
    result = diff_sessions(demo_session, build_demo_session())
    assert result["tempo_change"] is None
    assert result["tracks_added"] == []
    assert result["tracks_removed"] == []
    assert result["track_changes"] == []
    assert result["narrative"] == ["No structural differences detected."]


def test_tempo_change(demo_session):
    revised = build_demo_session(tempo=128.0)
    result = diff_sessions(demo_session, revised)
    assert result["tempo_change"] == {"base": 120.0, "revised": 128.0}
    assert any("Tempo changed" in line for line in result["narrative"])


def test_track_added_and_removed(demo_session):
    revised = build_demo_session()
    revised.tracks.append(
        Track(id="test:track-9", index=9, name="Pad", kind="audio", role="Keys")
    )
    revised.tracks = [t for t in revised.tracks if t.name != "Drums"]
    result = diff_sessions(demo_session, revised)
    assert result["tracks_added"] == ["Pad"]
    assert result["tracks_removed"] == ["Drums"]


def test_processor_and_route_changes(demo_session):
    revised = build_demo_session()
    vocal = revised.track_by_id("test:track-1")
    vocal.processors.append(
        make_processor("test:fx-9", "test:track-1", "DeEsser 2", "Dynamics", index=2)
    )
    revised.routes.append(
        Route(
            id="test:route-9",
            source_track_id="test:track-2",
            target_track_id="test:return-1",
            route_type="send",
        )
    )
    result = diff_sessions(demo_session, revised)
    changes = {c["track"]: c for c in result["track_changes"]}
    assert changes["Lead Vox"]["processors_added"] == ["DeEsser 2"]
    assert changes["Drums"]["routes_added"] == ["Reverb Return"]


def test_muted_route_not_counted(demo_session):
    revised = build_demo_session()
    revised.routes.append(
        Route(
            id="test:route-9",
            source_track_id="test:track-2",
            target_track_id="test:return-1",
            mute=True,
        )
    )
    result = diff_sessions(demo_session, revised)
    assert result["track_changes"] == []


def test_parameter_change_detected(demo_session):
    revised = build_demo_session()
    comp = revised.track_by_id("test:track-1").processors[1]
    comp.parameters[0].value = -24.0
    result = diff_sessions(demo_session, revised)
    assert result["parameter_changes"] == [
        {
            "owner": "Lead Vox",
            "processor": "Compressor",
            "parameter": "Threshold",
            "base": -18.0,
            "revised": -24.0,
            "unit": "dB",
        }
    ]
    assert any("Threshold" in line for line in result["narrative"])


def test_master_chain_change(demo_session):
    revised = build_demo_session()
    master = revised.tracks_of_kind("master")[0]
    master.processors.append(
        make_processor("test:fx-9", "test:master", "Glue Compressor", "Dynamics", index=1)
    )
    result = diff_sessions(demo_session, revised)
    assert result["master_processors_added"] == ["Glue Compressor"]


def test_return_track_changes(demo_session):
    revised = build_demo_session()
    revised.tracks.append(
        Track(id="test:return-2", index=1, name="Delay Return", kind="return", role="Bus")
    )
    result = diff_sessions(demo_session, revised)
    assert result["returns_added"] == ["Delay Return"]


def test_cross_dialect_diff_adds_caveat(demo_session):
    other = build_demo_session(dialect="other")
    result = diff_sessions(demo_session, other)
    assert result["base_dialect"] == "test"
    assert result["revised_dialect"] == "other"
    assert any("Cross-dialect" in c for c in result["caveats"])


def test_graph_stats_present(demo_session):
    result = diff_sessions(demo_session, build_demo_session())
    stats = result["graph_stats"]
    assert stats["base_nodes"] == stats["revised_nodes"] > 0
