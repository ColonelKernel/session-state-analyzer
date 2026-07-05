"""Cross-dialect semantic alignment (§18/§30) with applicability (§12).

Same-dialect diffing lives in :mod:`session_explorer.core.diff` ("what
changed?"). This module answers the cross-DAW question: given two canonical
sessions from *different* dialects, **what is semantically equivalent, what is
native-only, and what is not even applicable** to one side?

Alignment is concept-and-structure first, name second — two effect returns
align because they play the same production role and both receive sends, even
when one is an Ableton *return track* named "Reverb Return" and the other a
Cubase *FX channel* named "FX 1 — REVerence". Names only raise confidence and
disambiguate within a concept.

Every alignment states its ``basis`` so the UI can explain *why* two entities
were matched — this is an interpretable engine, not an opaque matcher.

Equivalence is deliberately conservative and never claims acoustic identity:

* ``exact``      — same concept, effectively identical (same name + structure)
* ``close``      — same concept and native object family (audio↔audio track)
* ``functional`` — same production role, different native object across
                   dialects (effect return ↔ FX channel)
* ``partial``    — related but with materially different native semantics
                   (Ableton group track vs Cubase group channel)
* ``none``       — no counterpart (surfaced as native-only)
* ``unknown``    — insufficient evidence to decide

Applicability (§12) is orthogonal to observability: a concept can be
*not_applicable* to a dialect (Cubase has no session-grid Scene) — a different
statement from *applicable but unobserved* (a hidden plug-in parameter). The
former is native difference; the latter is an observability gap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from .matching import name_match_confidence
from .models import CanonicalSession, Track

EquivalenceLevel = Literal["exact", "close", "functional", "partial", "none", "unknown"]
Applicability = Literal["applicable", "not_applicable", "unknown"]

MATCH_THRESHOLD = 0.34

# Semantic concept per canonical track kind — the unit of cross-dialect
# comparison. ``effect_return`` is the flagship: Ableton return tracks and
# Cubase FX channels both map to canonical ``kind="return"``.
_CONCEPT_BY_KIND = {
    "audio": "audio_track",
    "midi": "midi_track",
    "group": "group",
    "return": "effect_return",
    "master": "master",
    "aux": "aux",
}

# Cross-dialect equivalence for a shared concept when the two sides come from
# different dialects. Concepts absent here fall back to ``close``.
_CROSS_DIALECT_EQUIVALENCE: dict[str, EquivalenceLevel] = {
    "audio_track": "close",
    "midi_track": "close",
    "master": "close",
    "effect_return": "functional",  # return track ↔ FX channel
    "group": "partial",  # grouping semantics differ across DAWs
    "aux": "partial",
}

# Concepts that are structurally native to some dialects and not others.
# ``applicable_dialects`` lists dialects where the concept exists at all.
_CONCEPT_APPLICABILITY: dict[str, set[str]] = {
    # Session-grid scenes: an Ableton paradigm; linear-arranger dialects lack it.
    "scene": {"ableton"},
}


def semantic_concept(track: Track) -> str:
    """The cross-dialect concept for a track, derived from its canonical kind."""
    return _CONCEPT_BY_KIND.get(track.kind, track.kind or "track")


@dataclass
class EntityAlignment:
    """One aligned (or half-aligned) pair of entities across two sessions."""

    concept: str
    left_id: Optional[str] = None
    left_label: Optional[str] = None
    left_kind: Optional[str] = None
    right_id: Optional[str] = None
    right_label: Optional[str] = None
    right_kind: Optional[str] = None
    equivalence: EquivalenceLevel = "unknown"
    confidence: float = 0.0
    basis: list[str] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        return self.left_id is not None and self.right_id is not None


@dataclass
class CompareResult:
    left_dialect: str
    right_dialect: str
    left_name: str
    right_name: str
    alignments: list[EntityAlignment] = field(default_factory=list)
    # concept -> {"left": Applicability, "right": Applicability}
    applicability: dict[str, dict[str, Applicability]] = field(default_factory=dict)

    @property
    def matched(self) -> list[EntityAlignment]:
        return [a for a in self.alignments if a.matched]

    @property
    def left_only(self) -> list[EntityAlignment]:
        return [a for a in self.alignments if a.left_id and not a.right_id]

    @property
    def right_only(self) -> list[EntityAlignment]:
        return [a for a in self.alignments if a.right_id and not a.left_id]

    def summary(self) -> dict:
        return {
            "left_dialect": self.left_dialect,
            "right_dialect": self.right_dialect,
            "matched": len(self.matched),
            "left_only": len(self.left_only),
            "right_only": len(self.right_only),
            "by_equivalence": {
                level: sum(1 for a in self.alignments if a.equivalence == level)
                for level in ("exact", "close", "functional", "partial", "none")
                if any(a.equivalence == level for a in self.alignments)
            },
        }


def _receives_sends(track: Track, session: CanonicalSession) -> bool:
    return any(r.target_track_id == track.id for r in session.routes)


def _sends(track: Track, session: CanonicalSession) -> bool:
    return any(r.source_track_id == track.id for r in session.routes)


def _routing_signature(track: Track, session: CanonicalSession) -> str:
    parts = []
    if _receives_sends(track, session):
        parts.append("receives")
    if _sends(track, session):
        parts.append("sends")
    return "+".join(parts) or "none"


def _pair_equivalence(
    left: Track, right: Track, same_dialect: bool, name_conf: float
) -> EquivalenceLevel:
    concept = semantic_concept(left)
    if same_dialect and name_conf >= 0.99:
        return "exact"
    return _CROSS_DIALECT_EQUIVALENCE.get(concept, "close")


def _align_concept(
    concept: str,
    lefts: list[Track],
    rights: list[Track],
    left_session: CanonicalSession,
    right_session: CanonicalSession,
    same_dialect: bool,
) -> list[EntityAlignment]:
    """Greedy best-name-match alignment within one concept, structure-aware."""
    alignments: list[EntityAlignment] = []
    remaining = list(rights)

    for left in lefts:
        best = None
        best_conf = -1.0
        for right in remaining:
            conf = name_match_confidence(left.name, right.name)
            if conf > best_conf:
                best_conf, best = conf, right

        if best is not None:
            remaining.remove(best)
            basis = [f"shared concept '{concept}'"]
            left_sig = _routing_signature(left, left_session)
            right_sig = _routing_signature(best, right_session)
            if left_sig == right_sig and left_sig != "none":
                basis.append(f"matching routing role ({left_sig})")
            if best_conf >= MATCH_THRESHOLD:
                basis.append(f"name match ({left.name!r} ≈ {best.name!r})")
            else:
                basis.append(f"structural pairing (names differ: {left.name!r} / {best.name!r})")
            equivalence = _pair_equivalence(left, best, same_dialect, best_conf)
            # Confidence blends name similarity with a structural-role bonus.
            confidence = min(1.0, max(best_conf, 0.5) + (0.2 if left_sig == right_sig and left_sig != "none" else 0.0))
            alignments.append(
                EntityAlignment(
                    concept=concept,
                    left_id=left.id, left_label=left.name, left_kind=left.kind,
                    right_id=best.id, right_label=best.name, right_kind=best.kind,
                    equivalence=equivalence, confidence=round(confidence, 2), basis=basis,
                )
            )
        else:
            alignments.append(
                EntityAlignment(
                    concept=concept,
                    left_id=left.id, left_label=left.name, left_kind=left.kind,
                    equivalence="none", confidence=0.0,
                    basis=[f"no '{concept}' counterpart in the other session"],
                )
            )

    for leftover in remaining:
        alignments.append(
            EntityAlignment(
                concept=concept,
                right_id=leftover.id, right_label=leftover.name, right_kind=leftover.kind,
                equivalence="none", confidence=0.0,
                basis=[f"no '{concept}' counterpart in the other session"],
            )
        )
    return alignments


def compare_sessions(
    left: CanonicalSession, right: CanonicalSession
) -> CompareResult:
    """Align entities across two canonical sessions; preserve native difference."""
    same_dialect = left.dialect == right.dialect
    result = CompareResult(
        left_dialect=left.dialect, right_dialect=right.dialect,
        left_name=left.name, right_name=right.name,
    )

    left_by_concept: dict[str, list[Track]] = {}
    right_by_concept: dict[str, list[Track]] = {}
    for track in left.tracks:
        left_by_concept.setdefault(semantic_concept(track), []).append(track)
    for track in right.tracks:
        right_by_concept.setdefault(semantic_concept(track), []).append(track)

    for concept in sorted(set(left_by_concept) | set(right_by_concept)):
        result.alignments.extend(
            _align_concept(
                concept,
                left_by_concept.get(concept, []),
                right_by_concept.get(concept, []),
                left, right, same_dialect,
            )
        )

    # Applicability (§12): concepts native to one dialect but not the other.
    # Scenes are the canonical example — an Ableton session grid concept.
    result.applicability["scene"] = {
        "left": _scene_applicability(left),
        "right": _scene_applicability(right),
    }
    return result


def _scene_applicability(session: CanonicalSession) -> Applicability:
    applicable_dialects = _CONCEPT_APPLICABILITY["scene"]
    if session.dialect in applicable_dialects:
        return "applicable"
    # Linear-arranger dialects (Cubase/REAPER) have no session-grid scenes.
    if session.dialect in ("cubase", "reaper", "logic"):
        return "not_applicable"
    return "unknown"
