"""Generate the synthetic ``demo_song`` variant family from the real pipeline.

These are *synthetic stand-in* variants: there is no DAW behind them (real
per-version Logic families are Phase 4). They exist so the P8 variants analyzer
has a family it can group, order, and diff, built by running four nested
:class:`~canonical_snapshot.nested.CanonicalSession`s through the *real*
``flatten_session`` + ``validate_snapshot`` so the frozen bundles can never
drift from the code that produces them.

One family (``variant_family="demo_song"``), four members that genuinely
differ:

* **v1** — the root: a vocal + a guitar (2 tracks). ``derived_from = None``.
* **v2** — v1 plus a drum track. ``variant_diff(v1, v2)`` finds the +1 track.
* **v2_alpha** — an *alternative* to v2 (v1 plus a synth instead of drums), also
  derived from v1, so it shares v2's ordinal and forms an ALTERNATIVE_OF edge.
* **v3** — v2 plus a reverb return + a vocal→reverb send + a bumped EQ Gain
  (0.5→0.7). ``variant_diff(v2, v3)`` finds the +1 send and the parameter
  change.

Every member's vocal clip references the same audio path, so the flattener
emits the same shared MEDIA_ASSET in each and SHARES_SOURCE_WITH forms across
the family. Ordinals (0/1/1/2) are *not* stored on the wire — the contract
does not emit a variant ordinal — they are recovered analyzer-side from the
``derived_from`` chain (v1→v2→v3, v1→v2_alpha).

Run from anywhere:

    python fixtures/variants/inputs/make_inputs.py
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
FIXTURES_DIR = HERE.parent

DIALECT = "demo"
FAMILY = "demo_song"
SHARED_AUDIO = "audio/demo_song.wav"

V1_SID = "demo:v1:snapshot"
V2_SID = "demo:v2:snapshot"
V2A_SID = "demo:v2_alpha:snapshot"
V3_SID = "demo:v3:snapshot"


def _vox(gain: float) -> nested.Track:
    """The lead vocal track — identical across members except the EQ gain.

    Carries the shared audio clip (drives the shared MEDIA_ASSET) and a Channel
    EQ whose Gain parameter is the knob v3 moves.
    """
    return nested.Track(
        id="demo:track-vox",
        index=0,
        name="Lead Vocal",
        role="Vocal",
        volume_db=-3.0,
        clips=[
            nested.Clip(
                id="demo:clip-vox",
                track_id="demo:track-vox",
                name="Vox Take",
                clip_type="audio",
                position_seconds=0.0,
                length_seconds=8.0,
                audio_file=SHARED_AUDIO,
                source_type="WAVE",
            )
        ],
        processors=[
            nested.Processor(
                id="demo:proc-eq",
                track_id="demo:track-vox",
                index=0,
                name="Channel EQ",
                family="EQ",
                parameters=[
                    nested.ProcessorParameter(
                        id="demo:param-gain",
                        processor_id="demo:proc-eq",
                        name="Gain",
                        value=gain,
                        unit="dB",
                    )
                ],
            )
        ],
    )


def _guitar() -> nested.Track:
    return nested.Track(
        id="demo:track-gtr",
        index=1,
        name="Rhythm Guitar",
        role="Guitar",
        volume_db=-5.0,
    )


def _drums() -> nested.Track:
    return nested.Track(
        id="demo:track-drums",
        index=2,
        name="Drum Kit",
        role="Drums",
        volume_db=-4.0,
    )


def _synth() -> nested.Track:
    return nested.Track(
        id="demo:track-synth",
        index=2,
        name="Pad Synth",
        role="Synth",
        volume_db=-6.0,
    )


def _reverb_return() -> nested.Track:
    return nested.Track(
        id="demo:return-verb",
        index=3,
        name="Reverb Return",
        kind="return",
    )


def _vox_to_verb_send() -> nested.Route:
    return nested.Route(
        id="demo:send-vox-verb",
        source_track_id="demo:track-vox",
        target_track_id="demo:return-verb",
        route_type="send",
        volume_db=-9.0,
    )


def _session(
    *,
    label: str,
    derived_from: str | None,
    tracks: list[nested.Track],
    routes: list[nested.Route] | None = None,
) -> nested.CanonicalSession:
    return nested.CanonicalSession(
        dialect=DIALECT,
        name=f"Demo Song {label}",
        tempo=120.0,
        time_signature="4/4",
        sample_rate=48000,
        tracks=tracks,
        routes=routes or [],
        variant_label=label,
        variant_family=FAMILY,
        derived_from_snapshot_id=derived_from,
    )


# (folder name, snapshot id, nested session) for each member.
VARIANTS: list[tuple[str, str, nested.CanonicalSession]] = [
    (
        "v1",
        V1_SID,
        _session(label="v1", derived_from=None, tracks=[_vox(0.5), _guitar()]),
    ),
    (
        "v2",
        V2_SID,
        _session(
            label="v2",
            derived_from=V1_SID,
            tracks=[_vox(0.5), _guitar(), _drums()],
        ),
    ),
    (
        "v2_alpha",
        V2A_SID,
        _session(
            label="v2_alpha",
            derived_from=V1_SID,
            tracks=[_vox(0.5), _guitar(), _synth()],
        ),
    ),
    (
        "v3",
        V3_SID,
        _session(
            label="v3",
            derived_from=V2_SID,
            tracks=[_vox(0.7), _guitar(), _drums(), _reverb_return()],
            routes=[_vox_to_verb_send()],
        ),
    ),
]


def build_source() -> SourceInfo:
    return SourceInfo(
        daw=DIALECT,
        daw_version=None,
        adapter="variants-synthetic-generator",
        adapter_version="0.1.0",
        capture_modes=["synthetic"],
    )


def _field(support: str = "FULL") -> FieldCapability:
    # Hand-built fixture: source stability is MANUAL and the capability is
    # UNTESTED against any real DAW. It demonstrates the contract shape.
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
        adapter="variants-synthetic-generator",
        adapter_version="0.1.0",
        read={
            "structure": DomainCapability(
                fields={"track_name": _field(), "variant": _field()}
            ),
            "routing": DomainCapability(fields={"sends": _field()}),
            "channel": DomainCapability(fields={"volume": _field()}),
            "processing": DomainCapability(fields={"insert_chain": _field()}),
        },
        notes=[
            "Synthetic variant family (demo_song): no DAW behind it. Exercises "
            "P8 variant grouping, lineage, and version diffing through the real "
            "flatten_session pipeline."
        ],
    )


def build_descriptor() -> AdapterDescriptor:
    return AdapterDescriptor(
        adapter_id="variants-synthetic-generator",
        daw=DIALECT,
        capture_modes=["synthetic"],
        read=(
            "Synthetic variant-family generator. Emits three-to-four snapshots "
            "of one song (a shared variant_family + labels + derived_from "
            "chaining) that genuinely differ by a track, a send, and a "
            "parameter, all referencing one shared audio asset."
        ),
        write="NONE",
        live_observation="NONE",
        render="NONE",
        known_limitations=[
            "Not a real DAW capture: every value is hand-authored to exercise "
            "the contract. Source stability is MANUAL throughout. Real "
            "per-version Logic families are Phase 4.",
        ],
    )


def main() -> None:
    source = build_source()
    capabilities = build_capabilities()
    descriptor = build_descriptor()

    for folder, snapshot_id, session in VARIANTS:
        snapshot = flatten_session(
            session, source, capabilities, snapshot_id=snapshot_id
        )
        report = validate_snapshot(snapshot)
        if report.errors:
            raise SystemExit(f"{folder} snapshot failed validation: {report.errors}")

        bundle_dir = FIXTURES_DIR / folder
        bundle_dir.mkdir(parents=True, exist_ok=True)

        def _write(name: str, payload: dict) -> None:
            (bundle_dir / name).write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )

        _write("canonical.snapshot.json", snapshot.model_dump())
        _write("capabilities.json", capabilities.model_dump())
        _write("adapter_descriptor.json", descriptor.model_dump())
        _write("validation.json", report.model_dump())

        print(
            f"wrote {folder} -> {bundle_dir}  "
            f"({len(snapshot.entities)} entities, "
            f"{len(snapshot.relationships)} relationships, valid={report.valid})"
        )


if __name__ == "__main__":
    main()
