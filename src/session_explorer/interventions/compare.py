"""Comparing two canonical snapshots into a readable state→audio story.

Three steps, each a pure function over the frozen inputs:

1. :func:`snapshot_delta` — the *structural* difference (entities by id,
   relationships by ``(rel_type, source, target)``), surfacing the added
   ``CHANNEL_SENDS_TO`` edges specifically because they are the routing change.
2. :func:`explain_signal_flow` — *why* the sound changes: for each new send it
   traces source channel → target channel → the target's processors → the
   target's output, reading names and roles from the entities (never
   hardcoded), and composes one plain sentence plus the path chain.
3. :func:`acoustic_delta` — *how much*: level (RMS/peak in dB), brightness
   (spectral centroid), and loudness (LUFS) deltas between the two renders'
   descriptors, each with a direction word.

:func:`compare_intervention` runs all three and pairs them with the known
:class:`Intervention` into an :class:`InterventionComparison`.
"""

from __future__ import annotations

import math
from typing import Optional

from canonical_snapshot import CanonicalDAWSnapshot, Entity, Relationship

from session_explorer.core.models import AudioDescriptorSet
from session_explorer.loaders.bundle import SnapshotBundle

from .models import (
    AcousticDelta,
    AcousticMetric,
    DeltaRecord,
    Intervention,
    InterventionComparison,
    Render,
    SignalFlowChange,
    StateDelta,
)


# ---------------------------------------------------------------------------
# State delta
# ---------------------------------------------------------------------------


def _entity_label(entity: Entity) -> str:
    return entity.name or entity.id


def _entity_record(entity: Entity) -> DeltaRecord:
    return DeltaRecord(id=entity.id, type=entity.entity_type, label=_entity_label(entity))


def _rel_key(rel: Relationship) -> tuple[str, str, str]:
    return (rel.rel_type, rel.source, rel.target)


def _rel_label(rel: Relationship, snapshot: CanonicalDAWSnapshot) -> str:
    """A readable edge label using entity names where the snapshot has them."""
    src = snapshot.entity_by_id(rel.source)
    dst = snapshot.entity_by_id(rel.target)
    src_name = _entity_label(src) if src else rel.source
    dst_name = _entity_label(dst) if dst else rel.target
    label = f"{src_name} → {dst_name}"
    if rel.rel_type == "CHANNEL_SENDS_TO":
        pre = rel.properties.get("pre_fader")
        if pre is not None:
            label += " (pre-fader)" if pre else " (post-fader)"
    return label


def _rel_record(rel: Relationship, snapshot: CanonicalDAWSnapshot) -> DeltaRecord:
    return DeltaRecord(id=rel.id, type=rel.rel_type, label=_rel_label(rel, snapshot))


def _entity_signature(entity: Entity) -> tuple:
    return (
        entity.name,
        entity.entity_type,
        tuple(sorted(entity.semantic_roles)),
        tuple(sorted((k, str(v)) for k, v in entity.properties.items())),
    )


def snapshot_delta(
    before: CanonicalDAWSnapshot, after: CanonicalDAWSnapshot
) -> StateDelta:
    """Structural diff of two snapshots.

    Entities are keyed by id (added / removed / changed); relationships by
    ``(rel_type, source, target)`` (added / removed). A ``changed`` entity is
    one present in both whose name, type, roles, or properties differ. The
    added ``CHANNEL_SENDS_TO`` edges are also collected into ``added_sends`` —
    the intervention this comparison is designed to surface.
    """
    before_entities = {e.id: e for e in before.entities}
    after_entities = {e.id: e for e in after.entities}

    added_entities = [
        _entity_record(after_entities[eid])
        for eid in after_entities
        if eid not in before_entities
    ]
    removed_entities = [
        _entity_record(before_entities[eid])
        for eid in before_entities
        if eid not in after_entities
    ]
    changed = [
        _entity_record(after_entities[eid])
        for eid in after_entities
        if eid in before_entities
        and _entity_signature(before_entities[eid]) != _entity_signature(after_entities[eid])
    ]

    before_rels = {_rel_key(r): r for r in before.relationships}
    after_rels = {_rel_key(r): r for r in after.relationships}

    added_relationships = [
        _rel_record(after_rels[key], after)
        for key in after_rels
        if key not in before_rels
    ]
    removed_relationships = [
        _rel_record(before_rels[key], before)
        for key in before_rels
        if key not in after_rels
    ]
    added_sends = [
        _rel_record(after_rels[key], after)
        for key in after_rels
        if key not in before_rels and key[0] == "CHANNEL_SENDS_TO"
    ]

    return StateDelta(
        added_entities=added_entities,
        removed_entities=removed_entities,
        added_relationships=added_relationships,
        removed_relationships=removed_relationships,
        changed=changed,
        added_sends=added_sends,
    )


# ---------------------------------------------------------------------------
# Signal-flow explanation
# ---------------------------------------------------------------------------


