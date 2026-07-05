"""``flatten_session()`` — the one audited nested→flat converter.

The four adapter mappers produce the v0.1 nested :class:`~.nested.
CanonicalSession` (Ableton and REAPER round-trip-verified). This module is the
single place where that intermediate becomes the flat v0.2 wire format, so the
load-bearing modeling decisions live in exactly one spot:

- **TRACK ≠ CHANNEL split.** A nested ``Track`` fuses an organizational lane
  with a mixer signal path. Here they become separate entities joined by
  ``TRACK_USES_CHANNEL``. REAPER's plain audio tracks legitimately emit both —
  that *is* the honest representation of a DAW that fuses the concepts.
  Return/master tracks are channel-like and emit CHANNEL only; Logic's
  evidence-reconstructed tracks emit TRACK only, with an availability record
  saying the channel was never observed.
- **Semantic roles, not type explosions.** ``kind``/``role`` become
  ``semantic_roles`` so one entity can be both a submix and a folder parent.
- **A deduplicated provenance store.** Nested per-entity ``Provenance`` +
  ``field_provenance`` collapse into shared :class:`ProvenanceRecord`s
  referenced by id; ``"*"`` is the entity-level default. Evidence vocabulary
  migrates per decision D5: ``annotation→ANNOTATED``, ``derived→INFERRED``
  with ``capture_method="derived_computation"``.
- **The native payload never rides the wire.** It becomes a sibling
  ``native.json``; the snapshot carries only its path + hash in
  ``extensions``.

Coverage counts are computed from the same provenance evidence and are
*approximate but honest*: they bucket whole items (a track, a processor, a
route) by their entity-level evidence class, they do not count per-field
detail, and ANNOTATED items are counted as applicable without claiming an
observed/inferred/hidden bucket. The measured atlas (P5) refines this.
"""

from __future__ import annotations

import re
from os.path import basename
from typing import Any, Optional

from . import nested
from .capabilities import CapabilityManifest
from .enums import SourceStability
from .models import (
    CanonicalDAWSnapshot,
    DomainCoverage,
    Entity,
    NativeRef,
    ProvenanceRecord,
    Relationship,
    SourceInfo,
)

# Evidence migration (decision D5): the adapter contract uses exactly
# OBSERVED/INFERRED/ANNOTATED/HIDDEN; "derived" survives only as a
# capture_method tag.
_EVIDENCE_MAP = {
    "observed": "OBSERVED",
    "inferred": "INFERRED",
    "annotation": "ANNOTATED",
    "hidden": "HIDDEN",
    "derived": "INFERRED",
}

# Heuristic track roles → canonical semantic roles. Unknown roles pass
# through slugified rather than being dropped: the vocabulary is open.
ROLE_TO_SEMANTIC = {
    "vocal": "vocal_source",
    "vocals": "vocal_source",
    "drums": "drum_source",
    "drum": "drum_source",
    "percussion": "drum_source",
    "bass": "bass_source",
    "guitar": "guitar_source",
    "keys": "keys_source",
    "piano": "keys_source",
    "synth": "synth_source",
    "strings": "strings_source",
    "brass": "brass_source",
    "fx": "effect_source",
    "bus": "submix",
    "master": "main_output",
    "reference": "reference_material",
}

# Nested Track fields that live on the CHANNEL side of the split.
_CHANNEL_FIELDS = frozenset({"volume_db", "pan", "mute", "solo", "armed"})


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return slug or "unnamed"


def _semantic_role(role: str) -> str:
    return ROLE_TO_SEMANTIC.get(role.strip().lower(), _slug(role))


