"""Re-export shim: the nested v0.1 session models moved to ``canonical_snapshot.nested``.

The nested ``CanonicalSession`` family is now owned by the shared contract
package (``packages/canonical_snapshot``), where it serves as the adapters'
internal intermediate ahead of ``from_nested.flatten_session()``. This module
re-exports every public name so existing analyzer imports keep working
unchanged (decision D1: additive restructure, no big-bang rename).
"""

from __future__ import annotations

from canonical_snapshot.nested import (
    CANONICAL_SCHEMA_VERSION,
    KNOWN_DIALECTS,
    AudioDescriptorSet,
    AudioEvidence,
    CanonicalSession,
    ChannelStripNote,
    Clip,
    EvidenceBundle,
    HiddenStateMarker,
    MidiEvidence,
    MusicXmlEvidence,
    NativePayload,
    Processor,
    ProcessorParameter,
    Recommendation,
    ReferenceComparison,
    ReferenceTrackEvidence,
    Route,
    Scene,
    Severity,
    StemSumReconciliation,
    Track,
    TrackKind,
    to_dict,
)

__all__ = [
    "CANONICAL_SCHEMA_VERSION",
    "Severity",
    "KNOWN_DIALECTS",
    "TrackKind",
    "ProcessorParameter",
    "Processor",
    "Clip",
    "Route",
    "Scene",
    "Track",
    "HiddenStateMarker",
    "Recommendation",
    "AudioDescriptorSet",
    "AudioEvidence",
    "MidiEvidence",
    "MusicXmlEvidence",
    "ChannelStripNote",
    "ReferenceTrackEvidence",
    "StemSumReconciliation",
    "ReferenceComparison",
    "EvidenceBundle",
    "NativePayload",
    "CanonicalSession",
    "to_dict",
]
