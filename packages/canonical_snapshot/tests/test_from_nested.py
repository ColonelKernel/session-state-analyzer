"""flatten_session P6/P7 depth: routing channels, grouping honesty, control,
processing order, automation, modulation, and variants.

These exercise the additive contract-population added in Phase 1. They are
deliberately separate from the analyzer's ``tests/analyzer/test_from_nested.py``
(which covers the base TRACK≠CHANNEL split); here the point is the *depth*
fields, each asserted at the wire level and always re-validated.
"""

from __future__ import annotations

import pytest

from canonical_snapshot import (
    SourceInfo,
    flatten_session,
    nested,
    validate_snapshot,
)


def _source(daw="synthetic", modes=("synthetic",)):
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


def _props(snapshot, rel_type):
    return [r.properties for r in snapshot.relationships_of_type(rel_type)]


# ---------------------------------------------------------------------------
# Routing channels: present ⇒ keys ride; absent ⇒ omitted (stereo-implicit)
# ---------------------------------------------------------------------------


def test_channel_keys_ride_only_when_present():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[
            nested.Track(id="synthetic:track-0", name="Src"),
            nested.Track(id="synthetic:return-a", name="Verb", kind="return"),
        ],
        routes=[
            nested.Route(
                id="synthetic:send-ch",
                source_track_id="synthetic:track-0",
                target_track_id="synthetic:return-a",
                route_type="send",
                source_channels=[0, 1],
                target_channels=[0, 1],
                channel_count=2,
                channel_layout="stereo",
            ),
            nested.Route(
                id="synthetic:send-plain",
                source_track_id="synthetic:track-0",
                target_track_id="synthetic:return-a",
                route_type="send",
                volume_db=-6.0,
            ),
        ],
    )
    snapshot = _flatten(session)
    sends = snapshot.relationships_of_type("CHANNEL_SENDS_TO")
    channelled = next(r for r in sends if r.source == "synthetic:track-0:channel"
                      and "source_channels" in r.properties)
    assert channelled.properties["source_channels"] == [0, 1]
    assert channelled.properties["target_channels"] == [0, 1]
    assert channelled.properties["channel_count"] == 2
    assert channelled.properties["channel_layout"] == "stereo"

    # The plain send omits every channel key: stereo-implicit, not invented.
    plain = next(r for r in sends if r.properties.get("volume_db") == -6.0)
    for key in ("source_channels", "target_channels", "channel_count", "channel_layout"):
        assert key not in plain.properties


def test_channel_keys_ride_on_channel_routes_to():
    """The channel spec applies to CHANNEL_ROUTES_TO as well as sends."""
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[
            nested.Track(id="synthetic:track-0"),
            nested.Track(id="synthetic:track-1"),
        ],
        routes=[
            nested.Route(
                id="synthetic:route-1",
                source_track_id="synthetic:track-0",
                target_track_id="synthetic:track-1",
                route_type="hardware_output",
                channel_count=4,
                channel_layout="quad",
            )
        ],
    )
    snapshot = _flatten(session)
    routed = snapshot.relationships_of_type("CHANNEL_ROUTES_TO")
    assert routed[0].properties["channel_count"] == 4
    assert routed[0].properties["channel_layout"] == "quad"


# ---------------------------------------------------------------------------
# Grouping honesty: _group_sums decides SUMS_TO, CONTAINS is unconditional
# ---------------------------------------------------------------------------


def _group_session(group_track: nested.Track) -> nested.CanonicalSession:
    return nested.CanonicalSession(
        dialect="synthetic",
        tracks=[
            group_track,
            nested.Track(id="synthetic:child-1", group_id=group_track.id),
            nested.Track(id="synthetic:child-2", group_id=group_track.id),
        ],
    )


def test_organizational_only_folder_is_contains_only():
    snapshot = _flatten(
        _group_session(
            nested.Track(
                id="synthetic:folder",
                kind="group",
                extras={"organizational_only": True},
            )
        )
    )
    contains = [
        r for r in snapshot.relationships_of_type("CONTAINS")
        if r.properties.get("kind") == "group_member"
    ]
    assert len(contains) == 2  # both children still contained
    assert snapshot.relationships_of_type("SUMS_TO") == []
    # And no group-sum route was invented.
    assert not any(
        r.properties.get("via") == "group_sum"
        for r in snapshot.relationships_of_type("CHANNEL_ROUTES_TO")
    )


