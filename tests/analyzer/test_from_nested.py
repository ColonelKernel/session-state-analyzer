"""flatten_session: the nested→flat crossing, exercised per track kind.

Table-driven over the TRACK ≠ CHANNEL split: each nested ``Track.kind`` has a
defined flat shape, and the availability/provenance semantics are the point,
not a side effect.
"""

import pytest

from canonical_snapshot import (
    SourceInfo,
    flatten_session,
    nested,
    validate_snapshot,
)


def _source(daw="reaper", modes=("rpp_file",)):
    return SourceInfo(
        daw=daw,
        adapter=f"{daw}-explorer",
        adapter_version="0.1.0",
        capture_modes=list(modes),
    )


def _flatten(session, **kwargs):
    snapshot = flatten_session(session, _source(daw=session.dialect), **kwargs)
    report = validate_snapshot(snapshot)
    assert report.errors == [], report.errors
    return snapshot


def _rels(snapshot, rel_type):
    return [(r.source, r.target) for r in snapshot.relationships_of_type(rel_type)]


# ---------------------------------------------------------------------------
# The TRACK ≠ CHANNEL split, per kind
# ---------------------------------------------------------------------------

KIND_CASES = [
    # (kind, expect_track, expect_channel, expected_roles_subset)
    ("audio", True, True, set()),
    ("midi", True, True, set()),
    ("aux", True, True, set()),
    ("unknown", True, True, set()),
    ("group", True, True, {"submix", "folder_parent"}),
    ("return", False, True, {"effect_return"}),
    ("master", False, True, {"main_output"}),
    ("inferred", True, False, set()),
]


@pytest.mark.parametrize("kind,expect_track,expect_channel,roles", KIND_CASES)
def test_track_channel_split_per_kind(kind, expect_track, expect_channel, roles):
    track = nested.Track(id=f"reaper:track-0", name="T", kind=kind, volume_db=-6.0)
    snapshot = _flatten(nested.CanonicalSession(dialect="reaper", tracks=[track]))

    track_ids = {e.id for e in snapshot.entities_of_type("TRACK")}
    channel_ids = {e.id for e in snapshot.entities_of_type("CHANNEL")}

    if expect_track:
        assert "reaper:track-0" in track_ids
    else:
        assert track_ids == set()

    if expect_track and expect_channel:
        # Fused-concept DAW path: both halves plus the joining edge, with
        # the deterministic ":channel" id suffix.
        assert "reaper:track-0:channel" in channel_ids
        assert _rels(snapshot, "TRACK_USES_CHANNEL") == [
            ("reaper:track-0", "reaper:track-0:channel")
        ]
        channel = snapshot.entity_by_id("reaper:track-0:channel")
        assert channel.properties["volume_db"] == -6.0
        track_entity = snapshot.entity_by_id("reaper:track-0")
        assert "volume_db" not in track_entity.properties
    elif expect_channel:
        # Channel-like natives keep the nested id; no lane entity exists.
        assert channel_ids == {"reaper:track-0"}
        assert _rels(snapshot, "TRACK_USES_CHANNEL") == []
    else:
        # Evidence-only lane: no channel was observed, and the snapshot
        # says so instead of inventing one.
        assert channel_ids == set()
        track_entity = snapshot.entity_by_id("reaper:track-0")
        assert track_entity.availability == {"channel": "UNKNOWN"}

    entity = snapshot.entity_by_id("reaper:track-0")
    assert roles.issubset(set(entity.semantic_roles))
    assert entity.native.daw == "reaper"
    assert entity.native.native_type == kind


def test_role_mapping_known_and_unknown():
    session = nested.CanonicalSession(
        dialect="reaper",
        tracks=[
            nested.Track(id="reaper:track-0", name="Lead", role="Vocal"),
            nested.Track(id="reaper:track-1", name="Weird", role="Granular Mangler"),
        ],
    )
    snapshot = _flatten(session)
    assert snapshot.entity_by_id("reaper:track-0").semantic_roles == ["vocal_source"]
    # Unknown roles pass through slugified, never dropped.
    assert snapshot.entity_by_id("reaper:track-1").semantic_roles == ["granular_mangler"]


def test_group_membership_edges():
    session = nested.CanonicalSession(
        dialect="ableton",
        tracks=[
            nested.Track(id="ableton:group-1", name="Drum Bus", kind="group"),
            nested.Track(id="ableton:track-1", name="Kick", group_id="ableton:group-1"),
        ],
    )
    snapshot = _flatten(session)
    assert ("ableton:group-1", "ableton:track-1") in _rels(snapshot, "CONTAINS")
    assert ("ableton:track-1:channel", "ableton:group-1:channel") in _rels(
        snapshot, "CHANNEL_ROUTES_TO"
    )
    assert ("ableton:track-1:channel", "ableton:group-1:channel") in _rels(
        snapshot, "SUMS_TO"
    )


