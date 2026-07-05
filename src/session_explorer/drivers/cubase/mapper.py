"""Cubase native ↔ canonical mapping — two native forms, one dispatch.

The Cubase driver has TWO native model families, distinguished by
``NativePayload.model_name``:

* ``"SessionState"`` — the Cubase repo's rich provenance-carrying model, as
  produced by the DAWproject extractor. Mapped here.
* ``"ProjectState"`` — the Ableton-family model used by the hand-authored
  Cubase demo session and Cubase-flavoured session JSON. Mapped by reusing
  :mod:`session_explorer.drivers.ableton.mapper` with ``dialect="cubase"``
  (the ableton mapper is dialect-parameterised for exactly this reason), so
  ids come out namespaced ``cubase:...`` and round-trips stay exact.

``to_native`` dispatches on ``model_name`` and returns the corresponding
verbatim native model.

Provenance status mapping (native Cubase vocabulary → core observability):

======================  ==========================================
native status           canonical observability
======================  ==========================================
observed/exported/      ``observed``
parsed
inferred/reconstructed  ``inferred``
user_supplied           ``annotation``
unavailable             ``hidden``
conflicting             ``inferred`` (explanation records conflict)
======================  ==========================================
"""

from __future__ import annotations

from typing import Optional, Union

from ...core.ids import namespaced
from ...core.models import (
    CanonicalSession,
    Clip,
    HiddenStateMarker,
    NativePayload,
    Processor,
    ProcessorParameter,
    Route,
    Track,
)
from ...core.provenance import Provenance
from ..ableton import mapper as ableton_mapper
from ..ableton.native_models import ProjectState
from . import observation_model
from .native_models import (
    ClipState,
    DeviceState,
    FolderState,
    SessionState,
    TrackState,
)
from .native_provenance import Provenance as NativeProvenance

DIALECT = "cubase"

SESSION_STATE_MODEL_NAME = "SessionState"
PROJECT_STATE_MODEL_NAME = ableton_mapper.NATIVE_MODEL_NAME  # "ProjectState"

_STATUS_TO_OBSERVABILITY = {
    "observed": "observed",
    "exported": "observed",
    "parsed": "observed",
    "inferred": "inferred",
    "reconstructed": "inferred",
    "user_supplied": "annotation",
    "unavailable": "hidden",
    "conflicting": "inferred",
}

_TRACK_KIND = {
    "audio": "audio",
    "midi": "midi",
    "instrument": "midi",
    "group": "group",
    "fx": "return",
    "folder": "group",
    "master": "master",
}


def _map_prov(
    native: Optional[NativeProvenance], source_artifact: str
) -> Provenance:
    """Map a native Cubase Provenance into the core vocabulary."""
    if native is None:
        return Provenance(observability="observed", source_artifact=source_artifact)
    observability = _STATUS_TO_OBSERVABILITY.get(native.status, "inferred")
    explanation = native.explanation
    if native.status == "conflicting" and not explanation:
        explanation = "multiple evidence sources disagreed on this value"
    artifact = source_artifact
    if native.source is not None:
        artifact = native.source.type or source_artifact
    return Provenance(
        observability=observability,
        source_artifact=artifact,
        confidence=native.confidence,
        explanation=explanation,
    )


def _map_field_prov(
    entity, source_artifact: str
) -> dict[str, Provenance]:
    return {
        field: _map_prov(prov, source_artifact)
        for field, prov in entity.field_provenance.items()
    }


def _entity_extras(entity) -> dict:
    """Preserve the native side-channel where present."""
    extras: dict = {}
    if getattr(entity, "native", None):
        extras["native"] = dict(entity.native)
    return extras


def _map_device(device: DeviceState, source_artifact: str) -> Processor:
    extras = _entity_extras(device)
    for key in (
        "vendor",
        "plugin_identifier",
        "plugin_format",
        "bypassed",
        "state_blob_ref",
        "latency_samples",
    ):
        value = getattr(device, key)
        if value is not None:
            extras[key] = value
    return Processor(
        id=namespaced(DIALECT, device.id),
        track_id=namespaced(DIALECT, device.track_id),
        index=device.index,
        name=device.name,
        kind=device.device_type,
        family=device.device_family,
        enabled=device.enabled,
        preset=device.preset_name,
        parameters=[
            ProcessorParameter(
                id=namespaced(DIALECT, param.id),
                processor_id=namespaced(DIALECT, device.id),
                name=param.name,
                value=param.value,
                normalized_value=param.normalized_value,
                unit=param.unit,
                is_automated=param.is_automated,
                is_visible_to_host=param.is_visible_to_host,
            )
            for param in device.parameters
        ],
        provenance=_map_prov(device.provenance, source_artifact),
        field_provenance=_map_field_prov(device, source_artifact),
        extras=extras,
        raw_source=device.raw_source or None,
    )