def _non_none(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


class _ProvStore:
    """Deduplicating provenance store: identical records share one id."""

    def __init__(self, default_capture: str, default_stability: SourceStability):
        self.default_capture = default_capture
        self.default_stability = default_stability
        self._records: list[ProvenanceRecord] = []
        self._index: dict[tuple, str] = {}

    def add(
        self,
        evidence: str,
        capture_method: Optional[str] = None,
        confidence: Optional[float] = None,
        explanation: Optional[str] = None,
        source_ref: Optional[str] = None,
        warnings: tuple[str, ...] = (),
    ) -> str:
        capture = capture_method or self.default_capture
        key = (evidence, capture, self.default_stability, source_ref, confidence, explanation, warnings)
        found = self._index.get(key)
        if found is not None:
            return found
        prov_id = f"prov:{len(self._records) + 1:04d}"
        self._records.append(
            ProvenanceRecord(
                id=prov_id,
                evidence=evidence,  # type: ignore[arg-type]
                capture_method=capture,
                source_stability=self.default_stability,
                source_ref=source_ref,
                confidence=confidence,
                explanation=explanation,
                warnings=list(warnings),
            )
        )
        self._index[key] = prov_id
        return prov_id

    def add_nested(self, prov: nested.Provenance) -> str:
        """Map a nested v0.1 ``Provenance`` into the v0.2 store (decision D5)."""
        evidence = _EVIDENCE_MAP[prov.observability]
        if prov.observability == "derived":
            capture: Optional[str] = "derived_computation"
        else:
            capture = prov.source_artifact
        # Confidence only where it is meaningful: a directly observed value
        # does not get to claim confidence 1.0 as if it were a measurement.
        confidence = None if prov.observability == "observed" else prov.confidence
        return self.add(
            evidence,
            capture_method=capture,
            confidence=confidence,
            explanation=prov.explanation,
        )

    def records(self) -> list[ProvenanceRecord]:
        return list(self._records)


def flatten_session(
    session: nested.CanonicalSession,
    source: SourceInfo,
    capabilities: Optional[CapabilityManifest] = None,
    *,
    native_file: Optional[str] = None,
    native_sha256: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    created_at: str = "",
    default_stability: SourceStability = "COMMUNITY_DOCUMENTED",
) -> CanonicalDAWSnapshot:
    """Flatten a nested v0.1 session into a flat v0.2 snapshot.

    The nested form never appears on the wire; this is the only sanctioned
    crossing. See the module docstring for the modeling decisions made here.

    ``native_file``/``native_sha256`` reference the sibling ``native.json``
    written by the adapter's exporter; when the session carries a native
    payload but no sibling path is given, the omission is recorded explicitly
    (``extensions[daw]["native_payload_omitted"] = True``) rather than the
    payload being silently dropped or embedded.

    ``default_stability`` states how durable this adapter's capture pathway
    is; individual records inherit it (per-record stability overrides arrive
    with capability-manifest-aware adapters, not from the nested form, which
    never carried the dimension).
    """

    daw = source.daw
    # Id namespace comes from the nested session's dialect, matching every id
    # the adapter mapper already emitted ("ableton:track-1"), NOT from
    # source.daw ("ableton_live") — one snapshot, one namespace.
    namespace = session.dialect or daw
    default_capture = source.capture_modes[0] if source.capture_modes else "unknown"
    store = _ProvStore(default_capture, default_stability)

    entities: list[Entity] = []
    entity_by_id: dict[str, Entity] = {}
    relationships: list[Relationship] = []
    warnings: list[str] = list(session.warnings)
    ext: dict[str, Any] = {}

    _rel_counter = [0]

    def add_entity(entity: Entity) -> Entity:
        entities.append(entity)
        entity_by_id[entity.id] = entity
        return entity

    def add_rel(
        rel_type: str,
        src: str,
        dst: str,
        properties: Optional[dict[str, Any]] = None,
        prov_ref: Optional[str] = None,
    ) -> Relationship:
        _rel_counter[0] += 1
        rel = Relationship(
            id=f"rel:{_rel_counter[0]:04d}",
            rel_type=rel_type,
            source=src,
            target=dst,
            properties=properties or {},
            prov_ref=prov_ref,
        )
        relationships.append(rel)
        return rel

    # -- PROJECT ------------------------------------------------------------
    project_id = f"{namespace}:project"
    project_prov = store.add("OBSERVED")
    project = add_entity(
        Entity(
            id=project_id,
            entity_type="PROJECT",
            name=session.name,
            properties=_non_none(
                tempo=session.tempo,
                time_signature=session.time_signature,
                sample_rate=session.sample_rate,
                source_file=session.source_file,
            ),
            native=NativeRef(daw=daw, native_type="project"),
            prov={"*": project_prov},
        )
    )
    if session.extras:
        ext.update(nested.to_dict(session.extras))
    if session.metadata:
        ext["metadata"] = nested.to_dict(session.metadata)

    # -- tracks: the TRACK ≠ CHANNEL split -----------------------------------
    # channel_of: nested track id → the CHANNEL entity carrying its mixer
    # state (used for routing/processing endpoints). track_entity_of: nested
    # track id → the entity that plays the organizational role.
    channel_of: dict[str, str] = {}
    track_entity_of: dict[str, str] = {}
    track_evidence: list[str] = []
    channel_evidence: list[str] = []

    def _track_prov(track: nested.Track) -> tuple[dict[str, str], dict[str, str]]:
        """Split ``field_provenance`` between the TRACK and CHANNEL sides."""
        base = store.add_nested(track.provenance)
        track_prov = {"*": base}
        channel_prov = {"*": base}
        for field, fp in track.field_provenance.items():
            ref = store.add_nested(fp)
            if field in _CHANNEL_FIELDS:
                channel_prov[field] = ref
            elif field == "role":
                track_prov["semantic_roles"] = ref
            else:
                track_prov[field] = ref
        return track_prov, channel_prov

    def _channel_properties(track: nested.Track) -> dict[str, Any]:
        return _non_none(
            volume_db=track.volume_db,
            pan=track.pan,
            mute=track.mute,
            solo=track.solo,
            armed=track.armed,
        )

    def _native_ref(track: nested.Track) -> NativeRef:
        props = dict(nested.to_dict(track.extras)) if track.extras else {}
        if track.raw_source is not None:
            props["raw_source"] = nested.to_dict(track.raw_source)
        return NativeRef(daw=daw, native_type=track.kind, properties=props)

    for track in session.tracks:
        track_prov, channel_prov = _track_prov(track)
        track_evidence.append(track.provenance.observability)
        roles: list[str] = []
        if track.role:
            roles.append(_semantic_role(track.role))
        for w in track.warnings:
            warnings.append(f"{track.id}: {w}")

        if track.kind in ("return", "master"):
            # Channel-like natives: no organizational lane to speak of.
            # The CHANNEL keeps the nested id (no TRACK exists to claim it).
            role = "effect_return" if track.kind == "return" else "main_output"
            semantic = [role] + [r for r in roles if r not in ("submix", role)]
            add_entity(
                Entity(
                    id=track.id,
                    entity_type="CHANNEL",
                    name=track.name,
                    semantic_roles=semantic,
                    properties={"index": track.index, **_channel_properties(track)},
                    native=_native_ref(track),
                    prov={**channel_prov, **{k: v for k, v in track_prov.items() if k != "*"}},
                )
            )
            channel_of[track.id] = track.id
            track_entity_of[track.id] = track.id
            channel_evidence.append(track.provenance.observability)
            continue

        if track.kind == "inferred":
            # Evidence-reconstructed lane (Logic pathway): no channel was ever
            # observed — say so instead of inventing one.
            add_entity(
                Entity(
                    id=track.id,
                    entity_type="TRACK",
                    name=track.name,
                    semantic_roles=roles,
                    properties=_non_none(index=track.index, color=track.color),
                    native=_native_ref(track),
                    prov=track_prov,
                    availability={"channel": "UNKNOWN"},
                )
            )
            track_entity_of[track.id] = track.id
            continue

        # Default path (audio/midi/aux/unknown/group): the DAW fuses lane and
        # signal path — emit both halves explicitly. REAPER plain audio tracks
        # legitimately land here: TRACK + CHANNEL is their honest shape.
        if track.kind == "group":
            roles = ["submix", "folder_parent"] + [
                r for r in roles if r not in ("submix", "folder_parent")
            ]
        channel_id = f"{track.id}:channel"
        add_entity(
            Entity(
                id=track.id,
                entity_type="TRACK",
                name=track.name,
                semantic_roles=roles,
                properties=_non_none(index=track.index, color=track.color),
                native=_native_ref(track),
                prov=track_prov,
            )
        )
        add_entity(
            Entity(
                id=channel_id,
                entity_type="CHANNEL",
                name=track.name,
                semantic_roles=["submix"] if track.kind == "group" else [],
                properties=_channel_properties(track),
                native=NativeRef(daw=daw, native_type=track.kind),
                prov=channel_prov,
            )
        )
        add_rel("TRACK_USES_CHANNEL", track.id, channel_id, prov_ref=track_prov["*"])
        channel_of[track.id] = channel_id
        track_entity_of[track.id] = track.id
        channel_evidence.append(track.provenance.observability)

    # -- group containment + summing ------------------------------------------
    for track in session.tracks:
        if not track.group_id or track.group_id not in track_entity_of:
            if track.group_id:
                warnings.append(
                    f"{track.id}: group_id {track.group_id!r} does not match any track."
                )
            continue
        group_track = track_entity_of[track.group_id]
        member_prov = store.add_nested(track.provenance)
        add_rel(
            "CONTAINS",
            group_track,
            track_entity_of[track.id],
            properties={"kind": "group_member"},
            prov_ref=member_prov,
        )
        child_channel = channel_of.get(track.id)
        group_channel = channel_of.get(track.group_id)
        if child_channel and group_channel:
            # The summing semantics (SUMS_TO) and its signal-flow expression
            # (CHANNEL_ROUTES_TO) — layered views filter by whichever they need.
            add_rel(
                "CHANNEL_ROUTES_TO",
                child_channel,
                group_channel,
                properties={"via": "group_sum"},
                prov_ref=member_prov,
            )
            add_rel(
                "SUMS_TO",
                child_channel,
                group_channel,
                prov_ref=member_prov,
            )

    # -- processors + parameters ----------------------------------------------
    processor_evidence: list[str] = []
    for track in session.tracks:
        owner = channel_of.get(track.id, track_entity_of.get(track.id, track.id))
        for i, proc in enumerate(track.processors):
            proc_base = store.add_nested(proc.provenance)
            proc_prov = {"*": proc_base}
            for field, fp in proc.field_provenance.items():
                proc_prov[field] = store.add_nested(fp)
            processor_evidence.append(proc.provenance.observability)
            native_props = dict(nested.to_dict(proc.extras)) if proc.extras else {}
            if proc.raw_source is not None:
                native_props["raw_source"] = nested.to_dict(proc.raw_source)
            add_entity(
                Entity(
                    id=proc.id,
                    entity_type="PROCESSOR",
                    name=proc.name,
                    properties=_non_none(
                        family=proc.family,
                        kind=proc.kind,
                        enabled=proc.enabled,
                        offline=proc.offline,
                        preset=proc.preset,
                        chain=proc.chain,
                    ),
                    native=NativeRef(daw=daw, native_type=proc.kind, properties=native_props),
                    prov=proc_prov,
                )
            )
            add_rel(
                "CHANNEL_PROCESSED_BY",
                owner,
                proc.id,
                properties={"index": i},
                prov_ref=proc_base,
            )
            for param in proc.parameters:
                add_entity(
                    Entity(
                        id=param.id,
                        entity_type="PARAMETER",
                        name=param.name,
                        properties=_non_none(
                            value=param.value,
                            normalized_value=param.normalized_value,
                            unit=param.unit,
                            is_automated=param.is_automated,
                            is_visible_to_host=param.is_visible_to_host,
                        ),
                        native=NativeRef(daw=daw, native_type="parameter"),
                        prov={"*": proc_base},
                    )
                )
                # The registry has no HAS_PARAMETER; CONTAINS with an explicit
                # kind tag keeps the vocabulary small without losing meaning.
                add_rel(
                    "CONTAINS",
                    proc.id,
                    param.id,
                    properties={"kind": "parameter"},
                    prov_ref=proc_base,
                )

    # -- scenes -----------------------------------------------------------------
    scene_ids: set[str] = set()
    for scene in session.scenes:
        scene_prov = store.add_nested(scene.provenance)
        add_entity(
            Entity(
                id=scene.id,
                entity_type="STRUCTURAL_CONTAINER",
                name=scene.name,
                properties=_non_none(index=scene.index, tempo=scene.tempo),
                native=NativeRef(
                    daw=daw,
                    native_type="scene",
                    properties=dict(nested.to_dict(scene.extras)) if scene.extras else {},
                ),
                prov={"*": scene_prov},
            )
        )
        scene_ids.add(scene.id)
        add_rel("CONTAINS", project_id, scene.id, properties={"kind": "scene"}, prov_ref=scene_prov)

    # -- clips + media assets ----------------------------------------------------
    assets_by_path: dict[str, str] = {}
    for track in session.tracks:
        container = track_entity_of[track.id]
        for clip in track.clips:
            clip_prov = store.add_nested(clip.provenance)
            native_props = dict(nested.to_dict(clip.extras)) if clip.extras else {}
            if clip.raw_source is not None:
                native_props["raw_source"] = nested.to_dict(clip.raw_source)
            add_entity(
                Entity(
                    id=clip.id,
                    entity_type="TEMPORAL_OBJECT",
                    name=clip.name,
                    properties=_non_none(
                        clip_type=clip.clip_type,
                        # Unit-tagged time fields, copied as-is and never
                        # coerced between beats and seconds domains.
                        start_time_beats=clip.start_time_beats,
                        length_beats=clip.length_beats,
                        loop_start_beats=clip.loop_start_beats,
                        loop_end_beats=clip.loop_end_beats,
                        warp_enabled=clip.warp_enabled,
                        midi_note_count=clip.midi_note_count,
                        position_seconds=clip.position_seconds,
                        length_seconds=clip.length_seconds,
                        source_type=clip.source_type,
                        audio_file=clip.audio_file,
                    ),
                    native=NativeRef(daw=daw, native_type=clip.clip_type, properties=native_props),
                    prov={"*": clip_prov},
                )
            )
            add_rel(
                "TRACK_CONTAINS_TEMPORAL_OBJECT",
                container,
                clip.id,
                prov_ref=clip_prov,
            )
            if clip.audio_file:
                asset_id = assets_by_path.get(clip.audio_file)
                if asset_id is None:
                    asset_id = f"asset:{_slug(clip.audio_file)}"
                    assets_by_path[clip.audio_file] = asset_id
                    add_entity(
                        Entity(
                            id=asset_id,
                            entity_type="MEDIA_ASSET",
                            name=basename(clip.audio_file),
                            properties={"path": clip.audio_file},
                            native=NativeRef(daw=daw, native_type=clip.source_type or "audio_file"),
                            prov={"*": clip_prov},
                        )
                    )
                add_rel("REFERENCES_ASSET", clip.id, asset_id, prov_ref=clip_prov)
            if clip.scene_id and clip.scene_id in scene_ids:
                add_rel(
                    "CONTAINS",
                    clip.scene_id,
                    clip.id,
                    properties={"kind": "scene_member"},
                    prov_ref=clip_prov,
                )

    # -- routes ---------------------------------------------------------------
    route_evidence: list[str] = []
    for route in session.routes:
        route_prov = store.add_nested(route.provenance)
        route_evidence.append(route.provenance.observability)

        def _endpoint(track_id: Optional[str], label: Optional[str], suffix: str) -> str:
            if track_id is not None and track_id in track_entity_of:
                return channel_of.get(track_id, track_entity_of[track_id])
            # Unresolved endpoint: keep it as a first-class entity whose
            # identity is explicitly UNKNOWN instead of dropping the edge.
            endpoint_id = route.id if suffix == "source" else f"{route.id}:{suffix}"
            if endpoint_id not in entity_by_id:
                add_entity(
                    Entity(
                        id=endpoint_id,
                        entity_type="ROUTING_ENDPOINT",
                        name=label,
                        native=NativeRef(daw=daw, native_type="routing_endpoint"),
                        prov={"*": route_prov},
                        availability={"identity": "UNKNOWN"},
                    )
                )
            return endpoint_id

        src = _endpoint(route.source_track_id, route.source_name, "source")
        dst = _endpoint(route.target_track_id, route.target_name, "target")
        rel_type = (
            "CHANNEL_SENDS_TO"
            if route.route_type in ("send", "receive")
            else "CHANNEL_ROUTES_TO"
        )
        properties = _non_none(
            route_type=route.route_type,
            send_mode=route.send_mode,
            volume=route.volume,
            volume_db=route.volume_db,
            pan=route.pan,
            mute=route.mute,
            enabled=route.enabled,
        )
        if route.extras:
            properties.update(nested.to_dict(route.extras))
        add_rel(rel_type, src, dst, properties=properties, prov_ref=route_prov)

    # -- hidden-state markers ---------------------------------------------------
    if session.hidden_state_markers:
        ext["hidden_state_markers"] = [m.model_dump() for m in session.hidden_state_markers]
    for marker in session.hidden_state_markers:
        target = entity_by_id.get(marker.target_id)
        if target is None and marker.target_id in channel_of:
            target = entity_by_id.get(channel_of[marker.target_id])
        if target is None:
            warnings.append(
                f"hidden-state marker {marker.id!r} targets unknown entity "
                f"{marker.target_id!r}; recorded in extensions only."
            )
            continue
        field = marker.hidden_state_type
        if field.startswith("hidden_"):
            field = field[len("hidden_"):]
        hidden_prov = store.add(
            "HIDDEN",
            explanation=marker.description,
            warnings=(marker.consequence,) if marker.consequence else (),
        )
        target.availability[field] = "INACCESSIBLE"
        target.prov[field] = hidden_prov

    # -- evidence bundle ----------------------------------------------------------
    if session.evidence is not None:
        evidence = session.evidence
        ext["evidence"] = evidence.model_dump()
        for note in evidence.channel_strip_notes:
            note_prov = store.add(
                "ANNOTATED",
                capture_method="channel_strip_note",
                confidence=note.confidence,
                explanation="User-asserted channel-strip description; never a DAW fact.",
            )
            add_entity(
                Entity(
                    id=note.id,
                    entity_type="ANNOTATION",
                    name=note.track_name,
                    properties=_non_none(
                        role=note.role,
                        plugins=note.plugins or None,
                        sends=note.sends or None,
                        bus=note.bus,
                        notes=note.notes,
                    ),
                    native=NativeRef(daw=daw, native_type="channel_strip_note"),
                    prov={"*": note_prov},
                )
            )
        for audio in evidence.audio_files:
            audio_prov = store.add("OBSERVED", capture_method="exported_audio")
            audio_entity = add_entity(
                Entity(
                    id=audio.id,
                    entity_type="MEDIA_ASSET",
                    name=audio.file_name,
                    properties=_non_none(
                        path=audio.file_path,
                        duration_seconds=audio.duration_seconds,
                        sample_rate=audio.sample_rate,
                        is_mixdown=audio.is_mixdown,
                        is_reference=audio.is_reference,
                    ),
                    native=NativeRef(
                        daw=daw,
                        native_type="audio_evidence",
                        properties=audio.model_dump(),
                    ),
                    prov={"*": audio_prov},
                )
            )
            if audio.inferred_track_name or audio.inferred_role:
                inferred_prov = store.add(
                    "INFERRED",
                    confidence=audio.confidence,
                    explanation=audio.role_explanation,
                )
                if audio.inferred_track_name:
                    audio_entity.properties["inferred_track_name"] = audio.inferred_track_name
                    audio_entity.prov["inferred_track_name"] = inferred_prov
                if audio.inferred_role:
                    audio_entity.properties["inferred_role"] = audio.inferred_role
                    audio_entity.prov["inferred_role"] = inferred_prov
        observations: list[tuple[str, str, dict[str, Any]]] = []
        if evidence.stem_sum_reconciliation is not None:
            recon = evidence.stem_sum_reconciliation
            observations.append(
                (recon.id, "stem_sum_reconciliation", recon.model_dump())
            )
        for comparison in evidence.reference_comparisons:
            observations.append(
                (comparison.id, "reference_comparison", comparison.model_dump())
            )
        for obs_id, obs_type, payload in observations:
            obs_prov = store.add(
                "INFERRED",
                capture_method="derived_computation",
                explanation=f"Signal-level {obs_type.replace('_', ' ')} computed from evidence audio.",
            )
            add_entity(
                Entity(
                    id=obs_id,
                    entity_type="OBSERVATION",
                    name=obs_type,
                    properties=payload,
                    native=NativeRef(daw=daw, native_type=obs_type),
                    prov={"*": obs_prov},
                )
            )

    # -- analyzer-side artifacts kept as extensions --------------------------------
    if session.descriptors:
        ext["descriptors"] = [d.model_dump() for d in session.descriptors]
    if session.recommendations:
        ext["recommendations"] = [r.model_dump() for r in session.recommendations]

    # -- native payload: sibling file, never embedded -------------------------------
    if session.native is not None:
        if native_file is not None:
            ext["native_file"] = {"path": native_file, "sha256": native_sha256}
        else:
            ext["native_payload_omitted"] = True

    # -- coverage (approximate but honest; see module docstring) --------------------
    def _coverage(evidence_kinds: list[str]) -> DomainCoverage:
        return DomainCoverage(
            applicable=len(evidence_kinds),
            observed=sum(1 for e in evidence_kinds if e == "observed"),
            inferred=sum(1 for e in evidence_kinds if e in ("inferred", "derived")),
            hidden=sum(1 for e in evidence_kinds if e == "hidden"),
        )

    coverage = {
        "structure": _coverage(track_evidence),
        "channel": _coverage(channel_evidence),
        "processing": _coverage(processor_evidence),
        "routing": _coverage(route_evidence),
    }

    extensions: dict[str, dict[str, Any]] = {daw: ext} if ext else {}

    return CanonicalDAWSnapshot(
        snapshot_id=snapshot_id or f"{daw}:{_slug(session.name)}:snapshot",
        created_at=created_at,
        source=source,
        project=project_id,
        entities=entities,
        relationships=relationships,
        capabilities=capabilities,
        coverage=coverage,
        provenance=store.records(),
        extensions=extensions,
        warnings=warnings,
    )