# ---------------------------------------------------------------------------
# Processors, parameters, clips, assets
# ---------------------------------------------------------------------------


def test_processor_chain_with_parameters():
    session = nested.CanonicalSession(
        dialect="ableton",
        tracks=[
            nested.Track(
                id="ableton:track-1",
                name="Vox",
                processors=[
                    nested.Processor(
                        id="ableton:device-1",
                        track_id="ableton:track-1",
                        index=0,
                        name="EQ Eight",
                        kind="AudioEffect",
                        family="EQ",
                        enabled=True,
                        field_provenance={"family": nested.inferred("keyword classifier")},
                        parameters=[
                            nested.ProcessorParameter(
                                id="ableton:param-1",
                                processor_id="ableton:device-1",
                                name="Freq",
                                value=440.0,
                            )
                        ],
                    ),
                    nested.Processor(
                        id="ableton:device-2",
                        track_id="ableton:track-1",
                        index=1,
                        name="Glue Compressor",
                    ),
                ],
            )
        ],
    )
    snapshot = _flatten(session)

    processors = snapshot.entities_of_type("PROCESSOR")
    assert {p.id for p in processors} == {"ableton:device-1", "ableton:device-2"}

    # Processing edges hang off the CHANNEL side of the split, ordered.
    processed_by = snapshot.relationships_of_type("CHANNEL_PROCESSED_BY")
    assert [(r.source, r.target, r.properties["index"]) for r in processed_by] == [
        ("ableton:track-1:channel", "ableton:device-1", 0),
        ("ableton:track-1:channel", "ableton:device-2", 1),
    ]

    # Parameters: PARAMETER entity + CONTAINS(kind=parameter); the registry
    # deliberately has no HAS_PARAMETER.
    param = snapshot.entity_by_id("ableton:param-1")
    assert param.entity_type == "PARAMETER"
    assert param.properties["value"] == 440.0
    contains = [
        r
        for r in snapshot.relationships_of_type("CONTAINS")
        if r.properties.get("kind") == "parameter"
    ]
    assert [(r.source, r.target) for r in contains] == [("ableton:device-1", "ableton:param-1")]

    # field_provenance survives: the family value is marked inferred.
    device = snapshot.entity_by_id("ableton:device-1")
    family_prov = snapshot.provenance_by_id(device.prov["family"])
    assert family_prov.evidence == "INFERRED"
    assert family_prov.confidence == 0.5


def test_clips_become_temporal_objects_with_unit_tagged_time():
    session = nested.CanonicalSession(
        dialect="reaper",
        tracks=[
            nested.Track(
                id="reaper:track-0",
                clips=[
                    nested.Clip(
                        id="reaper:item-1",
                        track_id="reaper:track-0",
                        name="verse",
                        clip_type="audio",
                        position_seconds=12.5,
                        length_seconds=8.0,
                        audio_file="/audio/verse take 1.wav",
                    ),
                    nested.Clip(
                        id="reaper:item-2",
                        track_id="reaper:track-0",
                        clip_type="audio",
                        position_seconds=20.5,
                        audio_file="/audio/verse take 1.wav",
                    ),
                ],
            )
        ],
    )
    snapshot = _flatten(session)

    clip = snapshot.entity_by_id("reaper:item-1")
    assert clip.entity_type == "TEMPORAL_OBJECT"
    # Copied as-is: seconds stay seconds, no beats appear.
    assert clip.properties["position_seconds"] == 12.5
    assert "start_time_beats" not in clip.properties
    assert ("reaper:track-0", "reaper:item-1") in _rels(
        snapshot, "TRACK_CONTAINS_TEMPORAL_OBJECT"
    )

    # One shared file → one deduplicated MEDIA_ASSET, two references.
    assets = snapshot.entities_of_type("MEDIA_ASSET")
    assert len(assets) == 1
    assert assets[0].id == "asset:audio_verse_take_1_wav"
    assert assets[0].properties["path"] == "/audio/verse take 1.wav"
    refs = _rels(snapshot, "REFERENCES_ASSET")
    assert set(refs) == {
        ("reaper:item-1", "asset:audio_verse_take_1_wav"),
        ("reaper:item-2", "asset:audio_verse_take_1_wav"),
    }