def _source_noun(channel: Entity, snapshot: CanonicalDAWSnapshot) -> str:
    """A readable noun for a send's source: its role ("vocal") else its name.

    Roles are read off the channel and off the TRACK that uses it (Cubase puts
    ``vocal_source`` on the track, not the channel). A ``*_source`` role like
    ``vocal_source`` becomes "vocal"; otherwise fall back to the entity name.
    """
    roles = list(channel.semantic_roles)
    for rel in snapshot.relationships_of_type("TRACK_USES_CHANNEL"):
        if rel.target == channel.id:
            track = snapshot.entity_by_id(rel.source)
            if track is not None:
                roles += track.semantic_roles
    for role in roles:
        if role.endswith("_source"):
            noun = role[: -len("_source")].replace("_", " ").strip()
            if noun:
                return noun
    return channel.name or channel.id


def _output_phrase(entity: Optional[Entity]) -> str:
    """Describe a route destination: "the main output" when it plays that role."""
    if entity is None:
        return "its output"
    if "main_output" in entity.semantic_roles:
        return "the main output"
    return f"'{entity.name or entity.id}'"


def explain_signal_flow(
    after: CanonicalDAWSnapshot, delta: StateDelta
) -> SignalFlowChange:
    """Trace each newly-added send into one readable sentence + a path chain.

    For every added ``CHANNEL_SENDS_TO`` edge: read the source channel, the
    target channel, the target's ``CHANNEL_PROCESSED_BY`` processors and its
    ``CHANNEL_ROUTES_TO`` destination, then compose a sentence of the form
    "The <source> channel now sends to '<target>', whose <processors> sums back
    to <output> — so the <source> gains an effect it did not have before." The
    ``path`` is ``[source, target, processor(s)…, output]``. Nothing is
    hardcoded: names and roles come from the entities.
    """
    if not delta.added_sends:
        return SignalFlowChange(
            summary="No new send was added; the signal path is unchanged.",
            path=[],
        )

    sentences: list[str] = []
    path: list[str] = []

    for send in delta.added_sends:
        # send.id is the added relationship's id; recover the edge in `after`.
        edge = next((r for r in after.relationships if r.id == send.id), None)
        if edge is None:
            continue
        source = after.entity_by_id(edge.source)
        target = after.entity_by_id(edge.target)
        if source is None or target is None:
            continue

        source_noun = _source_noun(source, after)
        target_name = target.name or target.id

        processors = [
            after.entity_by_id(r.target)
            for r in after.relationships_of_type("CHANNEL_PROCESSED_BY")
            if r.source == target.id
        ]
        processor_names = [p.name for p in processors if p is not None and p.name]

        route_dest = next(
            (
                after.entity_by_id(r.target)
                for r in after.relationships_of_type("CHANNEL_ROUTES_TO")
                if r.source == target.id
            ),
            None,
        )

        if processor_names:
            proc_phrase = _join(processor_names)
            effect_kind = _effect_kind(processor_names[0])
            why = (
                f"whose {proc_phrase} {'sum' if len(processor_names) > 1 else 'sums'} "
                f"back to {_output_phrase(route_dest)}"
            )
            gains = f"so the {source_noun} gains {effect_kind} it did not have before"
        else:
            why = f"which feeds {_output_phrase(route_dest)}"
            gains = f"so the {source_noun} now feeds a shared return it did not before"

        pre = edge.properties.get("pre_fader")
        fader = "post-fader " if pre is False else ("pre-fader " if pre else "")
        sentences.append(
            f"The {source_noun} channel now has a {fader}send to '{target_name}', "
            f"{why} — {gains}."
        )

        # Build the left-to-right chain once (first send drives the diagram).
        if not path:
            path = [source.name or source.id, target_name]
            path.extend(processor_names)
            if route_dest is not None:
                path.append(route_dest.name or route_dest.id)

    summary = " ".join(sentences) if sentences else (
        "A send was added, but its endpoints could not be resolved."
    )
    return SignalFlowChange(summary=summary, path=path)


def _join(names: list[str]) -> str:
    if len(names) == 1:
        return f"{names[0]} reverb" if _is_reverb(names[0]) else names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


_REVERB_HINTS = ("verb", "reverence", "plate", "hall", "room", "space")


def _is_reverb(name: str) -> bool:
    low = name.lower()
    return any(hint in low for hint in _REVERB_HINTS)


def _effect_kind(processor_name: str) -> str:
    """Plain-language name for what the return adds ("wet reverb" for a verb)."""
    return "wet reverb" if _is_reverb(processor_name) else f"the '{processor_name}' effect"


# ---------------------------------------------------------------------------
# Acoustic delta
# ---------------------------------------------------------------------------


def _db_ratio(before: Optional[float], after: Optional[float]) -> Optional[float]:
    """20·log10(after/before), guarding zeros and missing values."""
    if before is None or after is None or before <= 0 or after <= 0:
        return None
    return round(20.0 * math.log10(after / before), 3)


def _level_direction(delta_db: Optional[float]) -> Optional[str]:
    if delta_db is None:
        return None
    if delta_db > 0.5:
        return "louder"
    if delta_db < -0.5:
        return "quieter"
    return "unchanged"


