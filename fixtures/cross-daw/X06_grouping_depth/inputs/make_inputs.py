"""Generate the X06 "grouping depth" bundle from the real contract pipeline.

X06 is a *synthetic* fixture: there is no DAW behind it. It exists to exercise
the P6 routing/grouping/processing depth added to the contract, by building one
nested :class:`~canonical_snapshot.nested.CanonicalSession` that packs every
grouping-honesty and routing-depth case into a single session, then running it
through the *real* ``flatten_session`` + ``validate_snapshot`` so the frozen
bundle can never drift from the code that produces it.

The one session exercises, in order:

* an **organizational-only folder** (``extras.organizational_only``) with two
  children — CONTAINS only, no summing;
* a **group-channel bus** (``extras.group_channel_enabled``) with two children —
  CONTAINS + SUMS_TO;
* a **VCA** track whose ``controls`` list scales two faders — CONTROLS, never
  SUMS_TO;
* a **stereo send** (``source_channels=[0, 1]``, ``channel_count=2``) and a
  **mono send** (``[2]``, count 1) — the channel spec rides only where observed;
* a **feedback pair** (A→B and B→A) — a routing cycle, which is data;
* an **FX channel** with an EQ→Delay main chain and a parallel Saturator→Chorus
  chain — branching, chain-scoped PRECEDES.

Run from anywhere:

    python fixtures/cross-daw/X06_grouping_depth/inputs/make_inputs.py
"""

from __future__ import annotations

import json
from pathlib import Path

from canonical_snapshot import (
    AdapterDescriptor,
    CapabilityManifest,
    DomainCapability,
    FieldCapability,
    SourceInfo,
    flatten_session,
    nested,
    validate_snapshot,
)

HERE = Path(__file__).resolve().parent
BUNDLE_DIR = HERE.parent / "bundles" / "synthetic"

DIALECT = "synthetic"
SESSION_NAME = "X06 Grouping Depth"


def build_session() -> nested.CanonicalSession:
    """The single session that packs every grouping/routing-depth case."""
    tracks = [
        # 1. Organizational-only folder + two children -> CONTAINS only.
        nested.Track(
            id="synthetic:folder-org",
            index=0,
            name="Arrange Folder",
            kind="group",
            extras={"organizational_only": True},
        ),
        nested.Track(
            id="synthetic:track-perc",
            index=1,
            name="Perc Loop",
            group_id="synthetic:folder-org",
        ),
        nested.Track(
            id="synthetic:track-shaker",
            index=2,
            name="Shaker",
            group_id="synthetic:folder-org",
        ),
        # 2. Group-channel bus + two children -> CONTAINS + SUMS_TO.
        nested.Track(
            id="synthetic:bus-drum",
            index=3,
            name="Drum Bus",
            kind="group",
            extras={"group_channel_enabled": True},
        ),
        nested.Track(
            id="synthetic:track-kick",
            index=4,
            name="Kick",
            role="Drums",
            group_id="synthetic:bus-drum",
        ),
        nested.Track(
            id="synthetic:track-snare",
            index=5,
            name="Snare",
            role="Drums",
            group_id="synthetic:bus-drum",
        ),
        # 3. VCA controlling the two drum faders -> CONTROLS (not summing).
        nested.Track(
            id="synthetic:vca-drums",
            index=6,
            name="Drum VCA",
            kind="unknown",
            role="VCA",
            controls=["synthetic:track-kick", "synthetic:track-snare"],
        ),
        # 4. Channel'd sends: a stereo source and a return.
        nested.Track(id="synthetic:track-lead", index=7, name="Lead Synth"),
        nested.Track(id="synthetic:track-bass", index=8, name="Bass"),
        nested.Track(
            id="synthetic:return-verb", index=9, name="Reverb Return", kind="return"
        ),
        # 5. Feedback pair.
        nested.Track(id="synthetic:track-fb-a", index=10, name="Feedback A"),
        nested.Track(id="synthetic:track-fb-b", index=11, name="Feedback B"),
        # 6. FX channel with a main chain and a parallel chain -> PRECEDES.
        nested.Track(
            id="synthetic:track-fx",
            index=12,
            name="FX Bus",
            kind="aux",
            processors=[
                nested.Processor(
                    id="synthetic:proc-eq",
                    track_id="synthetic:track-fx",
                    index=0,
                    name="EQ",
                    family="EQ",
                    chain="main",
                ),
                nested.Processor(
                    id="synthetic:proc-delay",
                    track_id="synthetic:track-fx",
                    index=1,
                    name="Delay",
                    family="Delay",
                    chain="main",
                ),
                nested.Processor(
                    id="synthetic:proc-sat",
                    track_id="synthetic:track-fx",
                    index=2,
                    name="Saturator",
                    family="Distortion",
                    chain="parallel",
                ),
                nested.Processor(
                    id="synthetic:proc-chorus",
                    track_id="synthetic:track-fx",
                    index=3,
                    name="Chorus",
                    family="Modulation",
                    chain="parallel",
                ),
            ],
        ),
    ]

    routes = [
        # Stereo send: channel spec present (2 channels, stereo layout).
        nested.Route(
            id="synthetic:send-stereo",
            source_track_id="synthetic:track-lead",
            target_track_id="synthetic:return-verb",
            route_type="send",
            volume_db=-6.0,
            source_channels=[0, 1],
            target_channels=[0, 1],
            channel_count=2,
            channel_layout="stereo",
        ),
        # Mono send: a single channel offset, mono layout.
        nested.Route(
            id="synthetic:send-mono",
            source_track_id="synthetic:track-bass",
            target_track_id="synthetic:return-verb",
            route_type="send",
            volume_db=-12.0,
            source_channels=[2],
            target_channels=[0],
            channel_count=1,
            channel_layout="mono",
        ),
        # Feedback pair -> a routing cycle (data, never a validation error).
        nested.Route(
            id="synthetic:send-fb-ab",
            source_track_id="synthetic:track-fb-a",
            target_track_id="synthetic:track-fb-b",
            route_type="send",
            volume_db=-18.0,
        ),
        nested.Route(
            id="synthetic:send-fb-ba",
            source_track_id="synthetic:track-fb-b",
            target_track_id="synthetic:track-fb-a",
            route_type="send",
            volume_db=-18.0,
        ),
    ]

    return nested.CanonicalSession(
        dialect=DIALECT,
        name=SESSION_NAME,
        tempo=120.0,
        time_signature="4/4",
        sample_rate=48000,
        tracks=tracks,
        routes=routes,
    )


