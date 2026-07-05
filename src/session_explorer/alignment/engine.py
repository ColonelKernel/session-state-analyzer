"""The explainable cross-DAW alignment engine (P4).

``align(snapshot_a, snapshot_b)`` proposes matches between the *strips* of two
snapshots. A strip is the alignment unit: a TRACK together with the CHANNEL it
uses (``TRACK_USES_CHANNEL``), a standalone CHANNEL (returns/masters), or a
TRACK that honestly has no channel (Logic evidence). TRACK ≠ CHANNEL stays
true in the data; alignment just refuses to double-count the two halves of one
mixer strip as rival candidates.

Signals — explainable only, no embeddings, every fired signal contributes a
human-readable reason:

===========================================  ======  =====================================
signal                                        weight  reason (example)
===========================================  ======  =====================================
shared registry concept (both sides declare)   0.45  "both are effect_return implementations
shared registry concept (≥1 side derived)      0.40   (return_track ↔ fx_channel)"
name token match (``core.matching``)         ≤ 0.30  "name tokens overlap: reverb"
entity shape (both have CHANNEL / same type)   0.10  "both expose a mixer channel"
both receive ≥1 send (observed or annotated)   0.10  "both receive ≥1 send"
both send to ≥1 destination                    0.05  "both send to ≥1 destination"
both route to the main output                  0.10  "both route to the main output"
shared processor family                        0.15  "both carry a reverb-family processor
                                                      (ReaVerbate ↔ Space Designer)"
media asset content-hash equality              0.25  "linked media assets share content hash"
===========================================  ======  =====================================

Scores are capped at 1.0. Concept membership itself is explainable: a strip is
an ``effect_return`` because its snapshot *declares* the role/native type, or
because the registry says this DAW implements returns as plain tracks and the
strip's topology witnesses it (receives ≥1 send + carries a reverb-family
processor) — and the derivation is spelled out in the reason.

Statuses: score ≥ 0.80 with ≥ 3 reasons → PROBABLE; score ≥ 0.55 → POSSIBLE;
otherwise UNMATCHED. When the two best candidates sit within 0.05 of each
other the engine returns CONFLICTING instead of silently picking one.
CONFIRMED is never produced by scoring — only :func:`confirm` (a user action)
yields it, as an ANNOTATED provenance payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Optional

from canonical_snapshot import CanonicalDAWSnapshot
from canonical_snapshot.models import Entity

from session_explorer.core.matching import (
    identity_tokens,
    name_match_confidence,
    tokens_equal,
)
from session_explorer.registry import ConceptRegistry, get_registry

from .models import AlignmentResult

# Status thresholds (see module docstring).
PROBABLE_SCORE = 0.80
PROBABLE_MIN_REASONS = 3
POSSIBLE_SCORE = 0.55
CONFLICT_MARGIN = 0.05

# Signal weights.
W_CONCEPT_DECLARED = 0.45
W_CONCEPT_DERIVED = 0.40
W_NAME = 0.30
W_SHAPE = 0.10
W_RECEIVES = 0.10
W_SENDS = 0.05
W_ROUTES_MAIN = 0.10
W_PROC_FAMILY = 0.15
W_MEDIA_HASH = 0.25

# Processor-family buckets: adapters spell families differently ("Ambience",
# "reverb", "delay"); buckets make the comparison honest without a taxonomy.
_FAMILY_BUCKETS = {
    "ambience": "reverb", "reverb": "reverb", "delay": "reverb", "echo": "reverb",
    "eq": "eq",
    "dynamics": "dynamics",
    "saturation": "saturation",
    "modulation": "modulation",
    "utility": "utility",
    "instrument": "instrument",
}

_HASH_KEYS = ("sha256", "content_hash", "hash")

_SOURCE_ROLE_SUFFIX = "_source"


def _bucket(family: Optional[str]) -> Optional[str]:
    if not family:
        return None
    return _FAMILY_BUCKETS.get(family.strip().lower(), family.strip().lower())


@dataclass
class _Strip:
    """One alignment unit: the lane+signal-path surface of a mixer strip."""

    primary_id: str
    daw: str
    name: Optional[str]
    member_ids: set[str] = field(default_factory=set)
    entity_types: set[str] = field(default_factory=set)
    native_types: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)
    has_channel: bool = False
    primary_type: str = "TRACK"
    receives_observed: bool = False
    receives_annotated: Optional[str] = None  # reason detail
    sends_observed: bool = False
    sends_annotated: Optional[str] = None
    routes_to_main: bool = False
    routes_to_main_via: Optional[str] = None
    processors: list[tuple[str, Optional[str]]] = field(default_factory=list)  # (name, bucket)
    media_hashes: set[str] = field(default_factory=set)
    # Filled by _classify:
    concept_id: Optional[str] = None
    concept_declared: bool = False
    concept_detail: Optional[str] = None

    @property
    def processor_buckets(self) -> set[str]:
        return {b for _, b in self.processors if b}

    def processor_named(self, bucket: str) -> Optional[str]:
        for name, b in self.processors:
            if b == bucket:
                return name
        return None


def _entity_native_type(entity: Entity) -> Optional[str]:
    return entity.native.native_type if entity.native else None


def build_strips(
    snapshot: CanonicalDAWSnapshot, registry: Optional[ConceptRegistry] = None
) -> list[_Strip]:
    """Extract and classify the snapshot's strips (see module docstring)."""
    registry = registry or get_registry()
    daw = snapshot.source.daw
    by_id = {e.id: e for e in snapshot.entities}

    channel_of: dict[str, str] = {}
    used_channels: set[str] = set()
    for rel in snapshot.relationships:
        if rel.rel_type == "TRACK_USES_CHANNEL":
            channel_of[rel.source] = rel.target
            used_channels.add(rel.target)

    strips: list[_Strip] = []
    for entity in snapshot.entities:
        if entity.entity_type == "TRACK":
            members = [entity]
            channel = by_id.get(channel_of.get(entity.id, ""))
            if channel is not None:
                members.append(channel)
            strips.append(_make_strip(entity, members, daw))
        elif entity.entity_type == "CHANNEL" and entity.id not in used_channels:
            strips.append(_make_strip(entity, [entity], daw))

    member_index = {mid: strip for strip in strips for mid in strip.member_ids}

    for rel in snapshot.relationships:
        if rel.rel_type == "CHANNEL_SENDS_TO":
            if rel.target in member_index:
                member_index[rel.target].receives_observed = True
            if rel.source in member_index:
                member_index[rel.source].sends_observed = True
        elif rel.rel_type == "CHANNEL_ROUTES_TO":
            strip = member_index.get(rel.source)
            target = by_id.get(rel.target)
            if strip and target and "main_output" in target.semantic_roles:
                strip.routes_to_main = True
                strip.routes_to_main_via = f"CHANNEL_ROUTES_TO → {target.name or rel.target}"
        elif rel.rel_type == "CHANNEL_PROCESSED_BY":
            strip = member_index.get(rel.source)
            proc = by_id.get(rel.target)
            if strip and proc:
                strip.processors.append(
                    (proc.name or rel.target, _bucket(proc.properties.get("family")))
                )
        elif rel.rel_type in ("TRACK_CONTAINS_TEMPORAL_OBJECT", "REFERENCES_ASSET"):
            pass  # handled below via the clip→asset walk

    # Media hashes: strip → clip → asset (only when the adapter shipped a hash).
    clips_of: dict[str, list[str]] = {}
    assets_of_clip: dict[str, list[str]] = {}
    for rel in snapshot.relationships:
        if rel.rel_type == "TRACK_CONTAINS_TEMPORAL_OBJECT":
            clips_of.setdefault(rel.source, []).append(rel.target)
        elif rel.rel_type == "REFERENCES_ASSET":
            assets_of_clip.setdefault(rel.source, []).append(rel.target)
    for strip in strips:
        for member in strip.member_ids:
            for clip_id in clips_of.get(member, []):
                for asset_id in assets_of_clip.get(clip_id, []):
                    asset = by_id.get(asset_id)
                    if asset is None:
                        continue
                    for key in _HASH_KEYS:
                        value = asset.properties.get(key)
                        if value:
                            strip.media_hashes.add(str(value))

    # The ANNOTATED pathway (Logic): channel-strip notes assert sends the
    # snapshot cannot observe. A note whose `sends` labels match a strip's
    # name makes that strip an annotated send *destination*; a note matching
    # the strip's own name with non-empty `sends` makes it an annotated
    # sender. Never promoted to observed — the reason strings say "annotated".
    for entity in snapshot.entities:
        if entity.entity_type != "ANNOTATION":
            continue
        sends = entity.properties.get("sends") or []
        if not isinstance(sends, list) or not sends:
            continue
        for strip in strips:
            if strip.name and name_match_confidence(entity.name, strip.name) >= 0.75:
                if not strip.sends_observed and strip.sends_annotated is None:
                    strip.sends_annotated = (
                        f"channel-strip note {entity.name!r} asserts sends {sends}"
                    )
            for label in sends:
                if strip.name and name_match_confidence(str(label), strip.name) >= 0.5:
                    if not strip.receives_observed and strip.receives_annotated is None:
                        strip.receives_annotated = (
                            f"channel-strip note {entity.name!r} asserts a send "
                            f"{label!r} matching this strip"
                        )

    for strip in strips:
        _classify(strip, registry)
    return strips


