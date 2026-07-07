"""Generate the modulation bundle from the real contract pipeline.

A *synthetic* fixture whose only job is to carry one **ANNOTATED** modulation
source, so the Observability Atlas's Modulation row — which is NOT_APPLICABLE
across every real adapter (none observe modulation) — flips to *measured*
somewhere, proving the row is a real measurement channel and not dead UI.

The scenario is the canonical one: a **sidechain** where a kick channel's
signal modulates a bass channel's gain (classic ducking). It is a user
*assertion* about intent, never state read from a DAW — hence ANNOTATED. It is
run through the real ``flatten_session`` + ``validate_snapshot`` so it cannot
drift.

Run from anywhere:

    python fixtures/modulation/inputs/make_inputs.py
"""

from __future__ import annotations

import json
from pathlib import Path

from canonical_snapshot import (
    AdapterDescriptor,
    CapabilityManifest,
    SourceInfo,
    flatten_session,
    nested,
    validate_snapshot,
)

HERE = Path(__file__).resolve().parent
BUNDLE_DIR = HERE.parent / "bundles" / "synthetic"

DIALECT = "synthetic"
SESSION_NAME = "Sidechain Modulation"


def build_session() -> nested.CanonicalSession:
    return nested.CanonicalSession(
        dialect=DIALECT,
        name=SESSION_NAME,
        tempo=128.0,
        time_signature="4/4",
        sample_rate=48000,
        tracks=[
            nested.Track(id="synthetic:track-kick", index=0, name="Kick", role="Drums"),
            nested.Track(id="synthetic:track-bass", index=1, name="Bass", role="Bass"),
        ],
        modulation=[
            nested.Modulation(
                id="synthetic:mod-duck",
                source_type="sidechain",
                parameter_name="gain",
                source_track_id="synthetic:track-kick",
                target_track_id="synthetic:track-bass",
                target_channel_field="gain",
                depth=-8.0,
                rate=None,
                unit="dB",
                # User assertion about the intended ducking, never observed
                # from a project file -> ANNOTATED.
                provenance=nested.annotation(
                    "Kick sidechains the bass gain (ducking) — asserted, not "
                    "observed from any DAW.",
                    confidence=0.6,
                ),
            )
        ],
    )


def build_source() -> SourceInfo:
    return SourceInfo(
        daw=DIALECT,
        adapter="modulation-synthetic-generator",
        adapter_version="0.1.0",
        capture_modes=["synthetic"],
    )


def build_capabilities() -> CapabilityManifest:
    # No modulation read-capability is declared: the atlas Modulation row has
    # no capability mapping at all, so the cell is measured purely from the
    # ANNOTATED MODULATION entity present in this capture.
    return CapabilityManifest(
        daw=DIALECT,
        adapter="modulation-synthetic-generator",
        adapter_version="0.1.0",
        notes=[
            "Synthetic fixture carrying one ANNOTATED sidechain modulation so "
            "the atlas Modulation row is measured somewhere."
        ],
    )


def build_descriptor() -> AdapterDescriptor:
    return AdapterDescriptor(
        adapter_id="modulation-synthetic-generator",
        daw=DIALECT,
        capture_modes=["synthetic"],
        read="Synthetic session carrying one ANNOTATED sidechain modulation.",
        write="NONE",
        live_observation="NONE",
        render="NONE",
        known_limitations=[
            "Not a real DAW capture. The modulation is a user assertion "
            "(ANNOTATED), not observed state.",
        ],
    )


def main() -> None:
    session = build_session()
    snapshot = flatten_session(session, build_source(), build_capabilities())
    report = validate_snapshot(snapshot)
    if report.errors:
        raise SystemExit(f"modulation snapshot failed validation: {report.errors}")

    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    def _write(name: str, payload: dict) -> None:
        (BUNDLE_DIR / name).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    _write("canonical.snapshot.json", snapshot.model_dump())
    _write("capabilities.json", build_capabilities().model_dump())
    _write("adapter_descriptor.json", build_descriptor().model_dump())
    _write("validation.json", report.model_dump())

    mods = snapshot.entities_of_type("MODULATION")
    print(f"wrote bundle -> {BUNDLE_DIR}")
    print(f"  {len(snapshot.entities)} entities, {len(mods)} MODULATION, valid={report.valid}")


if __name__ == "__main__":
    main()