def test_scenes_become_structural_containers():
    session = nested.CanonicalSession(
        dialect="ableton",
        scenes=[nested.Scene(id="ableton:scene-1", index=0, name="Intro")],
        tracks=[
            nested.Track(
                id="ableton:track-1",
                clips=[
                    nested.Clip(
                        id="ableton:clip-1",
                        track_id="ableton:track-1",
                        scene_id="ableton:scene-1",
                        clip_type="midi",
                        start_time_beats=0.0,
                    )
                ],
            )
        ],
    )
    snapshot = _flatten(session)
    scene = snapshot.entity_by_id("ableton:scene-1")
    assert scene.entity_type == "STRUCTURAL_CONTAINER"
    assert scene.native.native_type == "scene"
    contains = _rels(snapshot, "CONTAINS")
    assert ("ableton:project", "ableton:scene-1") in contains
    assert ("ableton:scene-1", "ableton:clip-1") in contains


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def test_routes_use_channel_endpoints():
    session = nested.CanonicalSession(
        dialect="ableton",
        tracks=[
            nested.Track(id="ableton:track-1", name="Vox"),
            nested.Track(id="ableton:return-a", name="Reverb", kind="return"),
        ],
        routes=[
            nested.Route(
                id="ableton:send-1",
                source_track_id="ableton:track-1",
                target_track_id="ableton:return-a",
                route_type="send",
                volume_db=-12.0,
                enabled=True,
            )
        ],
    )
    snapshot = _flatten(session)
    sends = snapshot.relationships_of_type("CHANNEL_SENDS_TO")
    assert len(sends) == 1
    send = sends[0]
    # Source resolves to the fused track's CHANNEL half; target is the
    # channel-only return entity (which kept the nested id).
    assert send.source == "ableton:track-1:channel"
    assert send.target == "ableton:return-a"
    assert send.properties["volume_db"] == -12.0
    assert send.properties["enabled"] is True
    assert send.prov_ref is not None


def test_receive_routes_are_sends_and_other_routes_route():
    session = nested.CanonicalSession(
        dialect="reaper",
        tracks=[
            nested.Track(id="reaper:track-0"),
            nested.Track(id="reaper:track-1"),
        ],
        routes=[
            nested.Route(
                id="reaper:route-1",
                source_track_id="reaper:track-0",
                target_track_id="reaper:track-1",
                route_type="receive",
                send_mode=0,
            ),
            nested.Route(
                id="reaper:route-2",
                source_track_id="reaper:track-0",
                target_track_id="reaper:track-1",
                route_type="hardware_output",
            ),
        ],
    )
    snapshot = _flatten(session)
    assert len(snapshot.relationships_of_type("CHANNEL_SENDS_TO")) == 1
    routed = snapshot.relationships_of_type("CHANNEL_ROUTES_TO")
    assert [r.properties["route_type"] for r in routed] == ["hardware_output"]


def test_unresolved_route_source_becomes_routing_endpoint():
    session = nested.CanonicalSession(
        dialect="ableton",
        tracks=[nested.Track(id="ableton:return-a", kind="return", name="Reverb")],
        routes=[
            nested.Route(
                id="ableton:send-9",
                source_track_id=None,
                source_name="(deleted track)",
                target_track_id="ableton:return-a",
                route_type="unresolved",
            )
        ],
    )
    snapshot = _flatten(session)
    endpoint = snapshot.entity_by_id("ableton:send-9")
    assert endpoint.entity_type == "ROUTING_ENDPOINT"
    assert endpoint.name == "(deleted track)"
    # Identity is a stated unknown, not a null.
    assert endpoint.availability == {"identity": "UNKNOWN"}
    routed = snapshot.relationships_of_type("CHANNEL_ROUTES_TO")
    assert [(r.source, r.target) for r in routed] == [("ableton:send-9", "ableton:return-a")]


# ---------------------------------------------------------------------------
# Provenance store semantics
# ---------------------------------------------------------------------------


def test_prov_store_dedups_identical_records():
    tracks = [
        nested.Track(id=f"reaper:track-{i}", provenance=nested.Provenance(
            observability="observed", source_artifact="rpp_file"))
        for i in range(5)
    ]
    snapshot = _flatten(nested.CanonicalSession(dialect="reaper", tracks=tracks))
    observed = [p for p in snapshot.provenance if p.evidence == "OBSERVED"]
    assert len(observed) == 1  # five identical claims → one record
    for track in snapshot.entities_of_type("TRACK"):
        assert track.prov["*"] == observed[0].id


