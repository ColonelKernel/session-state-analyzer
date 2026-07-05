"""Alignment result models.

An :class:`AlignmentResult` is one claim that an entity in snapshot A and an
entity in snapshot B implement the same thing — with the *reasons* that make
the claim, because an alignment nobody can audit is not analysis.

Statuses:

- ``CONFIRMED`` — a user confirmed the match (only :func:`~.engine.confirm`
  produces this; the engine itself never claims certainty).
- ``PROBABLE`` — strong multi-signal agreement.
- ``POSSIBLE`` — some agreement, worth a human look.
- ``UNMATCHED`` — no candidate cleared the floor.
- ``CONFLICTING`` — two candidates are too close to call; the engine refuses
  to pick rather than picking silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

AlignmentStatus = Literal[
    "CONFIRMED", "PROBABLE", "POSSIBLE", "UNMATCHED", "CONFLICTING"
]

ALIGNMENT_STATUSES: tuple[str, ...] = (
    "CONFIRMED", "PROBABLE", "POSSIBLE", "UNMATCHED", "CONFLICTING"
)


@dataclass
class AlignmentResult:
    """One source→target alignment claim with its evidence.

    ``target_entity`` is ``None`` for UNMATCHED (and names *both* rivals in
    ``reasons`` for CONFLICTING, where it carries the narrowly-leading one).
    ``confidence`` is the composite signal score in [0, 1]; ``None`` only when
    no candidate existed at all. ``concept_id`` is the registry concept both
    sides implement, when the concept signal fired.

    The ``source_name`` / ``target_name`` / ``source_daw`` / ``target_daw``
    fields are display conveniences for the workbench — the ids alone are the
    contract.
    """

    source_entity: str
    target_entity: Optional[str]
    status: AlignmentStatus
    confidence: Optional[float]
    reasons: list[str] = field(default_factory=list)
    concept_id: Optional[str] = None
    source_daw: Optional[str] = None
    target_daw: Optional[str] = None
    source_name: Optional[str] = None
    target_name: Optional[str] = None
