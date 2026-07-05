"""Assemble a complete :class:`SessionEvidence` from raw inputs.

This is the orchestration layer used by the driver (and originally by the
prototype's Streamlit app and CLI). It:

1. links each non-reference audio file to an inferred track,
2. optionally attaches descriptors, MIDI, MusicXML and channel-strip notes,
3. generates hidden-state markers for Logic-native state exports cannot reveal,
4. runs the recommendation engine.

The hidden-state markers are central to the research framing: they are emitted
deliberately and unconditionally, because the point is to make what we *cannot*
observe as visible as what we can.

Ported from the Logic prototype with imports rewired to core:

* the declarative observation matrix, ``annotated_fields_from_note`` and
  ``hidden_fields_for_track`` now live in
  :mod:`session_explorer.core.observability` (note the core Logic matrix adds
  ``mixer_state`` to what exported audio hides — a canonical-schema
  generalization, so inferred tracks now carry it in ``hidden_fields``);
* descriptor extraction and the signal comparisons live in
  :mod:`session_explorer.core.audio` (canonical descriptors are bridged back
  to the native shape via :func:`native_models.descriptor_to_native`);
* name matching lives in :mod:`session_explorer.core.matching`.

The hidden-state marker *catalogue* stays here: it is Logic-specific prose
(documented Logic constructs, page-cited), not shared observability
machinery.
"""

from __future__ import annotations

import os
from typing import Optional

from ...core import observability
from ...core.audio import descriptors as audio_descriptors
from ...core.matching import names_match
from . import rules as recommendations
from . import utils
from .native_models import (
    HiddenStateMarker,
    InferredTrackState,
    SessionEvidence,
    descriptor_to_canonical,
    descriptor_to_native,
)

# ---------------------------------------------------------------------------
# The hidden-state marker catalogue, derived from the fields no export
# reveals. ``target`` is "track" (one marker per undocumented track) or
# "session" (one marker for the whole session).
# Descriptions and consequences use Logic's documented constructs and
# terminology (Logic Pro User Guide: channel strips pp. 541-548, sends
# pp. 584-590, insert chain limit and serial order p. 583, track stacks
# pp. 161-167, VCA pp. 603-604, automation pp. 621-633, project
# alternatives pp. 105-109, mixer groups pp. 598-603).
# (Ported verbatim from the prototype's observation_model module; the generic
# observation matrix itself was promoted to core.observability.)
# ---------------------------------------------------------------------------
HIDDEN_STATE_DEFINITIONS: dict[str, dict] = {
    "hidden_plugin_chain": {
        "target": "track",
        "field": "plugin_chain",
        "display_name": "Hidden plug-in chain",
        "description": (
            "Native Logic channel-strip state — the serial insert-effect chain "
            "(up to 15 Audio FX slots, processed top-down in insertion order) "
            "and its parameter values — is not directly observable from "
            "exported audio alone."
        ),
        "consequence": (
            "An exported stem carries only the summed acoustic result of the "
            "insert chain: recommendations based on stem audio and filename "
            "evidence cannot distinguish printed processing from raw recording, "
            "nor recover plug-in identity, order, or settings."
        ),
    },
    "hidden_automation": {
        "target": "session",
        "field": "automation",
        "display_name": "Hidden automation",
        "description": (
            "Automation state — Logic's track automation and region automation "
            "curves, their parameter targets, and per-track mode "
            "(Read/Touch/Latch/Write) — is not available from exported stems "
            "unless separately documented."
        ),
        "consequence": (
            "Temporal mix decisions such as vocal rides, send throws, or filter "
            "sweeps may be audible as a printed gain or timbre envelope, but the "
            "point-by-point curves and their targets are no longer editable "
            "DAW state."
        ),
    },
    "hidden_routing": {
        "target": "session",
        "field": "bus_routing",
        "display_name": "Hidden routing",
        "description": (
            "Routing state — sends (Pre Fader / Post Fader / Post Pan) to "
            "bus-fed aux channel strips, summing and folder track stacks, VCA "
            "group assignments, mixer groups, and sidechain sources — is not "
            "reliably recoverable from stem audio alone."
        ),
        "consequence": (
            "The graph may represent exported stems as flat tracks even if the "
            "original Logic session used subgroup buses, track stacks, or VCA "
            "faders. The structures themselves are unrecoverable: a mixer group "
            "links controls without touching signal flow, while a VCA fader or "
            "a folder stack's stack master (which functions as a VCA master "
            "fader) imprints gain into each stem indistinguishably from "
            "individual fader moves."
        ),
    },
}


