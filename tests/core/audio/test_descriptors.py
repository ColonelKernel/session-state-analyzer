"""Descriptor extraction tests (adapted from the Logic prototype suite).

The audio backend is optional: tests that need librosa/soundfile skip when it
is absent, while the graceful-degradation and path-resolution tests run
everywhere — the module must import and behave without any audio dependency.
"""

import math
import struct
import wave

import pytest

from session_explorer.core import ids
from session_explorer.core.audio import descriptors

requires_librosa = pytest.mark.skipif(
    not descriptors.LIBROSA_AVAILABLE, reason="librosa not installed"
)


def _write_stereo_wav(path, *, seconds=1.0, sr=22050, left_gain=0.5, right_gain=0.5):
    n = int(seconds * sr)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            t = i / sr
            left = left_gain * math.sin(2 * math.pi * 440 * t)
            right = right_gain * math.sin(2 * math.pi * 440 * t)
            frames += struct.pack("<hh", int(left * 32767), int(right * 32767))
        wf.writeframes(bytes(frames))


def _write_mono_wav(path, *, freq=440.0, seconds=1.0, sr=22050, gain=0.5):
    n = int(seconds * sr)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            s = gain * math.sin(2 * math.pi * freq * i / sr)
            frames += struct.pack("<h", int(s * 32767))
        wf.writeframes(bytes(frames))


def _write_click_track(path, *, sr=44100, duration=3.0, bpm=120.0):
    """Write a WAV of short clicks at a fixed tempo."""
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    y = np.zeros(int(sr * duration), dtype=np.float32)
    click = np.hanning(256).astype(np.float32)
    step = int(sr * 60.0 / bpm)
    for start in range(0, len(y) - len(click), step):
        y[start : start + len(click)] += click
    sf.write(str(path), y, sr)


# ---------------------------------------------------------------------------
# Graceful degradation and path resolution: run without any audio backend
# ---------------------------------------------------------------------------


def test_module_imports_and_exposes_api_without_audio_backends():
    # The audio package must import fine without librosa/soundfile/pyloudnorm.
    from session_explorer.core import audio

    assert callable(audio.extract_descriptors)
    assert callable(audio.extract_many)
    assert callable(audio.resolve_audio_path)
    assert callable(audio.maybe_extract_highlevel)


def test_missing_backend_yields_unavailable_not_crash(monkeypatch, tmp_path):
    monkeypatch.setattr(descriptors, "LIBROSA_AVAILABLE", False)
    monkeypatch.setattr(descriptors, "LIBROSA_IMPORT_ERROR", "simulated absence")
    wav = tmp_path / "tone.wav"
    _write_mono_wav(wav)

    desc = descriptors.extract_descriptors(str(wav), node_id="audio-1")

    assert desc.available is False
    assert "librosa" in (desc.unavailable_reason or "")
    assert desc.node_id == "audio-1"
    assert desc.file_path == str(wav)


def test_extract_many_returns_one_set_per_item(monkeypatch):
    monkeypatch.setattr(descriptors, "LIBROSA_AVAILABLE", False)
    monkeypatch.setattr(descriptors, "LIBROSA_IMPORT_ERROR", "simulated absence")

    results = descriptors.extract_many([("a.wav", "audio-0"), ("b.wav", "audio-1")])

    assert [d.node_id for d in results] == ["audio-0", "audio-1"]
    assert all(d.available is False for d in results)


def test_resolve_audio_path_absolute(tmp_path):
    wav = tmp_path / "tone.wav"
    _write_mono_wav(wav)
    assert descriptors.resolve_audio_path(str(wav)) == str(wav)


def test_resolve_audio_path_relative_to_project_dir(tmp_path):
    (tmp_path / "Audio").mkdir()
    wav = tmp_path / "Audio" / "stem.wav"
    _write_mono_wav(wav)
    resolved = descriptors.resolve_audio_path("Audio/stem.wav", project_dir=str(tmp_path))
    assert resolved == str(wav)


def test_resolve_audio_path_basename_fallback_handles_relocated_stems(tmp_path):
    wav = tmp_path / "stem.wav"
    _write_mono_wav(wav)
    # The session references a directory layout that no longer exists.
    resolved = descriptors.resolve_audio_path(
        "C:\\old\\project\\Audio\\stem.wav", base_dir=str(tmp_path)
    )
    assert resolved == str(wav)


def test_resolve_audio_path_unresolvable_returns_none(tmp_path):
    assert descriptors.resolve_audio_path("missing.wav", base_dir=str(tmp_path)) is None
    assert descriptors.resolve_audio_path(None) is None
    assert descriptors.resolve_audio_path("") is None


@requires_librosa
def test_missing_file_reports_reason():
    desc = descriptors.extract_descriptors("/nonexistent/never.wav")
    assert desc.available is False
    assert desc.unavailable_reason == "Audio file path not found."


# ---------------------------------------------------------------------------
# Signal descriptors (require librosa)
# ---------------------------------------------------------------------------


