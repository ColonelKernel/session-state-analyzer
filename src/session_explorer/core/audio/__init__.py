"""Shared audio analysis: descriptors, optional Essentia extras, and signal
comparisons.

Everything in this package is optional and graceful: the modules import (and
the pipeline runs) without librosa, soundfile, pyloudnorm, or Essentia
installed; missing backends surface as ``available=False`` reasons or
warnings, never as crashes.
"""

from .descriptors import (
    AUDIO_EXTENSIONS,
    LIBROSA_AVAILABLE,
    PYLOUDNORM_AVAILABLE,
    extract_descriptors,
    extract_many,
    resolve_audio_path,
)
from .essentia_adapter import ESSENTIA_AVAILABLE, maybe_extract_highlevel
from .signal_comparisons import (
    OCTAVE_BANDS,
    compare_to_reference,
    reconcile_stem_sum,
)

__all__ = [
    "AUDIO_EXTENSIONS",
    "ESSENTIA_AVAILABLE",
    "LIBROSA_AVAILABLE",
    "OCTAVE_BANDS",
    "PYLOUDNORM_AVAILABLE",
    "compare_to_reference",
    "extract_descriptors",
    "extract_many",
    "maybe_extract_highlevel",
    "reconcile_stem_sum",
    "resolve_audio_path",
]