def test_group_channel_enabled_folder_sums():
    snapshot = _flatten(
        _group_session(
            nested.Track(
                id="synthetic:bus",
                kind="group",
                extras={"group_channel_enabled": True},
            )
        )
    )
    assert len([r for r in snapshot.relationships_of_type("CONTAINS")
                if r.properties.get("kind") == "group_member"]) == 2
    sums = _rels(snapshot, "SUMS_TO")
    assert ("synthetic:child-1:channel", "synthetic:bus:channel") in sums
    assert ("synthetic:child-2:channel", "synthetic:bus:channel") in sums


def test_group_defaults_to_summing():
    """No flags, no typed field: a group is honestly assumed a summing bus."""
    snapshot = _flatten(
        _group_session(nested.Track(id="synthetic:bus", kind="group"))
    )
    assert len(snapshot.relationships_of_type("SUMS_TO")) == 2


def test_typed_sums_children_overrides_extras():
    """An explicit ``sums_children`` wins over the extras heuristic."""
    snapshot = _flatten(
        _group_session(
            nested.Track(
                id="synthetic:bus",
                kind="group",
                sums_children=False,
                extras={"group_channel_enabled": True},  # would otherwise sum
            )
        )
    )
    assert snapshot.relationships_of_type("SUMS_TO") == []

    snapshot2 = _flatten(
        _group_session(
            nested.Track(
                id="synthetic:folder",
                kind="group",
                sums_children=True,
                extras={"organizational_only": True},  # would otherwise not sum
            )
        )
    )
    assert len(snapshot2.relationships_of_type("SUMS_TO")) == 2


# ---------------------------------------------------------------------------
# CONTROLS from Track.controls (VCA / edit group)
# ---------------------------------------------------------------------------


def test_controls_from_track_controls():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[
            nested.Track(
                id="synthetic:vca",
                kind="unknown",
                controls=["synthetic:track-a", "synthetic:track-b"],
            ),
            nested.Track(id="synthetic:track-a"),
            nested.Track(id="synthetic:track-b"),
        ],
    )
    snapshot = _flatten(session)
    controls = snapshot.relationships_of_type("CONTROLS")
    assert {(r.source, r.target) for r in controls} == {
        ("synthetic:vca:channel", "synthetic:track-a:channel"),
        ("synthetic:vca:channel", "synthetic:track-b:channel"),
    }
    assert all(r.properties["kind"] == "vca_or_edit_group" for r in controls)
    # CONTROLS is not SUMS_TO — a VCA carries no audio sum.
    assert snapshot.relationships_of_type("SUMS_TO") == []


def test_controls_unknown_target_warns_and_is_skipped():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[nested.Track(id="synthetic:vca", controls=["synthetic:ghost"])],
    )
    snapshot = _flatten(session)
    assert snapshot.relationships_of_type("CONTROLS") == []
    assert any("ghost" in w for w in snapshot.warnings)


# ---------------------------------------------------------------------------
# PRECEDES: chain-scoped processing order
# ---------------------------------------------------------------------------


def _proc(pid, index, chain="main"):
    return nested.Processor(
        id=pid, track_id="synthetic:track-fx", index=index, name=pid, chain=chain
    )


def test_precedes_links_consecutive_same_chain():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[
            nested.Track(
                id="synthetic:track-fx",
                processors=[
                    _proc("synthetic:eq", 0, "main"),
                    _proc("synthetic:delay", 1, "main"),
                ],
            )
        ],
    )
    snapshot = _flatten(session)
    precedes = snapshot.relationships_of_type("PRECEDES")
    assert [(r.source, r.target) for r in precedes] == [
        ("synthetic:eq", "synthetic:delay")
    ]
    assert precedes[0].properties["chain"] == "main"


def test_precedes_never_crosses_chains():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[
            nested.Track(
                id="synthetic:track-fx",
                processors=[
                    _proc("synthetic:eq", 0, "main"),
                    _proc("synthetic:delay", 1, "main"),
                    _proc("synthetic:rec-gate", 2, "rec"),
                    _proc("synthetic:rec-comp", 3, "rec"),
                ],
            )
        ],
    )
    snapshot = _flatten(session)
    precedes = {(r.source, r.target): r.properties["chain"]
                for r in snapshot.relationships_of_type("PRECEDES")}
    # Two intra-chain links, no main<->rec edge.
    assert precedes == {
        ("synthetic:eq", "synthetic:delay"): "main",
        ("synthetic:rec-gate", "synthetic:rec-comp"): "rec",
    }


