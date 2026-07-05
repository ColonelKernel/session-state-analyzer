"""The verbatim Logic Pro *native* evidence models.

These models describe *evidence* about a Logic Pro session rather than the
session itself. The distinction is deliberate: exported audio, MIDI, MusicXML
and user notes are partial, observable traces of a session whose native state
(plug-in chains, automation, routing) remains hidden. The models therefore
carry explicit ``observed`` / ``inferred`` / ``hidden`` bookkeeping.

:class:`SessionEvidence` is the native payload model for the ``logic``
dialect: ``mapper.to_canonical`` stores its complete ``model_dump()`` in
``CanonicalSession.native`` and ``mapper.to_native`` re-validates it, so the
round-trip is exact.

Deliberate simplifications versus the prototype source
(``logic_session_evidence_explorer.models``):

* The dataclass-based pydantic fallback shim is removed — pydantic v2 is a
  hard dependency of the monorepo, so the fallback path is dead code here.
* Classes whose fields are identical to their core promotions are aliased
  from :mod:`session_explorer.core.models` instead of duplicated
  (``AudioEvidence``, ``MidiEvidence``, ``MusicXmlEvidence``,
  ``ChannelStripNote``, ``ReferenceTrackEvidence``, ``HiddenStateMarker``,
  ``StemSumReconciliation``, ``ReferenceComparison``). Classes whose field
  names differ from the canonical schema stay verbatim local for payload
  fidelity: the native :class:`AudioDescriptorSet` keeps
  ``dynamic_range_approx`` (canonical renamed it ``dynamic_range_db``), the
  native :class:`Recommendation` keeps its original defaults and has no
  ``references`` field, and :class:`InferredTrackState` /
  :class:`SessionEvidence` are Logic-native shapes with no core counterpart.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ...core.models import (  # field-identical core promotions, aliased
    AudioEvidence,
    ChannelStripNote,
    HiddenStateMarker,
    MidiEvidence,
    MusicXmlEvidence,
    ReferenceComparison,
    ReferenceTrackEvidence,
    StemSumReconciliation,
    to_dict,
)
from ...core.models import AudioDescriptorSet as CanonicalAudioDescriptorSet

SCHEMA_VERSION = "0.1.0"


class AudioDescriptorSet(BaseModel):
    """Numeric descriptors extracted from a single audio file.

    Level descriptors come in two flavours: whole-file (``rms_mean``) and
    silence-gated (``active_rms_mean``). Logic exports each track at full song
    length, so a stem that plays only in one chorus is mostly digital silence
    — whole-file RMS then measures arrangement density, not level. The
    ``active_*`` fields measure only the frames where the stem is playing.

    Kept verbatim local (not aliased from core): the canonical schema renamed
    ``dynamic_range_approx`` to ``dynamic_range_db`` and grew extra fields
    (``available``, ``file_path``, ``extra``, ...) the native payload never
    carried.
    """

    id: str
    source_id: str
    source_type: str = "audio_evidence"
    file_name: str = ""
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    rms_mean: Optional[float] = None
    rms_std: Optional[float] = None
    peak_amplitude: Optional[float] = None
    dynamic_range_approx: Optional[float] = None
    activity_ratio: Optional[float] = None
    active_rms_mean: Optional[float] = None
    active_duration_seconds: Optional[float] = None
    dynamic_range_active_db: Optional[float] = None
    stereo_width_ratio: Optional[float] = None
    spectral_centroid_mean: Optional[float] = None
    spectral_bandwidth_mean: Optional[float] = None
    spectral_rolloff_mean: Optional[float] = None
    zero_crossing_rate_mean: Optional[float] = None
    onset_strength_mean: Optional[float] = None
    estimated_tempo: Optional[float] = None
    integrated_loudness_lufs: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)


class InferredTrackState(BaseModel):
    """A track reconstructed from the available evidence.

    ``observed_fields`` / ``inferred_fields`` / ``hidden_fields`` make the
    partial-observability of the reconstruction explicit.
    """

    id: str
    name: str
    role: Optional[str] = None
    source_audio_id: Optional[str] = None
    linked_midi_track_names: list[str] = Field(default_factory=list)
    linked_musicxml_parts: list[str] = Field(default_factory=list)
    channel_strip_note_ids: list[str] = Field(default_factory=list)
    descriptor_id: Optional[str] = None
    confidence: float = 0.0
    observed_fields: list[str] = Field(default_factory=list)
    inferred_fields: list[str] = Field(default_factory=list)
    hidden_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    """Verbatim native recommendation (severity is a free string here, and
    the defaults differ from the canonical :class:`Recommendation`)."""

    id: str
    title: str
    severity: str = "info"  # info | suggestion | warning
    confidence: float = 0.5
    related_node_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    suggested_action: str = ""
    caveat: str = ""


class GraphExport(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class SessionEvidence(BaseModel):
    schema_version: str = SCHEMA_VERSION
    session_name: str = "Untitled Logic Session Evidence"
    daw_name: str = "Logic Pro"
    daw_version: Optional[str] = None
    source_type: str = "logic_exports"  # logic_exports | synthetic_demo | mixed_evidence
    audio_files: list[AudioEvidence] = Field(default_factory=list)
    midi_evidence: Optional[MidiEvidence] = None
    musicxml_evidence: Optional[MusicXmlEvidence] = None
    channel_strip_notes: list[ChannelStripNote] = Field(default_factory=list)
    reference_tracks: list[ReferenceTrackEvidence] = Field(default_factory=list)
    inferred_tracks: list[InferredTrackState] = Field(default_factory=list)
    hidden_state_markers: list[HiddenStateMarker] = Field(default_factory=list)
    descriptors: list[AudioDescriptorSet] = Field(default_factory=list)
    stem_sum_reconciliation: Optional[StemSumReconciliation] = None
    reference_comparisons: list[ReferenceComparison] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Descriptor bridge: native <-> canonical AudioDescriptorSet.
#
# The only field-name divergence between the two schemas is
# dynamic_range_approx (native) <-> dynamic_range_db (canonical). Canonical
# extras the native payload never carried (available, file_path, node_id,
# extra, Essentia fields) are dropped on the way in; unavailable_reason is
# folded into warnings, mirroring the prototype's "librosa not available"
# warning behaviour.
# ---------------------------------------------------------------------------

_SHARED_DESCRIPTOR_FIELDS = [
    "source_type",
    "file_name",
    "duration_seconds",
    "sample_rate",
    "rms_mean",
    "rms_std",
    "peak_amplitude",
    "activity_ratio",
    "active_rms_mean",
    "active_duration_seconds",
    "dynamic_range_active_db",
    "stereo_width_ratio",
    "spectral_centroid_mean",
    "spectral_bandwidth_mean",
    "spectral_rolloff_mean",
    "zero_crossing_rate_mean",
    "onset_strength_mean",
    "estimated_tempo",
    "integrated_loudness_lufs",
]


def descriptor_to_native(
    canonical: CanonicalAudioDescriptorSet,
    *,
    descriptor_id: Optional[str] = None,
    source_id: Optional[str] = None,
) -> AudioDescriptorSet:
    """Convert a canonical descriptor (e.g. from ``core.audio.descriptors``)
    into the verbatim native shape."""

    data = {f: getattr(canonical, f) for f in _SHARED_DESCRIPTOR_FIELDS}
    warnings = list(canonical.warnings)
    if canonical.unavailable_reason:
        warnings.append(canonical.unavailable_reason)
    return AudioDescriptorSet(
        id=descriptor_id or canonical.id or "",
        source_id=source_id or canonical.source_id or "",
        dynamic_range_approx=canonical.dynamic_range_db,
        warnings=warnings,
        **data,
    )


def descriptor_to_canonical(native: AudioDescriptorSet) -> CanonicalAudioDescriptorSet:
    """Convert a native descriptor into the canonical shape (ids untouched;
    the mapper namespaces them separately)."""

    data = {f: getattr(native, f) for f in _SHARED_DESCRIPTOR_FIELDS}
    return CanonicalAudioDescriptorSet(
        id=native.id,
        source_id=native.source_id,
        dynamic_range_db=native.dynamic_range_approx,
        # The native model has no availability flag; a descriptor that carries
        # at least a duration was demonstrably extracted from real audio.
        available=native.duration_seconds is not None,
        warnings=list(native.warnings),
        **data,
    )


__all__ = [
    "SCHEMA_VERSION",
    "AudioDescriptorSet",
    "AudioEvidence",
    "MidiEvidence",
    "MusicXmlEvidence",
    "ChannelStripNote",
    "ReferenceTrackEvidence",
    "InferredTrackState",
    "HiddenStateMarker",
    "StemSumReconciliation",
    "ReferenceComparison",
    "Recommendation",
    "GraphExport",
    "SessionEvidence",
    "to_dict",
    "descriptor_to_native",
    "descriptor_to_canonical",
]