def session_level_definitions() -> list[tuple[str, dict]]:
    return [(k, v) for k, v in HIDDEN_STATE_DEFINITIONS.items() if v["target"] == "session"]


def track_level_definitions() -> list[tuple[str, dict]]:
    return [(k, v) for k, v in HIDDEN_STATE_DEFINITIONS.items() if v["target"] == "track"]


def _hidden_marker(target_id: str, hstype: str, definition: dict) -> HiddenStateMarker:
    return HiddenStateMarker(
        id=utils.make_id("hidden"),
        target_id=target_id,
        hidden_state_type=hstype,
        description=definition["description"],
        consequence=definition["consequence"],
        possible_sources=list(observability.POSSIBLE_SOURCES),
    )


def build_inferred_tracks(session: SessionEvidence) -> list[InferredTrackState]:
    """Create one inferred track per non-mixdown, non-reference stem."""

    tracks: list[InferredTrackState] = []
    for audio in session.audio_files:
        if audio.is_mixdown or audio.is_reference:
            continue
        observed = ["file_name"]
        if audio.duration_seconds is not None:
            observed.append("duration_seconds")
        if audio.sample_rate is not None:
            observed.append("sample_rate")

        note_ids = [
            n.id
            for n in session.channel_strip_notes
            if names_match(n.track_name, audio.inferred_track_name or audio.file_name)
        ]

        # Fields the user has annotated move from "hidden" to "annotated";
        # both sets are derived from the declarative observation model.
        # Collect across notes, then order by the model's field order so the
        # exported list is stable regardless of note order.
        asserted: set[str] = set()
        for note in session.channel_strip_notes:
            if note.id in note_ids:
                asserted.update(observability.annotated_fields_from_note(note))
        annotated_fields = [
            f for f in observability.NOTE_FIELD_ASSERTIONS.values() if f in asserted
        ]
        hidden_fields = observability.hidden_fields_for_track(
            annotated_fields, dialect="logic", artifact_type="exported_audio"
        )

        track = InferredTrackState(
            id=utils.make_id("track"),
            name=audio.inferred_track_name or audio.file_name,
            role=audio.inferred_role,
            source_audio_id=audio.id,
            channel_strip_note_ids=note_ids,
            descriptor_id=audio.descriptor_id,
            confidence=audio.confidence,
            observed_fields=observed,
            inferred_fields=["role", "track_name"] + annotated_fields,
            hidden_fields=hidden_fields,
        )
        tracks.append(track)
    return tracks


def generate_hidden_state_markers(session: SessionEvidence) -> list[HiddenStateMarker]:
    """Derive hidden-state markers from the declarative observation model.

    Session-level definitions always emit one marker; track-level definitions
    emit one marker per inferred track whose corresponding field has not been
    lifted by a user annotation. Deriving (rather than hard-coding) makes the
    marker set checkable for completeness against the model.
    """

    markers: list[HiddenStateMarker] = []

    for hstype, definition in session_level_definitions():
        markers.append(_hidden_marker("session", hstype, definition))

    for hstype, definition in track_level_definitions():
        for track in session.inferred_tracks:
            if definition["field"] in track.hidden_fields:
                markers.append(_hidden_marker(track.id, hstype, definition))
    return markers