def _map_clip(clip: ClipState, source_artifact: str) -> Clip:
    extras = _entity_extras(clip)
    if clip.media_id:
        extras["media_id"] = clip.media_id
    if clip.notes:
        extras["midi_notes"] = [note.model_dump() for note in clip.notes]
    return Clip(
        id=namespaced(DIALECT, clip.id),
        track_id=namespaced(DIALECT, clip.track_id),
        name=clip.name,
        clip_type=clip.clip_type,
        # Beats domain (Cubase arranger events); seconds fields, when the
        # extractor observed them, keep their own unit-tagged canonical slots.
        start_time_beats=clip.start_time_beats,
        length_beats=clip.length_beats,
        loop_start_beats=clip.loop_start_beats,
        loop_end_beats=clip.loop_end_beats,
        position_seconds=clip.start_time_seconds,
        length_seconds=clip.length_seconds,
        midi_note_count=clip.midi_note_count,
        audio_file=clip.audio_file,
        provenance=_map_prov(clip.provenance, source_artifact),
        extras=extras,
        raw_source=clip.raw_source or None,
    )


def _map_track(
    track: TrackState, source_artifact: str, kind_override: Optional[str] = None
) -> Track:
    kind = kind_override or _TRACK_KIND.get(track.track_type, "unknown")
    extras = _entity_extras(track)
    for key in (
        "record_enabled",
        "monitor",
        "frozen",
        "channel_config",
    ):
        value = getattr(track, key)
        if value is not None:
            extras[key] = value
    if track.output_target_id:
        extras["output_target_id"] = namespaced(DIALECT, track.output_target_id)
    extras["native_track_type"] = track.track_type
    return Track(
        id=namespaced(DIALECT, track.id),
        index=track.index,
        name=track.name,
        kind=kind,  # type: ignore[arg-type]
        role="Bus" if kind == "return" and track.role is None else track.role,
        color=track.color,
        volume_db=track.volume_db,
        pan=track.pan,
        mute=track.mute,
        solo=track.solo,
        armed=track.record_enabled,
        group_id=namespaced(DIALECT, track.parent_id) if track.parent_id else None,
        clips=[_map_clip(clip, source_artifact) for clip in track.clips],
        processors=[_map_device(dev, source_artifact) for dev in track.devices],
        provenance=_map_prov(track.provenance, source_artifact),
        field_provenance=_map_field_prov(track, source_artifact),
        extras=extras,
        raw_source=track.raw_source or None,
    )


def _map_folder(folder: FolderState, source_artifact: str) -> Track:
    """A FolderState becomes a group-kind Track carrying folder semantics."""
    extras = _entity_extras(folder)
    extras.update(
        {
            "folder": True,
            "organizational_only": folder.organizational_only,
            "group_channel_enabled": folder.group_channel_enabled,
            "child_track_ids": [
                namespaced(DIALECT, child) for child in folder.child_track_ids
            ],
        }
    )
    return Track(
        id=namespaced(DIALECT, folder.id),
        index=folder.index,
        name=folder.name,
        kind="group",
        provenance=_map_prov(folder.provenance, source_artifact),
        field_provenance=_map_field_prov(folder, source_artifact),
        extras=extras,
    )


def _hidden_markers(state: SessionState) -> list[HiddenStateMarker]:
    markers = []
    for unknown in state.unknown_state:
        info = observation_model.STATE_GAP_INFO.get(unknown.state_gap, {})
        markers.append(
            HiddenStateMarker(
                id=namespaced(DIALECT, unknown.id),
                target_id=(
                    namespaced(DIALECT, unknown.entity_id)
                    if unknown.entity_id
                    else "project"
                ),
                hidden_state_type=unknown.state_gap,
                description=unknown.reason,
                consequence=str(
                    info.get(
                        "consequence",
                        "This state is not recoverable from the available "
                        "evidence surfaces.",
                    )
                ),
                possible_sources=list(unknown.potential_sources)
                or [str(s) for s in info.get("potential_sources", [])],
            )
        )
    return markers


