"""Stem-sum reconciliation and reference comparison tests (from the Logic suite).

All tests here operate on synthesized WAV files, so the whole module skips
when librosa is not installed — matching the source suite's property that the
package works (and its other tests pass) without any audio backend.
"""

import math
import struct
import wave

import pytest

pytest.importorskip("librosa")
np = pytest.importorskip("numpy")

from session_explorer.core import ids  # noqa: E402
from session_explorer.core.audio import signal_comparisons  # noqa: E402
from session_explorer.core.models import AudioDescriptorSet  # noqa: E402


def _write_wav(path, samples, sr=22050):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples
        )
        wf.writeframes(frames)


def _tone(freq, seconds=1.0, sr=22050, gain=0.3):
    n = int(seconds * sr)
    return [gain * math.sin(2 * math.pi * freq * t / sr) for t in range(n)]


@pytest.fixture
def perfect_session(tmp_path):
    """Two stems whose exact sum is the mixdown."""

    ids.reset_id_counters()
    bass = _tone(110, gain=0.3)
    lead = _tone(880, gain=0.2)
    mix = [a + b for a, b in zip(bass, lead)]
    paths = {}
    for name, samples in [("bass.wav", bass), ("lead.wav", lead), ("mix.wav", mix)]:
        p = tmp_path / name
        _write_wav(p, samples)
        paths[name] = str(p)
    return paths


def test_perfect_stem_sum_has_low_residual(perfect_session):
    result = signal_comparisons.reconcile_stem_sum(
        {"audio_1": perfect_session["bass.wav"], "audio_2": perfect_session["lead.wav"]},
        perfect_session["mix.wav"],
        mixdown_audio_id="audio_3",
    )
    assert result.residual_db is not None
    assert result.residual_db < -30  # 16-bit quantisation bounds perfection
    assert result.correlation > 0.99
    assert result.fitted_gain == pytest.approx(1.0, abs=0.05)
    assert "closely" in result.interpretation


def test_processed_mixdown_has_high_residual(perfect_session, tmp_path):
    # A mixdown with substantial content the stems do not contain.
    extra = _tone(3000, gain=0.4)
    bass = _tone(110, gain=0.3)
    lead = _tone(880, gain=0.2)
    mix = [a + b + c for a, b, c in zip(bass, lead, extra)]
    mix_path = tmp_path / "mix_processed.wav"
    _write_wav(mix_path, mix)
    result = signal_comparisons.reconcile_stem_sum(
        {"audio_1": perfect_session["bass.wav"], "audio_2": perfect_session["lead.wav"]},
        str(mix_path),
        mixdown_audio_id="audio_3",
    )
    assert result.residual_db > -20
    # The residual concentrates in the band containing the extra content.
    assert result.band_residuals_db
    worst_band = max(result.band_residuals_db.items(), key=lambda kv: kv[1])[0]
    assert worst_band == "2000-4000Hz"


def test_duration_mismatch_warns(perfect_session, tmp_path):
    short = _tone(110, seconds=0.5)
    short_path = tmp_path / "short.wav"
    _write_wav(short_path, short)
    result = signal_comparisons.reconcile_stem_sum(
        {"audio_1": str(short_path), "audio_2": perfect_session["lead.wav"]},
        perfect_session["mix.wav"],
        mixdown_audio_id="audio_3",
    )
    assert any("duration differs" in w for w in result.warnings)


def test_reference_comparison_same_file_is_flat(perfect_session):
    result = signal_comparisons.compare_to_reference(
        perfect_session["mix.wav"], perfect_session["mix.wav"],
        mixdown_audio_id="audio_3", reference_id="ref_1",
    )
    assert result.band_deltas_db
    assert all(abs(v) < 0.1 for v in result.band_deltas_db.values())


def test_reference_comparison_detects_band_shift(perfect_session, tmp_path):
    # Reference is bass-heavy relative to the mixdown -> the mixdown shows
    # proportionally less low energy (negative delta in the low band).
    ref = [a + b for a, b in zip(_tone(110, gain=0.6), _tone(880, gain=0.05))]
    ref_path = tmp_path / "ref.wav"
    _write_wav(ref_path, ref)
    result = signal_comparisons.compare_to_reference(
        perfect_session["mix.wav"], str(ref_path),
        mixdown_audio_id="audio_3", reference_id="ref_1",
    )
    low = result.band_deltas_db.get("60-120Hz")
    assert low is not None and low < 0
    assert result.summary