def attach_descriptors(session: SessionEvidence, *, estimate_tempo: bool = True) -> None:
    """Extract descriptors for every audio file / reference that has a path."""

    for audio in session.audio_files:
        if not audio.file_path or not os.path.exists(audio.file_path):
            continue
        canonical = audio_descriptors.extract_descriptors(
            audio.file_path,
            source_id=audio.id,
            source_type="audio_evidence",
            file_name=audio.file_name,
            estimate_tempo=estimate_tempo,
        )
        # Bridge to the native shape, with a native-vocabulary id
        # ("descriptor_1") so payload ids stay in the prototype's format.
        desc = descriptor_to_native(
            canonical, descriptor_id=utils.make_id("descriptor")
        )
        audio.descriptor_id = desc.id
        if audio.duration_seconds is None:
            audio.duration_seconds = desc.duration_seconds
        if audio.sample_rate is None:
            audio.sample_rate = desc.sample_rate
        session.descriptors.append(desc)

    for ref in session.reference_tracks:
        if not ref.file_path or not os.path.exists(ref.file_path):
            continue
        canonical = audio_descriptors.extract_descriptors(
            ref.file_path,
            source_id=ref.id,
            source_type="reference_track",
            file_name=ref.file_name,
            estimate_tempo=estimate_tempo,
        )
        desc = descriptor_to_native(
            canonical, descriptor_id=utils.make_id("descriptor")
        )
        ref.descriptor_id = desc.id
        session.descriptors.append(desc)


def _descriptor_by_id(session: SessionEvidence, descriptor_id):
    for d in session.descriptors:
        if d.id == descriptor_id:
            return d
    return None


def _canonical_descriptor_by_id(session: SessionEvidence, descriptor_id):
    """Native descriptors bridged back to canonical for the core comparators
    (which read the canonical ``dynamic_range_db`` field name)."""

    native = _descriptor_by_id(session, descriptor_id)
    return descriptor_to_canonical(native) if native is not None else None


def attach_signal_comparisons(session: SessionEvidence) -> None:
    """Run stem-sum reconciliation and reference comparison when the needed
    audio files are on disk. Failures degrade to warnings on the result."""

    from ...core.audio import signal_comparisons

    def _on_disk(obj):
        return obj.file_path and os.path.exists(obj.file_path)

    mixdown = next((a for a in session.audio_files if a.is_mixdown and _on_disk(a)), None)
    if not mixdown:
        return

    stems = {
        a.id: a.file_path
        for a in session.audio_files
        if not a.is_mixdown and not a.is_reference and _on_disk(a)
    }
    if len(stems) >= 2:
        session.stem_sum_reconciliation = signal_comparisons.reconcile_stem_sum(
            stems, mixdown.file_path, mixdown_audio_id=mixdown.id
        )

    references = [a for a in session.audio_files if a.is_reference and _on_disk(a)]
    # A dedicated reference that duplicates a file already in the stem pool
    # (same file uploaded to both uploaders) must be compared only once —
    # mirroring the graph's node dedup.
    audio_file_names = {a.file_name for a in session.audio_files}
    references += [
        r for r in session.reference_tracks
        if _on_disk(r) and r.file_name not in audio_file_names
    ]
    for ref in references:
        session.reference_comparisons.append(
            signal_comparisons.compare_to_reference(
                mixdown.file_path,
                ref.file_path,
                mixdown_audio_id=mixdown.id,
                reference_id=ref.id,
                mixdown_descriptor=_canonical_descriptor_by_id(session, mixdown.descriptor_id),
                reference_descriptor=_canonical_descriptor_by_id(session, ref.descriptor_id),
            )
        )


def finalize_session(session: SessionEvidence, *, with_descriptors: bool = True) -> SessionEvidence:
    """Run the full assembly pipeline on a session that already has audio_files
    (and optionally MIDI / MusicXML / notes) populated."""

    if with_descriptors:
        attach_descriptors(session)
        attach_signal_comparisons(session)
    session.inferred_tracks = build_inferred_tracks(session)
    # Re-point inferred track descriptor ids now that descriptors exist.
    for track in session.inferred_tracks:
        for audio in session.audio_files:
            if audio.id == track.source_audio_id and audio.descriptor_id:
                track.descriptor_id = audio.descriptor_id
    session.hidden_state_markers = generate_hidden_state_markers(session)
    session.recommendations = recommendations.generate_recommendations(session)
    return session
