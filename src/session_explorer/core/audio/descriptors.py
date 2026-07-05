"""Audio descriptor extraction (union of the REAPER, Ableton, and Logic prototypes).

By default this uses ``librosa`` to compute a small, interpretable set of acoustic
descriptors per audio file. Everything here is *optional and graceful*: if librosa
is unavailable, or a file cannot be read, the function returns an
:class:`AudioDescriptorSet` with ``available=False`` and a human-readable reason
instead of raising. The rest of the pipeline (parsing, graph, structural
recommendations) does not depend on audio being present.

The descriptors are intentionally modest — they characterise the *acoustic
outcome* of a file, not the DAW processing that produced it. We do not claim
mastering-grade loudness analysis; integrated loudness (LUFS) is computed only
when the optional ``pyloudnorm`` package is installed, and is otherwise left
unset. Alongside whole-file levels, the Logic prototype's silence-gated
``active_*`` levels are computed because full-song-length stems are mostly
silence outside their section: whole-file RMS measures arrangement density,
not level. When Essentia is installed (see :mod:`.essentia_adapter`), its
high-level descriptors land in ``extra`` and the typed
``spectral_complexity_mean`` / ``danceability`` fields.
"""

from __future__ import annotations

import math
import os
from typing import List, Optional

from ..ids import make_id
from ..models import AudioDescriptorSet
from .essentia_adapter import maybe_extract_highlevel

# --- optional backends, imported defensively --------------------------------
try:  # pragma: no cover - exercised implicitly by environment
    import librosa
    import numpy as np

    LIBROSA_AVAILABLE = True
    LIBROSA_IMPORT_ERROR: Optional[str] = None
except Exception as exc:  # pragma: no cover - environment dependent
    LIBROSA_AVAILABLE = False
    LIBROSA_IMPORT_ERROR = str(exc)

try:  # pragma: no cover - environment dependent
    import pyloudnorm as _pyln

    PYLOUDNORM_AVAILABLE = True
except Exception:  # pragma: no cover
    PYLOUDNORM_AVAILABLE = False

AUDIO_EXTENSIONS = {".wav", ".aif", ".aiff", ".flac", ".ogg", ".mp3", ".m4a"}

# Silence gate for the active_* level descriptors, in linear amplitude.
SILENCE_THRESHOLD = 10.0 ** (-60.0 / 20.0)  # -60 dBFS


def resolve_audio_path(
    source_file: Optional[str],
    project_dir: Optional[str] = None,
    base_dir: Optional[str] = None,
) -> Optional[str]:
    """Resolve a media source path to a real, existing file if possible.

    Resolution order (first hit wins):

    1. an absolute path that exists on disk;
    2. relative to the directory of the session/project file (when known);
    3. relative to a user-supplied base directory;
    4. base directory + just the file's basename (handles relocated stems).

    Returns ``None`` when nothing resolves, leaving the caller to record a warning.
    """

    if not source_file:
        return None

    candidate = source_file.replace("\\", "/")

    if os.path.isabs(candidate) and os.path.isfile(candidate):
        return candidate

    search_roots = [d for d in (project_dir, base_dir) if d]
    for root in search_roots:
        joined = os.path.join(root, candidate)
        if os.path.isfile(joined):
            return joined

    basename = os.path.basename(candidate)
    for root in search_roots:
        joined = os.path.join(root, basename)
        if os.path.isfile(joined):
            return joined

    if os.path.isfile(candidate):
        return candidate

    return None