def test_single_processor_has_no_precedes():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[
            nested.Track(
                id="synthetic:track-fx", processors=[_proc("synthetic:eq", 0)]
            )
        ],
    )
    snapshot = _flatten(session)
    assert snapshot.relationships_of_type("PRECEDES") == []


# ---------------------------------------------------------------------------
# Automation: entity + CONTROLS target resolution + flat mirror + coverage
# ---------------------------------------------------------------------------


def _fx_track_with_param():
    return nested.Track(
        id="synthetic:track-fx",
        processors=[
            nested.Processor(
                id="synthetic:comp",
                track_id="synthetic:track-fx",
                index=0,
                name="Comp",
                parameters=[
                    nested.ProcessorParameter(
                        id="synthetic:param-thr",
                        processor_id="synthetic:comp",
                        name="Threshold",
                        value=-20.0,
                    )
                ],
            )
        ],
    )


def test_automation_targets_parameter():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[_fx_track_with_param()],
        automation=[
            nested.Automation(
                id="synthetic:auto-thr",
                parameter_name="Threshold",
                target_parameter_id="synthetic:param-thr",
                unit="dB",
                points=[
                    nested.AutomationPoint(time=0.0, value=-20.0),
                    nested.AutomationPoint(time=4.0, value=-8.0),
                ],
            )
        ],
    )
    snapshot = _flatten(session)
    autos = snapshot.entities_of_type("AUTOMATION")
    assert len(autos) == 1
    auto = autos[0]
    assert auto.id == "synthetic:auto:threshold:1"
    assert auto.properties["point_count"] == 2
    assert auto.properties["value_min"] == -20.0
    assert auto.properties["value_max"] == -8.0
    assert auto.properties["first_value"] == -20.0
    assert auto.properties["last_value"] == -8.0
    assert auto.availability == {}  # target resolved

    controls = snapshot.relationships_of_type("CONTROLS")
    assert [(r.source, r.target) for r in controls] == [
        ("synthetic:auto:threshold:1", "synthetic:param-thr")
    ]
    assert controls[0].properties["target"] == "parameter"

    # Flat mirror + coverage.
    assert snapshot.automation[0]["id"] == "synthetic:auto:threshold:1"
    assert snapshot.automation[0]["target"] == "synthetic:param-thr"
    assert len(snapshot.automation[0]["points"]) == 2
    assert snapshot.coverage["automation"].applicable == 1
    assert snapshot.coverage["automation"].observed == 1


def test_automation_targets_processor_field():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[
            nested.Track(
                id="synthetic:track-fx",
                processors=[
                    nested.Processor(
                        id="synthetic:comp",
                        track_id="synthetic:track-fx",
                        index=0,
                        name="Comp",
                    )
                ],
            )
        ],
        automation=[
            nested.Automation(
                id="synthetic:auto-mix",
                parameter_name="Mix",
                target_processor_id="synthetic:comp",
            )
        ],
    )
    snapshot = _flatten(session)
    controls = snapshot.relationships_of_type("CONTROLS")
    assert (controls[0].source, controls[0].target) == (
        "synthetic:auto:mix:1",
        "synthetic:comp",
    )
    assert controls[0].properties == {"target": "processor_field", "target_field": "Mix"}


def test_automation_targets_channel_field():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[nested.Track(id="synthetic:track-vox")],
        automation=[
            nested.Automation(
                id="synthetic:auto-vol",
                parameter_name="Volume",
                target_track_id="synthetic:track-vox",
                target_channel_field="volume_db",
            )
        ],
    )
    snapshot = _flatten(session)
    controls = snapshot.relationships_of_type("CONTROLS")
    assert (controls[0].source, controls[0].target) == (
        "synthetic:auto:volume:1",
        "synthetic:track-vox:channel",
    )
    assert controls[0].properties == {"target": "channel_field", "field": "volume_db"}


def test_automation_unknown_target_gets_availability_and_no_edge():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[nested.Track(id="synthetic:track-0")],
        automation=[
            nested.Automation(
                id="synthetic:auto-orphan",
                parameter_name="Orphan",
                target_parameter_id="synthetic:does-not-exist",
            )
        ],
    )
    snapshot = _flatten(session)
    auto = snapshot.entities_of_type("AUTOMATION")[0]
    assert auto.availability == {"target": "UNKNOWN"}
    assert snapshot.relationships_of_type("CONTROLS") == []
    # Still mirrored into the flat list, with a null target.
    assert snapshot.automation[0]["target"] is None