def _make_strip(primary: Entity, members: list[Entity], daw: str) -> _Strip:
    strip = _Strip(
        primary_id=primary.id,
        daw=daw,
        name=primary.name,
        primary_type=primary.entity_type,
    )
    for member in members:
        strip.member_ids.add(member.id)
        strip.entity_types.add(member.entity_type)
        strip.roles.update(member.semantic_roles)
        native_type = _entity_native_type(member)
        if native_type:
            strip.native_types.add(native_type)
        if member.entity_type == "CHANNEL":
            strip.has_channel = True
        if member.native and member.native.properties.get("main_send"):
            strip.routes_to_main = True
            strip.routes_to_main_via = "native main_send flag"
    return strip


def _classify(strip: _Strip, registry: ConceptRegistry) -> None:
    """Assign the strip's primary concept, with an explainable derivation."""
    native_concepts: list[str] = []
    for native_type in strip.native_types:
        native_concepts.extend(registry.concepts_for_native(strip.daw, native_type))

    def declared(concept: str) -> bool:
        return concept in strip.roles or concept in native_concepts

    if declared("effect_return"):
        strip.concept_id, strip.concept_declared = "effect_return", True
        strip.concept_detail = (
            "declared by the snapshot (semantic role / native type)"
        )
        return
    receives = strip.receives_observed or strip.receives_annotated is not None
    if (
        receives
        and "reverb" in strip.processor_buckets
        and "main_output" not in strip.roles
    ):
        strip.concept_id, strip.concept_declared = "effect_return", False
        noun = registry.native_noun("effect_return", strip.daw) or "track"
        strip.concept_detail = (
            f"derived: receives ≥1 send and carries a reverb-family processor "
            f"({strip.processor_named('reverb')}) — {strip.daw} implements "
            f"effect returns as plain {noun}s (registry: "
            f"{registry.equivalence('effect_return', strip.daw)})"
        )
        return
    for concept in ("main_output", "submix", "scene"):
        if declared(concept):
            strip.concept_id, strip.concept_declared = concept, True
            strip.concept_detail = "declared by the snapshot"
            return
    if "audio_source" in native_concepts or any(
        role.endswith(_SOURCE_ROLE_SUFFIX) for role in strip.roles
    ):
        strip.concept_id, strip.concept_declared = "audio_source", True
        strip.concept_detail = "declared by the snapshot (native type / *_source role)"
        return
    strip.concept_id = "track" if strip.primary_type == "TRACK" else "channel"
    strip.concept_declared = True
    strip.concept_detail = "fallback: canonical entity type"


