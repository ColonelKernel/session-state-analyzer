"""Generate the ``parameter_change`` experiment fixture — deterministically.

Run from the repo root with the analyzer venv::

    .venv/bin/python fixtures/experiments/parameter_change/make_inputs.py

It writes two canonical bundles (``before`` / ``after``) that are identical
except for one delay **FEEDBACK** ``PARAMETER`` (0.2 → 0.7), built via the REAL
``flatten_session`` + ``validate_snapshot`` so they cannot drift from the
contract, plus two REAL delay-line render descriptors (a feedback comb applied
at 0.2 vs 0.7). The WAVs are synthesised, measured with the analyzer's own
``extract_descriptors``, and discarded — descriptors travel, WAVs do not.

Honesty note: this is a SYNTHETIC fixture. Cubase VST3 plug-in parameters are
opaque (an added feedback change would be HIDDEN there), so the observable path
is modelled on REAPER JS-plugin parameters and the audio is fixture-generated,
not printed from a human performance.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from canonical_snapshot import SourceInfo, flatten_session, nested, validate_snapshot

from session_explorer.core.audio.descriptors import extract_descriptors

HERE = Path(__file__).resolve().parent

SR = 44100
DUR_S = 2.0
N = int(SR * DUR_S)  # 88_200
DELAY_S = 0.13
CREATED_AT = "2026-07-07T00:00:00+00:00"

FEEDBACK_LOW = 0.2
FEEDBACK_HIGH = 0.7


# ---------------------------------------------------------------------------
# Canonical bundles (real flatten_session + validate_snapshot)
# ---------------------------------------------------------------------------


def build_session(feedback: float) -> nested.CanonicalSession:
    """A vocal track → a Delay processor carrying one Feedback parameter."""
    vox = nested.Track(
        id="reaper:track-vox",
        index=0,
        name="Lead Vox",
        kind="audio",
        role="Vocal",
        volume_db=-1.4,
        pan=0.0,
        field_provenance={
            "role": nested.inferred(
                "role 'Vocal' inferred from track name 'Lead Vox'", confidence=0.6
            )
        },
        processors=[
            nested.Processor(
                id="reaper:fx-delay",
                track_id="reaper:track-vox",
                index=0,
                name="Delay",
                kind="JS",
                family="Delay",
                enabled=True,
                parameters=[
                    nested.ProcessorParameter(
                        id="reaper:fx-delay:feedback",
                        processor_id="reaper:fx-delay",
                        name="Feedback",
                        value=feedback,
                        normalized_value=feedback,
                        unit="",
                        is_visible_to_host=True,
                    ),
                ],
            )
        ],
    )
    master = nested.Track(
        id="reaper:track-master",
        index=0,
        name="Master",
        kind="master",
        volume_db=0.0,
    )
    return nested.CanonicalSession(
        dialect="reaper",
        name="delay_feedback",
        source_file="fixtures/reaper/delay_feedback.rpp",
        tempo=120.0,
        time_signature="4/4",
        sample_rate=SR,
        tracks=[vox, master],
        routes=[
            nested.Route(
                id="reaper:route-vox-master",
                source_track_id="reaper:track-vox",
                target_track_id="reaper:track-master",
                route_type="output",
                volume_db=0.0,
            )
        ],
    )


def flatten(session: nested.CanonicalSession):
    source = SourceInfo(
        daw="reaper",
        daw_version="7.25",
        adapter="reaper-session-state-explorer",
        adapter_version="0.1.0",
        capture_modes=["rpp_file"],
    )
    snap = flatten_session(session, source, created_at=CREATED_AT)
    # Content-hash snapshot id (independent of snapshot_id/created_at) so the
    # before/after ids differ by the one changed value and nothing else.
    digest_src = json.dumps(
        {
            "entities": [e.model_dump() for e in snap.entities],
            "relationships": [r.model_dump() for r in snap.relationships],
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()[:12]
    snap.snapshot_id = f"reaper:delay_feedback:{digest}"
    return snap


def write_bundle(dir_path: Path, snap) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    payload = snap.model_dump()
    report = validate_snapshot(payload)
    assert report.valid, f"{dir_path} did not validate: {report.errors}"
    (dir_path / "canonical.snapshot.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (dir_path / "validation.json").write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Real delay-line renders
# ---------------------------------------------------------------------------


def make_delay_render(feedback: float) -> np.ndarray:
    """A broadband excitation through an overlapping feedback comb.

    ``y[k] = dry[k] + fb·y[k-D]`` with a delay (0.13 s) shorter than the 1.0 s
    excitation, so echoes overlap and their (uncorrelated) energy accumulates:
    higher feedback ⇒ a louder sustained bed *and* a longer tail, which raises
    RMS, peak, and gated loudness together. A fixed RNG seed keeps it
    deterministic; the dry amplitude is low enough that the safety guard below
    never fires (so the honest amplitude relationship is preserved, not
    normalised away).
    """
    rng = np.random.default_rng(20260707)
    sustain = int(1.0 * SR)
    fade = int(0.02 * SR)
    env = np.zeros(N, dtype=np.float64)
    env[:sustain] = 0.06
    env[:fade] *= np.linspace(0.0, 1.0, fade)
    env[sustain - fade : sustain] *= np.linspace(1.0, 0.0, fade)
    dry = rng.standard_normal(N) * env

    delay = int(DELAY_S * SR)
    y = dry.copy()
    for k in range(delay, N):
        y[k] += feedback * y[k - delay]

    peak = float(np.max(np.abs(y)))
    if peak > 0.98:  # numerical safety; does not fire for these low amplitudes
        y *= 0.98 / peak
    return y.astype(np.float32)


def descriptor_for(y: np.ndarray, name: str):
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / f"{name}.wav"
        sf.write(str(wav), y, SR)
        d = extract_descriptors(
            str(wav),
            node_id=f"render:{name}",
            source_id=f"render:{name}",
            source_type="mixdown",
            file_name=name,
        )
    # Freeze the identity fields (extract_descriptors mints a fresh id) and drop
    # the temp path, matching the effect_send descriptor shape exactly.
    d.id = f"descriptor:{name}"
    d.file_path = None
    return d


def main() -> None:
    before_snap = flatten(build_session(FEEDBACK_LOW))
    after_snap = flatten(build_session(FEEDBACK_HIGH))
    write_bundle(HERE / "before", before_snap)
    write_bundle(HERE / "after", after_snap)

    renders_dir = HERE / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)
    for name, fb in (("routing_a", FEEDBACK_LOW), ("routing_b", FEEDBACK_HIGH)):
        d = descriptor_for(make_delay_render(fb), name)
        (renders_dir / f"{name}.descriptors.json").write_text(
            json.dumps(d.model_dump(), indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"{name}: fb={fb}  rms={d.rms_mean}  lufs={d.integrated_loudness_lufs}"
            f"  peak={d.peak_amplitude}"
        )

    print("before snapshot_id:", before_snap.snapshot_id)
    print("after  snapshot_id:", after_snap.snapshot_id)


if __name__ == "__main__":
    main()