def test_evidence_vocabulary_migration():
    session = nested.CanonicalSession(
        dialect="logic",
        tracks=[
            nested.Track(
                id="logic:track-1",
                kind="inferred",
                provenance=nested.Provenance(
                    observability="inferred", confidence=0.7, explanation="from stem name"
                ),
                field_provenance={
                    "name": nested.annotation("user manifest"),
                    "color": nested.Provenance(observability="derived", confidence=0.9),
                },
            )
        ],
    )
    snapshot = _flatten(session)
    track = snapshot.entity_by_id("logic:track-1")

    base = snapshot.provenance_by_id(track.prov["*"])
    assert base.evidence == "INFERRED"
    assert base.confidence == 0.7

    name_prov = snapshot.provenance_by_id(track.prov["name"])
    assert name_prov.evidence == "ANNOTATED"

    # D5: "derived" arrives as INFERRED tagged derived_computation.
    color_prov = snapshot.provenance_by_id(track.prov["color"])
    assert color_prov.evidence == "INFERRED"
    assert color_prov.capture_method == "derived_computation"


def test_observed_records_carry_no_confidence():
    snapshot = _flatten(
        nested.CanonicalSession(dialect="reaper", tracks=[nested.Track(id="reaper:track-0")])
    )
    for record in snapshot.provenance:
        if record.evidence == "OBSERVED":
            assert record.confidence is None


def test_field_provenance_splits_between_track_and_channel():
    session = nested.CanonicalSession(
        dialect="reaper",
        tracks=[
            nested.Track(
                id="reaper:track-0",
                role="Vocal",
                volume_db=-3.0,
                field_provenance={
                    "role": nested.inferred("keyword match", confidence=0.6),
                    "volume_db": nested.Provenance(observability="observed", source_artifact="rpp_file"),
                },
            )
        ],
    )
    snapshot = _flatten(session)
    track = snapshot.entity_by_id("reaper:track-0")
    channel = snapshot.entity_by_id("reaper:track-0:channel")
    # role lands on the TRACK's semantic_roles; volume on the CHANNEL side.
    assert "semantic_roles" in track.prov
    assert "volume_db" in channel.prov
    assert "volume_db" not in track.prov
    assert snapshot.provenance_by_id(track.prov["semantic_roles"]).evidence == "INFERRED"


# ---------------------------------------------------------------------------
# Hidden state, evidence bundle, extensions, native payload
# ---------------------------------------------------------------------------


def test_hidden_state_markers_become_availability_plus_hidden_prov():
    session = nested.CanonicalSession(
        dialect="reaper",
        tracks=[nested.Track(id="reaper:track-0")],
        hidden_state_markers=[
            nested.HiddenStateMarker(
                id="hsm-1",
                target_id="reaper:track-0",
                hidden_state_type="hidden_plugin_parameters",
                description="Plug-in parameter blobs are not decoded.",
                consequence="Parameter-level analysis is impossible from this artifact.",
            )
        ],
    )
    snapshot = _flatten(session)
    track = snapshot.entity_by_id("reaper:track-0")
    assert track.availability["plugin_parameters"] == "INACCESSIBLE"
    hidden = snapshot.provenance_by_id(track.prov["plugin_parameters"])
    assert hidden.evidence == "HIDDEN"
    assert "not decoded" in hidden.explanation
    markers = snapshot.extensions["reaper"]["hidden_state_markers"]
    assert markers[0]["id"] == "hsm-1"


def test_evidence_bundle_entities_and_extension_dump():
    evidence = nested.EvidenceBundle(
        audio_files=[
            nested.AudioEvidence(
                id="logic:audio-1",
                file_name="Lead Vox.wav",
                inferred_track_name="Lead Vox",
                inferred_role="Vocal",
                confidence=0.8,
                duration_seconds=180.0,
            )
        ],
        channel_strip_notes=[
            nested.ChannelStripNote(
                id="logic:note-1",
                track_name="Lead Vox",
                plugins=["Channel EQ", "Compressor"],
                bus="Vocal Bus",
                confidence=0.5,
            )
        ],
        stem_sum_reconciliation=nested.StemSumReconciliation(
            id="logic:stemsum-1",
            mixdown_audio_id="logic:audio-9",
            residual_db=-18.5,
        ),
        reference_comparisons=[
            nested.ReferenceComparison(
                id="logic:refcmp-1",
                mixdown_audio_id="logic:audio-9",
                reference_id="logic:ref-1",
            )
        ],
    )
    session = nested.CanonicalSession(dialect="logic", evidence=evidence)
    snapshot = _flatten(session)

    note = snapshot.entity_by_id("logic:note-1")
    assert note.entity_type == "ANNOTATION"
    note_prov = snapshot.provenance_by_id(note.prov["*"])
    assert note_prov.evidence == "ANNOTATED"
    assert note_prov.confidence == 0.5

    audio = snapshot.entity_by_id("logic:audio-1")
    assert audio.entity_type == "MEDIA_ASSET"
    assert snapshot.provenance_by_id(audio.prov["*"]).evidence == "OBSERVED"
    inferred_prov = snapshot.provenance_by_id(audio.prov["inferred_role"])
    assert inferred_prov.evidence == "INFERRED"
    assert inferred_prov.confidence == 0.8

    assert snapshot.entity_by_id("logic:stemsum-1").entity_type == "OBSERVATION"
    assert snapshot.entity_by_id("logic:refcmp-1").entity_type == "OBSERVATION"

    # Nothing dropped: the full bundle rides in extensions.
    dump = snapshot.extensions["logic"]["evidence"]
    assert dump["channel_strip_notes"][0]["bus"] == "Vocal Bus"