def _shared_tokens(a: Optional[str], b: Optional[str]) -> list[str]:
    ta, tb = identity_tokens(a), identity_tokens(b)
    return sorted(t for t in ta if any(tokens_equal(t, u) for u in tb))


def _noun(strip: _Strip, registry: ConceptRegistry) -> str:
    noun = registry.native_noun(strip.concept_id or "", strip.daw)
    if noun:
        return noun
    return next(iter(sorted(strip.native_types)), strip.primary_type.lower())


def _score_pair(
    a: _Strip, b: _Strip, registry: ConceptRegistry
) -> tuple[float, list[str], Optional[str]]:
    score = 0.0
    reasons: list[str] = []
    concept_id: Optional[str] = None

    # 1. Registry concept.
    if a.concept_id and a.concept_id == b.concept_id:
        concept_id = a.concept_id
        both_declared = a.concept_declared and b.concept_declared
        score += W_CONCEPT_DECLARED if both_declared else W_CONCEPT_DERIVED
        reason = (
            f"both are {concept_id} implementations "
            f"({_noun(a, registry)} ↔ {_noun(b, registry)})"
        )
        for side in (a, b):
            if not side.concept_declared and side.concept_detail:
                reason += f"; {side.daw}: {side.concept_detail}"
        reasons.append(reason)

    # 2. Name tokens.
    name_conf = name_match_confidence(a.name, b.name)
    if name_conf > 0:
        score += W_NAME * name_conf
        if name_conf >= 0.5:
            shared = ", ".join(_shared_tokens(a.name, b.name)) or "(full name)"
            reasons.append(f"name tokens overlap: {shared}")

    # 3. Entity shape.
    if a.has_channel and b.has_channel:
        score += W_SHAPE
        reasons.append("both expose a mixer channel (signal-path surface)")
    elif a.primary_type == b.primary_type:
        score += W_SHAPE
        reasons.append(f"same canonical entity type ({a.primary_type})")

    # 4. Both receive sends.
    a_recv = a.receives_observed or a.receives_annotated is not None
    b_recv = b.receives_observed or b.receives_annotated is not None
    if a_recv and b_recv:
        score += W_RECEIVES
        reason = "both receive ≥1 send"
        for side in (a, b):
            if not side.receives_observed and side.receives_annotated:
                reason += f" ({side.daw}: annotated — {side.receives_annotated})"
        reasons.append(reason)

    # 5. Both send somewhere.
    a_send = a.sends_observed or a.sends_annotated is not None
    b_send = b.sends_observed or b.sends_annotated is not None
    if a_send and b_send:
        score += W_SENDS
        reason = "both send to ≥1 destination"
        for side in (a, b):
            if not side.sends_observed and side.sends_annotated:
                reason += f" ({side.daw}: annotated — {side.sends_annotated})"
        reasons.append(reason)

    # 6. Both route to the main output.
    if a.routes_to_main and b.routes_to_main:
        score += W_ROUTES_MAIN
        reasons.append(
            "both route to the main output "
            f"({a.routes_to_main_via} ↔ {b.routes_to_main_via})"
        )

    # 7. Shared processor family.
    shared_buckets = a.processor_buckets & b.processor_buckets
    if shared_buckets:
        score += W_PROC_FAMILY
        bucket = "reverb" if "reverb" in shared_buckets else sorted(shared_buckets)[0]
        reasons.append(
            f"both carry a {bucket}-family processor "
            f"({a.processor_named(bucket)} ↔ {b.processor_named(bucket)})"
        )

    # 8. Media content hashes.
    shared_hashes = a.media_hashes & b.media_hashes
    if shared_hashes:
        score += W_MEDIA_HASH
        digest = sorted(shared_hashes)[0]
        reasons.append(f"linked media assets share content hash {digest[:12]}…")

    return min(1.0, score), reasons, concept_id


