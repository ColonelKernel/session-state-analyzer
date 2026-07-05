"""Provenance: where a value came from and how much to trust it.

Generalizes the Logic prototype's observability bookkeeping to every dialect.
Each canonical entity carries a :class:`Provenance`; individual fields whose
origin differs from the entity's (a heuristic ``role`` on an otherwise parsed
track, say) get an entry in the entity's ``field_provenance``.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Observability = Literal["observed", "inferred", "annotation", "hidden", "derived"]

OBSERVABILITY_VALUES: tuple[str, ...] = (
    "observed",
    "inferred",
    "annotation",
    "hidden",
    "derived",
)


class Provenance(BaseModel):
    """How a value entered the canonical session.

    ``source_artifact`` names the evidence artifact type from the dialect's
    observation matrix (``"rpp_file"``, ``"extension_json"``, ``"exported_audio"``,
    ...). ``confidence`` is 1.0 for directly parsed values; heuristics report
    their own calibrated confidence and a human-readable ``explanation``.
    """

    observability: Observability = "observed"
    source_artifact: Optional[str] = None
    confidence: float = 1.0
    explanation: Optional[str] = None


OBSERVED = Provenance(observability="observed")


def inferred(
    explanation: Optional[str] = None,
    confidence: float = 0.5,
    source_artifact: Optional[str] = None,
) -> Provenance:
    """Convenience constructor for heuristic-derived values."""
    return Provenance(
        observability="inferred",
        confidence=confidence,
        explanation=explanation,
        source_artifact=source_artifact,
    )


def annotation(
    explanation: Optional[str] = None,
    confidence: float = 0.5,
    source_artifact: Optional[str] = None,
) -> Provenance:
    """Convenience constructor for user-asserted values (never DAW facts)."""
    return Provenance(
        observability="annotation",
        confidence=confidence,
        explanation=explanation,
        source_artifact=source_artifact,
    )