def test_native_payload_never_embedded():
    native = nested.NativePayload(dialect="reaper", model_name="ProjectState", model={"big": "blob"})
    session = nested.CanonicalSession(dialect="reaper", native=native)

    with_file = _flatten(session, native_file="native.json", native_sha256="abc123")
    ref = with_file.extensions["reaper"]["native_file"]
    assert ref == {"path": "native.json", "sha256": "abc123"}
    assert "big" not in str(with_file.model_dump().get("extensions"))

    without_file = _flatten(session)
    assert without_file.extensions["reaper"]["native_payload_omitted"] is True


def test_descriptors_recommendations_and_warnings_survive():
    session = nested.CanonicalSession(
        dialect="reaper",
        warnings=["route target not found"],
        descriptors=[nested.AudioDescriptorSet(id="desc-1", file_name="mix.wav")],
        recommendations=[nested.Recommendation(id="rec-1", title="Consider a HPF")],
        tracks=[nested.Track(id="reaper:track-0", warnings=["fx name truncated"])],
    )
    snapshot = _flatten(session)
    assert "route target not found" in snapshot.warnings
    assert any("fx name truncated" in w for w in snapshot.warnings)
    ext = snapshot.extensions["reaper"]
    assert ext["descriptors"][0]["id"] == "desc-1"
    assert ext["recommendations"][0]["title"] == "Consider a HPF"


def test_coverage_counts_are_split_by_evidence():
    session = nested.CanonicalSession(
        dialect="logic",
        tracks=[
            nested.Track(id="logic:track-1"),  # observed default
            nested.Track(
                id="logic:track-2",
                kind="inferred",
                provenance=nested.Provenance(observability="inferred", confidence=0.5),
            ),
        ],
        routes=[
            nested.Route(
                id="logic:route-1",
                source_track_id="logic:track-1",
                target_track_id="logic:track-2",
                provenance=nested.Provenance(observability="annotation", confidence=0.5),
            )
        ],
    )
    snapshot = _flatten(session)
    structure = snapshot.coverage["structure"]
    assert structure.applicable == 2
    assert structure.observed == 1
    assert structure.inferred == 1
    # The inferred track contributed no channel: channel coverage sees one.
    assert snapshot.coverage["channel"].applicable == 1
    routing = snapshot.coverage["routing"]
    # ANNOTATED items count as applicable without claiming a bucket
    # (documented approximation).
    assert routing.applicable == 1
    assert routing.observed == 0 and routing.inferred == 0 and routing.hidden == 0


def test_snapshot_id_deterministic_and_project_pointer():
    session = nested.CanonicalSession(dialect="cubase", name="My Song (v2)")
    snap_a = _flatten(session)
    snap_b = _flatten(session)
    assert snap_a.snapshot_id == snap_b.snapshot_id == "cubase:my_song_v2:snapshot"
    assert snap_a.project == "cubase:project"
    project = snap_a.entity_by_id("cubase:project")
    assert project.entity_type == "PROJECT"


def test_project_extras_merge_into_extensions():
    session = nested.CanonicalSession(
        dialect="reaper",
        tempo=140.0,
        time_signature="7/8",
        sample_rate=48000,
        extras={"time_sig_num": 7, "header_platform": "darwin"},
        metadata={"source_artifact": "rpp_file"},
    )
    snapshot = _flatten(session)
    project = snapshot.entity_by_id("reaper:project")
    assert project.properties["tempo"] == 140.0
    assert project.properties["time_signature"] == "7/8"
    assert project.properties["sample_rate"] == 48000
    ext = snapshot.extensions["reaper"]
    assert ext["time_sig_num"] == 7
    assert ext["metadata"] == {"source_artifact": "rpp_file"}