def test_duration_warning_blames_only_the_short_stem(perfect_session, tmp_path):
    # A short stem must not make later full-length stems look mismatched,
    # regardless of iteration order.
    short = _tone(110, seconds=0.5)
    short_path = tmp_path / "short.wav"
    _write_wav(short_path, short)
    for order in (
        {"stem_short": str(short_path), "stem_full": perfect_session["lead.wav"]},
        {"stem_full": perfect_session["lead.wav"], "stem_short": str(short_path)},
    ):
        result = signal_comparisons.reconcile_stem_sum(
            order, perfect_session["mix.wav"], mixdown_audio_id="mix"
        )
        blamed = [w for w in result.warnings if "duration differs" in w]
        assert len(blamed) == 1
        assert "stem_short" in blamed[0]


def test_zero_crest_delta_is_preserved(perfect_session):
    # Identical gated crests (delta 0.0) must not fall through to the
    # whole-file crest delta.
    mix_d = AudioDescriptorSet(id="d1", source_id="a1",
                               dynamic_range_active_db=10.0, dynamic_range_db=30.0)
    ref_d = AudioDescriptorSet(id="d2", source_id="a2",
                               dynamic_range_active_db=10.0, dynamic_range_db=12.0)
    result = signal_comparisons.compare_to_reference(
        perfect_session["mix.wav"], perfect_session["mix.wav"],
        mixdown_audio_id="a1", reference_id="a2",
        mixdown_descriptor=mix_d, reference_descriptor=ref_d,
    )
    assert result.crest_delta_db == 0.0


def test_band_deltas_are_bounded_in_empty_bands(perfect_session, tmp_path):
    # Reference with essentially no high-frequency energy: the delta in that
    # band must be clamped, not an absurd headline number.
    result = signal_comparisons.compare_to_reference(
        perfect_session["mix.wav"], perfect_session["mix.wav"],
        mixdown_audio_id="a1", reference_id="ref",
    )
    assert all(abs(v) <= 40.0 for v in result.band_deltas_db.values())

    bright = [a + b for a, b in zip(_tone(880, gain=0.2), _tone(6000, gain=0.4))]
    bright_path = tmp_path / "bright.wav"
    _write_wav(bright_path, bright)
    result = signal_comparisons.compare_to_reference(
        str(bright_path), perfect_session["mix.wav"],
        mixdown_audio_id="a1", reference_id="ref",
    )
    high = result.band_deltas_db.get("4000-8000Hz")
    assert high is not None and 0 < high <= 40.0


def test_brickwalled_mixdown_residual_band_still_reported(perfect_session, tmp_path):
    # Mixdown missing content the stems have (e.g. muted track at bounce):
    # the guilty band must appear with a large positive residual.
    bass = _tone(110, gain=0.3)
    lead = _tone(880, gain=0.2)
    high = _tone(6000, gain=0.3)
    mix_without_high = [a + b for a, b in zip(bass, lead)]
    high_path = tmp_path / "high_stem.wav"
    mix_path = tmp_path / "mix_no_high.wav"
    _write_wav(high_path, high)
    _write_wav(mix_path, mix_without_high)
    result = signal_comparisons.reconcile_stem_sum(
        {
            "a1": perfect_session["bass.wav"],
            "a2": perfect_session["lead.wav"],
            "a3": str(high_path),
        },
        str(mix_path),
        mixdown_audio_id="mix",
    )
    assert result.band_residuals_db.get("4000-8000Hz") is not None
    assert result.band_residuals_db["4000-8000Hz"] > 0


def test_reconciliation_survives_missing_file(perfect_session):
    result = signal_comparisons.reconcile_stem_sum(
        {"audio_1": "/nonexistent/never.wav"},
        perfect_session["mix.wav"],
        mixdown_audio_id="audio_3",
    )
    assert result.warnings
    assert result.residual_db is None
