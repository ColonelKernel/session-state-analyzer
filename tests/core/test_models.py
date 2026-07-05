"""Canonical schema unit tests (Phase 0 gate)."""

from session_explorer.core.models import (
    CANONICAL_SCHEMA_VERSION,
    AudioDescriptorSet,
    CanonicalSession,
    ChannelStripNote,
    Clip,
    EvidenceBundle,
    HiddenStateMarker,
    NativePayload,
    Processor,
    Recommendation,
    Route,
    Track,
    to_dict,
)
from session_explorer.core.provenance import Provenance, annotation, inferred


def _session() -> CanonicalSession:
    track = Track(
        id="reaper:track-1",
        index=0,
        name="Lead Vox",
        kind="audio",
        role="Vocal",
        field_provenance={"role": inferred("keyword match on 'vox'", confidence=0.75)},
        processors=[
            Processor(
                id="reaper:fx-1",
                track_id="reaper:track-1",
                name="ReaComp",
                kind="VST",
                family="Dynamics",
                enabled=True,
                extras={"offline": False, "chain": "main"},
                raw_source="<VST ...>",
            )
        ],
        clips=[
            Clip(
                id="reaper:item-1",
                track_id="reaper:track-1",
                name="vox take 3",
                clip_type="audio",
                position_seconds=12.5,
                length_seconds=30.0,
            )
        ],
        extras={"pan_law": -3.0, "solo_defeat": False},
    )
    return CanonicalSession(
        dialect="reaper",
        name="Test Session",
        tempo=120.0,
        time_signature="4/4",
        tracks=[track],
        routes=[
            Route(
                id="reaper:route-1",
                source_track_id="reaper:track-1",
                target_track_id="reaper:track-2",
                route_type="send",
                volume=1.0,
                volume_db=0.0,
            )
        ],
        hidden_state_markers=[
            HiddenStateMarker(
                id="hidden-1",
                target_id="reaper:track-1",
                hidden_state_type="hidden_plugin_parameters",
                description="Plug-in-private parameter state is not decoded from the .rpp.",
                consequence="Chain identity and order are known; settings are not.",
            )
        ],
        native=NativePayload(
            dialect="reaper", model_name="ProjectState", model={"tracks": []}
        ),
    )


def test_session_round_trips_through_model_dump():
    session = _session()
    payload = session.model_dump()
    restored = CanonicalSession.model_validate(payload)
    assert restored == session
    assert restored.schema_version == CANONICAL_SCHEMA_VERSION


def test_time_domains_are_independent():
    clip = _session().tracks[0].clips[0]
    assert clip.position_seconds == 12.5
    assert clip.start_time_beats is None  # never coerced across domains


def test_native_payload_preserves_arbitrary_model():
    session = _session()
    assert session.native is not None
    assert session.native.dialect == "reaper"
    assert session.native.model == {"tracks": []}


def test_field_provenance_marks_heuristics():
    track = _session().tracks[0]
    assert track.field_provenance["role"].observability == "inferred"
    assert track.provenance.observability == "observed"


def test_provenance_helpers():
    assert inferred("x").observability == "inferred"
    assert annotation("x").observability == "annotation"
    assert Provenance().observability == "observed"
    assert Provenance().confidence == 1.0


def test_convenience_accessors():
    session = _session()
    assert [p.name for p in session.all_processors()] == ["ReaComp"]
    assert [c.name for c in session.all_clips()] == ["vox take 3"]
    assert session.track_by_id("reaper:track-1").name == "Lead Vox"
    assert session.track_by_id("nope") is None
    assert session.tracks_of_kind("audio")[0].id == "reaper:track-1"


def test_recommendation_defaults_carry_caveat_and_references():
    rec = Recommendation(id="r-1", title="Test")
    assert rec.caveat  # non-empty by default: producer agency is preserved
    assert rec.references == []


def test_descriptor_set_union_fields():
    d = AudioDescriptorSet(
        available=True,
        rms_mean=0.1,
        active_rms_mean=0.2,  # Logic silence-gated field
        spectral_complexity_mean=3.4,  # Ableton essentia field
        extra={"custom": 1},  # Reaper adapter hook
    )
    assert d.active_rms_mean == 0.2
    assert d.spectral_complexity_mean == 3.4


def test_evidence_bundle_attaches_to_any_dialect():
    session = _session()
    session.evidence = EvidenceBundle(
        channel_strip_notes=[ChannelStripNote(id="note-1", track_name="Lead Vox")]
    )
    assert session.evidence.channel_strip_notes[0].track_name == "Lead Vox"


def test_to_dict_is_json_ready():
    payload = to_dict(_session())
    assert isinstance(payload, dict)
    assert payload["tracks"][0]["processors"][0]["name"] == "ReaComp"
    assert payload["tracks"][0]["field_provenance"]["role"]["observability"] == "inferred"