def build_source() -> SourceInfo:
    return SourceInfo(
        daw=DIALECT,
        daw_version=None,
        adapter="x06-synthetic-generator",
        adapter_version="0.1.0",
        capture_modes=["synthetic"],
    )


def _field(support: str = "FULL") -> FieldCapability:
    # A hand-built fixture: the honest source stability is MANUAL and the
    # capability is UNTESTED against any real DAW — it demonstrates the
    # contract shape, not a captured pathway.
    return FieldCapability(
        applicability="APPLICABLE",
        support=support,
        capture_method="synthetic",
        source_stability="MANUAL",
        validation_status="UNTESTED",
    )


def build_capabilities() -> CapabilityManifest:
    return CapabilityManifest(
        daw=DIALECT,
        adapter="x06-synthetic-generator",
        adapter_version="0.1.0",
        read={
            "structure": DomainCapability(
                fields={"track_name": _field(), "hierarchy": _field()}
            ),
            "routing": DomainCapability(
                fields={"sends": _field(), "channel_offsets": _field()}
            ),
            "channel": DomainCapability(fields={"volume": _field()}),
            "processing": DomainCapability(
                fields={"insert_chain": _field(), "chain_order": _field()}
            ),
        },
        notes=[
            "Synthetic fixture: no DAW behind it. Exercises P6 grouping/routing/"
            "processing depth through the real flatten_session pipeline."
        ],
    )


def build_descriptor() -> AdapterDescriptor:
    return AdapterDescriptor(
        adapter_id="x06-synthetic-generator",
        daw=DIALECT,
        capture_modes=["synthetic"],
        read=(
            "Synthetic session generator. Emits grouping honesty "
            "(organizational-only vs group-channel), VCA CONTROLS, channel'd "
            "sends, a feedback cycle, and chain-scoped PRECEDES."
        ),
        write="NONE",
        live_observation="NONE",
        render="NONE",
        known_limitations=[
            "Not a real DAW capture: every value is hand-authored to exercise "
            "the contract. Source stability is MANUAL throughout.",
        ],
    )


def main() -> None:
    session = build_session()
    source = build_source()
    capabilities = build_capabilities()
    descriptor = build_descriptor()

    snapshot = flatten_session(session, source, capabilities)
    report = validate_snapshot(snapshot)
    if report.errors:
        raise SystemExit(f"X06 snapshot failed validation: {report.errors}")

    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    def _write(name: str, payload: dict) -> None:
        (BUNDLE_DIR / name).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    _write("canonical.snapshot.json", snapshot.model_dump())
    _write("capabilities.json", capabilities.model_dump())
    _write("adapter_descriptor.json", descriptor.model_dump())
    _write("validation.json", report.model_dump())

    print(f"wrote bundle -> {BUNDLE_DIR}")
    print(
        f"  {len(snapshot.entities)} entities, "
        f"{len(snapshot.relationships)} relationships, valid={report.valid}"
    )


if __name__ == "__main__":
    main()
