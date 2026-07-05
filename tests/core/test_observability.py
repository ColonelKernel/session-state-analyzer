"""Observation-model framework tests (Phase 0 gate)."""

from session_explorer.core import observability as obs


def test_all_known_dialects_have_matrices():
    for dialect in ("logic", "reaper", "ableton", "cubase"):
        assert obs.artifact_types(dialect), dialect


def test_logic_matrix_preserves_prototype_semantics():
    exported = obs.observation_for("logic", "exported_audio")
    assert exported["reveals"] == ["audio_content"]
    assert "plugin_chain" in exported["hides"]
    note = obs.observation_for("logic", "channel_strip_note")
    assert "plugin_chain" in note["asserts"]


def test_reaper_rpp_hides_plugin_parameters_but_reveals_chain():
    rpp = obs.observation_for("reaper", "rpp_file")
    assert "plugin_chain" in rpp["reveals"]
    assert "plugin_parameters" in rpp["hides"]
    assert "automation" in rpp["hides"]


def test_ableton_extension_hides_mixer_state_and_automation():
    ext = obs.observation_for("ableton", "extension_json")
    assert "plugin_chain" in ext["reveals"]
    assert "mixer_state" in ext["hides"]
    assert "automation" in ext["hides"]


def test_unknown_lookups_are_empty_not_errors():
    assert obs.observation_for("nope", "nothing") == {}
    assert obs.hidden_fields("nope", "nothing") == []


def test_note_annotation_lifts_hidden_fields():
    class Note:
        plugins = ["ReaComp"]
        sends = []
        bus = "Bus 3"

    annotated = obs.annotated_fields_from_note(Note())
    assert annotated == ["plugin_chain", "bus_routing"]
    remaining = obs.hidden_fields_for_track(annotated)
    assert "plugin_chain" not in remaining
    assert "sends" in remaining


def test_observation_fields_are_known():
    for dialect, artifacts in obs.OBSERVATION_MODEL.items():
        for artifact, mapping in artifacts.items():
            for kind in ("reveals", "constrains", "asserts", "hides"):
                for field in mapping.get(kind, []):
                    assert field in obs.SESSION_STATE_FIELDS, (dialect, artifact, field)
