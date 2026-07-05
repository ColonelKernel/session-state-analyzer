"""Explainable cross-DAW semantic alignment (P4).

``align(a, b)`` proposes strip-level matches between two snapshots using only
auditable signals (registry concepts, name tokens, entity shape, local
topology, media hashes) and returns results whose every claim carries reasons.
``confirm(result)`` is the sole path to CONFIRMED — a user annotation.
"""

from .engine import align, build_strips, confirm
from .models import ALIGNMENT_STATUSES, AlignmentResult, AlignmentStatus

__all__ = [
    "ALIGNMENT_STATUSES",
    "AlignmentResult",
    "AlignmentStatus",
    "align",
    "build_strips",
    "confirm",
]