def extract_descriptors(
    path: str,
    node_id: Optional[str] = None,
    *,
    source_id: Optional[str] = None,
    source_type: str = "file",
    file_name: Optional[str] = None,
    estimate_tempo: bool = True,
) -> AudioDescriptorSet:
    """Compute descriptors for a single audio file.

    Always returns an :class:`AudioDescriptorSet`; never raises. When the audio
    backend is missing or the file is unreadable, ``available`` is ``False`` and
    ``unavailable_reason`` explains why. Per-feature failures degrade to entries
    in ``warnings`` — surfaced, not hidden — so a single fragile descriptor
    never discards the rest.
    """

    result = AudioDescriptorSet(
        id=make_id("descriptor"),
        node_id=node_id,
        source_id=source_id,
        source_type=source_type,
        file_path=path,
        file_name=file_name or os.path.splitext(os.path.basename(path))[0],
    )

    if not LIBROSA_AVAILABLE:
        result.unavailable_reason = (
            "librosa is not installed; install the 'audio' extra to enable "
            f"descriptor extraction. ({LIBROSA_IMPORT_ERROR})"
        )
        return result

    if not os.path.isfile(path):
        result.unavailable_reason = "Audio file path not found."
        return result

    try:
        # Load in the file's original channel layout: loudness (BS.1770), peak,
        # and stereo width must be measured on the real channels, not a mono
        # downmix.
        y_raw, sr = librosa.load(path, sr=None, mono=False)
    except Exception as exc:
        result.unavailable_reason = f"Could not read audio file: {exc}"
        return result

    if y_raw is None or y_raw.size == 0:
        result.unavailable_reason = "Audio file is empty."
        return result

    result.available = True
    result.sample_rate = int(sr)
    result.duration_seconds = _f(y_raw.shape[-1] / sr)

    # Spectral/temporal features are computed on a mono mix; y_raw keeps the
    # channel layout for peak, loudness, and width. Remove DC so an offset does
    # not register as activity or crush the crest figure (BS.1770 loudness has
    # its own highpass; sample peak legitimately includes DC).
    y = np.mean(y_raw, axis=0) if y_raw.ndim > 1 else y_raw
    y = y - float(np.mean(y))

    try:
        rms = librosa.feature.rms(y=y)[0]
        result.rms_mean = _f(np.mean(rms))
        result.rms_std = _f(np.std(rms))

        # Silence-gated level: full-song-length stem exports leave a part that
        # plays in one section mostly silent, so whole-file RMS measures
        # arrangement density, not level. Gate at -60 dBFS.
        active = rms > SILENCE_THRESHOLD
        result.activity_ratio = _f(np.mean(active))
        if active.any():
            result.active_rms_mean = _f(np.mean(rms[active]))
            if result.duration_seconds:
                result.active_duration_seconds = _f(
                    float(np.mean(active)) * result.duration_seconds
                )
    except Exception as exc:
        result.warnings.append(f"RMS failed ({exc}).")

    try:
        peak = float(np.max(np.abs(y_raw)))
        result.peak_amplitude = _f(peak)
        # Rough crest-factor style dynamic-range proxy in dB, whole-file and
        # silence-gated. The gated variant is the meaningful one for sparse
        # stems (silence inflates the whole-file figure).
        if result.rms_mean and result.rms_mean > 0 and peak > 0:
            result.dynamic_range_db = _f(20.0 * math.log10(peak / result.rms_mean))
        if result.active_rms_mean and result.active_rms_mean > 0 and peak > 0:
            result.dynamic_range_active_db = _f(
                20.0 * math.log10(peak / result.active_rms_mean)
            )
    except Exception as exc:
        result.warnings.append(f"Peak/dynamic-range failed ({exc}).")

    # Stereo width: RMS of the side signal relative to the mid signal.
    # 0 = dual-mono, ~1 = fully decorrelated; direct observable evidence of
    # printed stereo processing (reverbs, wideners, true-stereo sources).
    try:
        if y_raw.ndim > 1 and y_raw.shape[0] == 2:
            mid = (y_raw[0] + y_raw[1]) / 2.0
            side = (y_raw[0] - y_raw[1]) / 2.0
            mid_rms = float(np.sqrt(np.mean(mid**2)))
            side_rms = float(np.sqrt(np.mean(side**2)))
            if mid_rms > 0:
                result.stereo_width_ratio = _f(side_rms / mid_rms)
            elif side_rms > 0:
                result.warnings.append(
                    "Channels are exactly out of phase (no mid signal); stereo "
                    "width ratio is undefined."
                )
    except Exception as exc:
        result.warnings.append(f"Stereo width failed ({exc}).")

    try:
        result.spectral_centroid_mean = _f(
            np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
        )
        result.spectral_bandwidth_mean = _f(
            np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr))
        )
        result.spectral_rolloff_mean = _f(
            np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr))
        )
    except Exception as exc:
        result.warnings.append(f"Spectral descriptors failed ({exc}).")

    try:
        result.zero_crossing_rate_mean = _f(
            np.mean(librosa.feature.zero_crossing_rate(y=y))
        )
    except Exception as exc:
        result.warnings.append(f"Zero-crossing-rate failed ({exc}).")

    try:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        result.onset_strength_mean = _f(np.mean(onset_env))
        if estimate_tempo:
            # librosa 0.10+ lazy-loads submodules; librosa.feature.rhythm must
            # be imported explicitly or the tempo call raises AttributeError.
            import librosa.feature.rhythm

            tempo = librosa.feature.rhythm.tempo(onset_envelope=onset_env, sr=sr)
            result.estimated_tempo = _f(
                tempo[0] if hasattr(tempo, "__len__") else tempo
            )
    except Exception as exc:
        # Tempo estimation can be unstable on very short / tonal stems.
        result.warnings.append(f"Onset/tempo failed ({exc}).")

    # Optional true loudness measurement (BS.1770 via pyloudnorm), on the
    # file's original channel layout — pyloudnorm expects (samples, channels).
    if PYLOUDNORM_AVAILABLE:
        result.integrated_loudness_lufs = _integrated_loudness(y_raw, sr)

    # Optional Essentia high-level descriptors: the raw dict lands in ``extra``
    # and the couple of typed fields the prototypes surfaced are promoted.
    try:
        extra = maybe_extract_highlevel(path)
        if extra:
            result.extra.update(extra)
            if result.danceability is None and "essentia_danceability" in extra:
                result.danceability = _f(extra["essentia_danceability"])
            if (
                result.spectral_complexity_mean is None
                and "essentia_spectral_complexity_mean" in extra
            ):
                result.spectral_complexity_mean = _f(
                    extra["essentia_spectral_complexity_mean"]
                )
    except Exception as exc:  # pragma: no cover - defensive
        result.warnings.append(f"Essentia descriptors failed ({exc}).")

    return result


def extract_many(items: List[tuple]) -> List[AudioDescriptorSet]:
    """Convenience: extract for a list of ``(path, node_id)`` tuples."""

    return [extract_descriptors(path, node_id) for path, node_id in items]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _f(value) -> Optional[float]:
    """Round to 6 places, mapping unparseable / non-finite values to ``None``."""

    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 6)


def _integrated_loudness(y_raw, sr) -> Optional[float]:
    try:  # pragma: no cover - optional dependency
        meter = _pyln.Meter(sr)
        loudness_input = y_raw.T if y_raw.ndim > 1 else y_raw
        loudness = meter.integrated_loudness(loudness_input)
        if loudness == float("-inf"):
            return None
        return round(float(loudness), 2)
    except Exception:
        # Silently leave as None: absence of loudness is expected, not an error.
        return None