@requires_librosa
def test_stereo_file_duration_uses_samples_not_channels(tmp_path):
    ids.reset_id_counters()
    path = tmp_path / "stereo_tone.wav"
    _write_stereo_wav(path, seconds=1.0)
    desc = descriptors.extract_descriptors(
        str(path), source_id="audio_test", estimate_tempo=False
    )
    # A (2, n) channel-first array must not be read as 2 samples long.
    assert desc.available is True
    assert desc.duration_seconds == pytest.approx(1.0, abs=0.01)
    assert desc.sample_rate == 22050
    assert desc.peak_amplitude == pytest.approx(0.5, abs=0.02)
    assert desc.rms_mean is not None


@requires_librosa
def test_stereo_loudness_measured_on_real_channels(tmp_path):
    pyln = pytest.importorskip("pyloudnorm")  # noqa: F841
    ids.reset_id_counters()
    # One channel silent: a mono (L+R)/2 downmix would read ~6 dB lower than
    # the true BS.1770 stereo measurement of this signal.
    quiet_right = tmp_path / "one_sided.wav"
    _write_stereo_wav(quiet_right, left_gain=0.5, right_gain=0.0)
    both = tmp_path / "both_sides.wav"
    _write_stereo_wav(both, left_gain=0.5, right_gain=0.5)

    desc_one = descriptors.extract_descriptors(
        str(quiet_right), source_id="a1", estimate_tempo=False
    )
    desc_both = descriptors.extract_descriptors(
        str(both), source_id="a2", estimate_tempo=False
    )
    assert desc_one.integrated_loudness_lufs is not None
    assert desc_both.integrated_loudness_lufs is not None
    # BS.1770 sums channel energies: both-channel signal reads ~3 dB louder
    # than the one-channel signal. A mono downmix would report ~6 dB.
    delta = desc_both.integrated_loudness_lufs - desc_one.integrated_loudness_lufs
    assert delta == pytest.approx(3.0, abs=0.5)


@requires_librosa
def test_silence_gated_levels_ignore_arrangement_density(tmp_path):
    # A stem that plays loud for 25% of the file and is silent otherwise:
    # whole-file RMS is dragged down by silence; active RMS is not.
    sr = 22050
    n = sr * 2
    path = tmp_path / "sparse_loud.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            s = 0.8 * math.sin(2 * math.pi * 220 * i / sr) if i < n // 4 else 0.0
            frames += struct.pack("<h", int(s * 32767))
        wf.writeframes(bytes(frames))

    desc = descriptors.extract_descriptors(
        str(path), source_id="a1", estimate_tempo=False
    )
    assert desc.activity_ratio is not None
    assert desc.activity_ratio == pytest.approx(0.25, abs=0.05)
    assert desc.active_rms_mean > desc.rms_mean * 2
    assert desc.active_duration_seconds == pytest.approx(0.5, abs=0.1)
    # Gated crest reflects the playing signal, not the silence.
    assert desc.dynamic_range_active_db < desc.dynamic_range_db


@requires_librosa
def test_stereo_width_ratio(tmp_path):
    identical = tmp_path / "mono_ish.wav"
    _write_stereo_wav(identical, left_gain=0.5, right_gain=0.5)
    one_sided = tmp_path / "wide.wav"
    _write_stereo_wav(one_sided, left_gain=0.5, right_gain=0.0)

    narrow = descriptors.extract_descriptors(
        str(identical), source_id="a1", estimate_tempo=False
    )
    wide = descriptors.extract_descriptors(
        str(one_sided), source_id="a2", estimate_tempo=False
    )
    assert narrow.stereo_width_ratio == pytest.approx(0.0, abs=0.01)
    assert wide.stereo_width_ratio == pytest.approx(1.0, abs=0.05)


@requires_librosa
def test_mono_file_still_works(tmp_path):
    ids.reset_id_counters()
    path = tmp_path / "mono_tone.wav"
    _write_mono_wav(path, freq=440.0, seconds=1.0)
    desc = descriptors.extract_descriptors(
        str(path), source_id="audio_test", estimate_tempo=False
    )
    assert desc.duration_seconds == pytest.approx(1.0, abs=0.01)
    assert desc.rms_mean is not None
    assert desc.peak_amplitude is not None


@requires_librosa
def test_tempo_estimated_without_onset_warning(tmp_path):
    # Regression: librosa 0.10+ lazy-loads librosa.feature.rhythm, so tempo
    # estimation raised AttributeError and every descriptor carried an
    # "Onset/tempo failed" warning.
    ids.reset_id_counters()
    wav = tmp_path / "click.wav"
    _write_click_track(wav)

    descriptor = descriptors.extract_descriptors(str(wav), source_id="src-1")

    assert descriptor.estimated_tempo is not None
    assert not any("Onset/tempo failed" in w for w in descriptor.warnings)


@requires_librosa
def test_descriptors_extracted_from_click_track(tmp_path):
    ids.reset_id_counters()
    wav = tmp_path / "click.wav"
    _write_click_track(wav)

    descriptor = descriptors.extract_descriptors(str(wav), source_id="src-1")

    assert descriptor.available is True
    assert descriptor.sample_rate == 44100
    assert descriptor.duration_seconds == pytest.approx(3.0, abs=0.01)
    assert descriptor.rms_mean is not None
    assert descriptor.onset_strength_mean is not None