def _bright_direction(delta_hz: Optional[float]) -> Optional[str]:
    if delta_hz is None:
        return None
    if delta_hz > 1.0:
        return "brighter"
    if delta_hz < -1.0:
        return "darker"
    return "unchanged"


def acoustic_delta(
    before: Optional[AudioDescriptorSet], after: Optional[AudioDescriptorSet]
) -> AcousticDelta:
    """The measured change in sound between two renders' descriptors.

    Level deltas (RMS, peak) are in dB via 20·log10 of the amplitude ratio;
    brightness is the spectral-centroid difference in Hz; loudness is the LUFS
    difference when both renders carry it. Every division guards against a
    zero or missing operand — an absent descriptor degrades to an unavailable
    delta, never a crash.
    """
    if before is None or after is None or not before.available or not after.available:
        return AcousticDelta(
            metrics=[],
            summary="No acoustic delta: at least one render has no descriptor.",
            available=False,
            unavailable_reason="A render descriptor is missing or unavailable.",
        )

    metrics: list[AcousticMetric] = []

    rms_db = _db_ratio(before.rms_mean, after.rms_mean)
    metrics.append(
        AcousticMetric(
            name="rms_db",
            before=before.rms_mean,
            after=after.rms_mean,
            delta=rms_db,
            unit="dB",
            direction=_level_direction(rms_db),
        )
    )

    peak_db = _db_ratio(before.peak_amplitude, after.peak_amplitude)
    metrics.append(
        AcousticMetric(
            name="peak_db",
            before=before.peak_amplitude,
            after=after.peak_amplitude,
            delta=peak_db,
            unit="dB",
            direction=_level_direction(peak_db),
        )
    )

    if before.spectral_centroid_mean is not None and after.spectral_centroid_mean is not None:
        centroid_delta = round(
            after.spectral_centroid_mean - before.spectral_centroid_mean, 3
        )
        metrics.append(
            AcousticMetric(
                name="spectral_centroid_hz",
                before=before.spectral_centroid_mean,
                after=after.spectral_centroid_mean,
                delta=centroid_delta,
                unit="Hz",
                direction=_bright_direction(centroid_delta),
            )
        )

    if before.integrated_loudness_lufs is not None and after.integrated_loudness_lufs is not None:
        lufs_delta = round(
            after.integrated_loudness_lufs - before.integrated_loudness_lufs, 2
        )
        metrics.append(
            AcousticMetric(
                name="lufs",
                before=before.integrated_loudness_lufs,
                after=after.integrated_loudness_lufs,
                delta=lufs_delta,
                unit="LUFS",
                direction=_level_direction(lufs_delta),
            )
        )

    return AcousticDelta(metrics=metrics, summary=_acoustic_summary(metrics))


def _acoustic_summary(metrics: list[AcousticMetric]) -> str:
    by_name = {m.name: m for m in metrics}
    parts: list[str] = []
    rms = by_name.get("rms_db")
    if rms is not None and rms.delta is not None and rms.direction:
        parts.append(f"{abs(rms.delta):.1f} dB {rms.direction} in level (RMS)")
    lufs = by_name.get("lufs")
    if lufs is not None and lufs.delta is not None and lufs.direction:
        parts.append(f"{abs(lufs.delta):.1f} LUFS {lufs.direction} overall")
    centroid = by_name.get("spectral_centroid_hz")
    if centroid is not None and centroid.delta is not None and centroid.direction:
        if centroid.direction == "unchanged":
            parts.append("essentially the same brightness")
        else:
            parts.append(f"{centroid.direction} ({abs(centroid.delta):.0f} Hz centroid shift)")
    if not parts:
        return "The renders are acoustically indistinguishable on these metrics."
    return "The render is " + ", and ".join(parts) + "."


# ---------------------------------------------------------------------------
# Whole comparison
# ---------------------------------------------------------------------------


def _descriptor_for(
    render_id: Optional[str], renders: Optional[dict[str, Render]]
) -> Optional[AudioDescriptorSet]:
    if render_id is None or not renders:
        return None
    render = renders.get(render_id)
    return render.descriptor if render is not None else None


def compare_intervention(
    before_bundle: SnapshotBundle,
    after_bundle: SnapshotBundle,
    intervention: Intervention,
    renders: Optional[dict[str, Render]] = None,
) -> InterventionComparison:
    """Run the whole state→audio chain for one controlled intervention.

    ``renders`` maps a ``render_id`` to its :class:`Render` (carrying the
    descriptor); the intervention's before/after observations name which render
    each side used, so the acoustic delta is pulled from the observations'
    renders. When no renders are supplied the acoustic delta degrades honestly.
    """
    delta = snapshot_delta(before_bundle.snapshot, after_bundle.snapshot)
    flow = explain_signal_flow(after_bundle.snapshot, delta)
    before_desc = _descriptor_for(intervention.before.render_id, renders)
    after_desc = _descriptor_for(intervention.after.render_id, renders)
    acoustic = acoustic_delta(before_desc, after_desc)
    return InterventionComparison(
        intervention=intervention,
        state_delta=delta,
        signal_flow=flow,
        acoustic_delta=acoustic,
    )