def align(
    snapshot_a: CanonicalDAWSnapshot,
    snapshot_b: CanonicalDAWSnapshot,
    *,
    registry: Optional[ConceptRegistry] = None,
) -> list[AlignmentResult]:
    """Align every strip of ``snapshot_a`` against ``snapshot_b``.

    Directional: one result per source strip in A (align(B, A) gives the
    other direction). See the module docstring for signals and thresholds.
    """
    registry = registry or get_registry()
    strips_a = build_strips(snapshot_a, registry)
    strips_b = build_strips(snapshot_b, registry)

    results: list[AlignmentResult] = []
    for strip in strips_a:
        scored = sorted(
            (
                (*_score_pair(strip, candidate, registry), candidate)
                for candidate in strips_b
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        base = AlignmentResult(
            source_entity=strip.primary_id,
            target_entity=None,
            status="UNMATCHED",
            confidence=None,
            source_daw=strip.daw,
            source_name=strip.name,
            target_daw=snapshot_b.source.daw,
        )
        if not scored:
            base.reasons = ["target snapshot has no strips to align against"]
            results.append(base)
            continue

        best_score, best_reasons, best_concept, best_strip = scored[0]
        if best_score < POSSIBLE_SCORE:
            base.confidence = round(best_score, 3)
            base.reasons = [
                f"no candidate reached the POSSIBLE floor ({POSSIBLE_SCORE}); "
                f"best was {best_strip.name!r} at {best_score:.2f}"
            ]
            results.append(base)
            continue

        result = replace(
            base,
            target_entity=best_strip.primary_id,
            target_name=best_strip.name,
            confidence=round(best_score, 3),
            concept_id=best_concept,
            reasons=list(best_reasons),
        )
        runner_up = scored[1] if len(scored) > 1 else None
        if (
            runner_up is not None
            and runner_up[0] >= POSSIBLE_SCORE
            and best_score - runner_up[0] < CONFLICT_MARGIN
        ):
            result.status = "CONFLICTING"
            result.reasons = [
                f"two candidates within {CONFLICT_MARGIN}: "
                f"{best_strip.name!r} ({best_score:.2f}) vs "
                f"{runner_up[3].name!r} ({runner_up[0]:.2f}) — refusing to pick"
            ] + result.reasons
        elif best_score >= PROBABLE_SCORE and len(best_reasons) >= PROBABLE_MIN_REASONS:
            result.status = "PROBABLE"
        else:
            result.status = "POSSIBLE"
        results.append(result)
    return results


def confirm(result: AlignmentResult, *, confirmed_by: str = "user") -> dict[str, Any]:
    """Turn an engine proposal into a user-confirmed alignment.

    Confirmation is an annotation, not a computation: the return value is an
    ANNOTATED :class:`~canonical_snapshot.models.ProvenanceRecord` payload
    (plain dict) that the workbench can persist alongside the pair later.
    The engine never produces CONFIRMED on its own.
    """
    if result.target_entity is None:
        raise ValueError("cannot confirm an alignment that has no target entity")
    result.status = "CONFIRMED"
    return {
        "id": f"prov:alignment:{result.source_entity}__{result.target_entity}",
        "evidence": "ANNOTATED",
        "capture_method": "user_alignment_confirmation",
        "source_stability": "MANUAL",
        "source_ref": f"{result.source_entity} -> {result.target_entity}",
        "confidence": result.confidence,
        "explanation": (
            f"Alignment confirmed by {confirmed_by}. Engine signals: "
            + "; ".join(result.reasons)
        ),
        "warnings": [],
    }