def session_state_to_canonical(
    state: SessionState, source_artifact: str = "dawproject"
) -> CanonicalSession:
    """Map the Cubase repo's ``SessionState`` into a canonical session."""

    tracks: list[Track] = []
    tracks += [_map_track(t, source_artifact) for t in state.tracks]
    tracks += [
        _map_track(t, source_artifact, kind_override="group") for t in state.groups
    ]
    tracks += [
        _map_track(t, source_artifact, kind_override="return")
        for t in state.return_tracks
    ]
    if state.master_track is not None:
        tracks.append(
            _map_track(state.master_track, source_artifact, kind_override="master")
        )
    tracks += [_map_folder(folder, source_artifact) for folder in state.folders]

    routes: list[Route] = []
    for track in state.all_tracks():
        for send in track.sends:
            routes.append(
                Route(
                    id=namespaced(DIALECT, send.id),
                    source_track_id=namespaced(DIALECT, send.source_track_id),
                    target_track_id=(
                        namespaced(DIALECT, send.target_return_id)
                        if send.target_return_id
                        else None
                    ),
                    route_type="send",
                    volume_db=send.level_db,
                    pan=send.pan,
                    enabled=send.enabled,
                    provenance=_map_prov(send.provenance, source_artifact),
                    extras={
                        key: value
                        for key, value in (
                            ("send_name", send.send_name),
                            ("pre_fader", send.pre_fader),
                        )
                        if value is not None
                    },
                    raw_source=send.raw_source or None,
                )
            )
    for route in state.routes:
        routes.append(
            Route(
                id=namespaced(DIALECT, route.id),
                source_track_id=namespaced(DIALECT, route.source_track_id),
                target_track_id=namespaced(DIALECT, route.target_id),
                route_type=route.route_type,
                provenance=_map_prov(route.provenance, source_artifact),
                raw_source=route.raw_source or None,
            )
        )

    extras: dict = {
        "musical_structure": state.musical_structure.model_dump(),
        "project_meta": state.project.model_dump(),
        "capture": state.capture.model_dump(),
    }
    if state.media:
        extras["media"] = [media.model_dump() for media in state.media]
    if state.automation:
        extras["automation_lanes"] = [
            {
                "id": namespaced(DIALECT, lane.id),
                "track_id": namespaced(DIALECT, lane.track_id),
                "parameter_name": lane.parameter_name,
                "point_count": lane.point_count,
            }
            for lane in state.automation
        ]

    return CanonicalSession(
        dialect=DIALECT,
        name=state.project.project_name,
        source_file=state.project.project_path,
        tempo=state.tempo,
        time_signature=state.time_signature,
        sample_rate=state.project.sample_rate,
        tracks=tracks,
        routes=routes,
        hidden_state_markers=_hidden_markers(state),
        warnings=list(state.warnings),
        metadata={
            "source_artifact": source_artifact,
            "native_metadata": dict(state.metadata),
        },
        extras=extras,
        native=NativePayload(
            dialect=DIALECT,
            model_name=SESSION_STATE_MODEL_NAME,
            model=state.model_dump(),
        ),
    )


def project_state_to_canonical(
    project: ProjectState, source_artifact: str = "session_json"
) -> CanonicalSession:
    """Map an Ableton-family ``ProjectState`` (demo / session JSON) as Cubase."""
    return ableton_mapper.to_canonical(
        project, source_artifact=source_artifact, dialect=DIALECT
    )


def to_canonical(
    native: Union[SessionState, ProjectState], source_artifact: str = "dawproject"
) -> CanonicalSession:
    """Dispatch on the native model family."""
    if isinstance(native, SessionState):
        return session_state_to_canonical(native, source_artifact)
    if isinstance(native, ProjectState):
        return project_state_to_canonical(native, source_artifact)
    raise TypeError(
        f"Unsupported native model {type(native).__name__!r}; expected "
        "SessionState or ProjectState."
    )


def to_native(session: CanonicalSession) -> Union[SessionState, ProjectState]:
    """Reconstruct the verbatim native model, dispatching on model_name."""
    if session.native is None:
        raise ValueError(
            "This session carries no native payload; the native model cannot "
            "be reconstructed."
        )
    if session.native.model_name == SESSION_STATE_MODEL_NAME:
        return SessionState.model_validate(session.native.model)
    if session.native.model_name == PROJECT_STATE_MODEL_NAME:
        return ProjectState.model_validate(session.native.model)
    raise ValueError(
        f"Unknown native model name {session.native.model_name!r}; expected "
        f"{SESSION_STATE_MODEL_NAME!r} or {PROJECT_STATE_MODEL_NAME!r}."
    )