# ---------------------------------------------------------------------------
# Modulation: ANNOTATED entity + CONTROLS + sidechain LINKED_WITH
# ---------------------------------------------------------------------------


def test_modulation_sidechain_is_annotated_with_links():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[
            nested.Track(id="synthetic:track-kick"),
            nested.Track(id="synthetic:track-bass"),
        ],
        modulation=[
            nested.Modulation(
                id="synthetic:mod-duck",
                source_type="sidechain",
                parameter_name="gain",
                source_track_id="synthetic:track-kick",
                target_track_id="synthetic:track-bass",
                target_channel_field="gain",
                depth=-6.0,
                provenance=nested.annotation("asserted ducking", confidence=0.6),
            )
        ],
    )
    snapshot = _flatten(session)
    mods = snapshot.entities_of_type("MODULATION")
    assert len(mods) == 1
    mod = mods[0]
    assert mod.properties["source_type"] == "sidechain"
    # The entity-level provenance is ANNOTATED (a user assertion).
    assert snapshot.provenance_by_id(mod.prov["*"]).evidence == "ANNOTATED"

    controls = snapshot.relationships_of_type("CONTROLS")
    assert (controls[0].source, controls[0].target) == (
        mod.id,
        "synthetic:track-bass:channel",
    )
    linked = snapshot.relationships_of_type("LINKED_WITH")
    assert (linked[0].source, linked[0].target) == (
        "synthetic:track-kick:channel",
        mod.id,
    )
    assert linked[0].properties["kind"] == "sidechain_source"
    assert snapshot.modulation[0]["source_type"] == "sidechain"


def test_non_sidechain_modulation_has_no_linked_with():
    session = nested.CanonicalSession(
        dialect="synthetic",
        tracks=[nested.Track(id="synthetic:track-pad")],
        modulation=[
            nested.Modulation(
                id="synthetic:mod-lfo",
                source_type="lfo",
                parameter_name="cutoff",
                target_track_id="synthetic:track-pad",
                target_channel_field="pan",
                rate=0.5,
            )
        ],
    )
    snapshot = _flatten(session)
    assert snapshot.relationships_of_type("LINKED_WITH") == []
    assert len(snapshot.relationships_of_type("CONTROLS")) == 1


# ---------------------------------------------------------------------------
# Variant: one entity from the self-declared fields, lineage as properties
# ---------------------------------------------------------------------------


def test_variant_entity_from_fields():
    session = nested.CanonicalSession(
        dialect="synthetic",
        name="Song v7",
        variant_label="v7",
        variant_family="5_Step",
        derived_from_snapshot_id="synthetic:song_v6:snapshot",
        tracks=[nested.Track(id="synthetic:track-0")],
    )
    snapshot = _flatten(session)
    variants = snapshot.entities_of_type("VARIANT")
    assert len(variants) == 1
    variant = variants[0]
    assert variant.id == "synthetic:variant"
    assert variant.properties == {
        "label": "v7",
        "family": "5_Step",
        "derived_from_snapshot_id": "synthetic:song_v6:snapshot",
    }
    # Lineage is properties only: no cross-snapshot edges are emitted here.
    assert snapshot.relationships_of_type("DERIVED_FROM") == []
    assert snapshot.relationships_of_type("ALTERNATIVE_OF") == []


def test_no_variant_entity_without_declared_fields():
    session = nested.CanonicalSession(
        dialect="synthetic", tracks=[nested.Track(id="synthetic:track-0")]
    )
    snapshot = _flatten(session)
    assert snapshot.entities_of_type("VARIANT") == []


# ---------------------------------------------------------------------------
# Additivity: a bare session still produces the same base shape
# ---------------------------------------------------------------------------


def test_bare_session_has_empty_temporal_and_variant():
    snapshot = _flatten(
        nested.CanonicalSession(
            dialect="synthetic", tracks=[nested.Track(id="synthetic:track-0")]
        )
    )
    assert snapshot.automation == []
    assert snapshot.modulation == []
    assert snapshot.entities_of_type("AUTOMATION") == []
    assert snapshot.entities_of_type("MODULATION") == []
    assert snapshot.entities_of_type("VARIANT") == []
