"""REAPER keyword sets and classification helpers.

The core keyword tables (:data:`session_explorer.core.roles.DEFAULT_KEYWORDS`)
are the union of the Ableton and REAPER prototype taxonomies with REAPER's
orderings preserved (buses first, REAPER's finer-grained Metering family
kept), so the REAPER driver re-exports them unchanged — the verbatim parser
tests pass against the merged tables.

What *is* REAPER-specific is the authoritative knowledge hook: stock Cockos
processors are classified via the guide-derived :mod:`.fx_knowledge` table
before any keyword heuristic runs (e.g. a bare ``"VST: ReaEQ (Cockos)"``
resolves to EQ through the knowledge table, never through substring luck).
"""

from __future__ import annotations

from typing import Optional

from ...core.roles import (
    AMBIENCE_FAMILIES,
    DEFAULT_KEYWORDS,
    DYNAMICS_FAMILIES,
    EQ_FAMILIES,
    KeywordSets,
    classify_processor_family,
    classify_track_role as _core_classify_track_role,
    is_vocal_name,
)
from .fx_knowledge import lookup_stock_fx

__all__ = [
    "AMBIENCE_FAMILIES",
    "DYNAMICS_FAMILIES",
    "EQ_FAMILIES",
    "KeywordSets",
    "REAPER_KEYWORDS",
    "classify_fx_family",
    "classify_track_role",
    "is_ambience_fx",
    "is_vocal_name",
    "knowledge_family_lookup",
]

# REAPER's orderings are already merged into the core default tables, so the
# dialect keyword set is the default set (specialize with
# ``dataclasses.replace`` if REAPER-only vocabulary ever diverges).
REAPER_KEYWORDS: KeywordSets = DEFAULT_KEYWORDS


def knowledge_family_lookup(name: Optional[str]) -> Optional[str]:
    """Authoritative family for stock Cockos FX; ``None`` for third-party names."""

    if not name:
        return None
    stock = lookup_stock_fx(name)
    return stock.family if stock is not None else None


def classify_fx_family(name: Optional[str]) -> str:
    """Return a coarse FX family for a processor name (``"Unknown"`` if no match).

    Stock REAPER processors are identified authoritatively via the guide-derived
    knowledge table; everything else falls back to keyword heuristics.
    """

    return classify_processor_family(
        name, REAPER_KEYWORDS, knowledge_lookup=knowledge_family_lookup
    )


def classify_track_role(name: Optional[str]) -> str:
    """Return a coarse production role for a track name (``"Unknown"`` if no match)."""

    return _core_classify_track_role(name, REAPER_KEYWORDS)


def is_ambience_fx(name: Optional[str]) -> bool:
    """True when a processor name reads as ambience (reverb/delay/echo/...)."""

    return classify_fx_family(name) in AMBIENCE_FAMILIES
