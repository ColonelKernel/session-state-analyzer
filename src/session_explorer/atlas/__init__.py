"""The Observability Atlas (P5): measured per-domain observability across DAWs.

Honest profiles, not a single score. Each of the ten :data:`ATLAS_DOMAINS` is
read across every loaded DAW bundle as two independent facts — what a snapshot
*measured* and what an adapter *declares* it can read — and the two are kept
visibly apart. See :mod:`session_explorer.atlas.domains` for the row taxonomy
and :mod:`session_explorer.atlas.coverage` for the measurement.
"""

from __future__ import annotations

from .coverage import (
    Atlas,
    AtlasCell,
    DeclaredCoverage,
    DeclaredFieldCapability,
    MeasuredCoverage,
    UNKNOWN_CATEGORIES,
    build_atlas,
    declared_domain,
    measure_domain,
    unknown_state_map,
)
from .domains import (
    ATLAS_DOMAINS,
    ATLAS_DOMAINS_BY_NAME,
    AtlasDomain,
    atlas_domains,
    get_domain,
)

__all__ = [
    "ATLAS_DOMAINS",
    "ATLAS_DOMAINS_BY_NAME",
    "AtlasDomain",
    "atlas_domains",
    "get_domain",
    "Atlas",
    "AtlasCell",
    "MeasuredCoverage",
    "DeclaredCoverage",
    "DeclaredFieldCapability",
    "UNKNOWN_CATEGORIES",
    "build_atlas",
    "declared_domain",
    "measure_domain",
    "unknown_state_map",
]
