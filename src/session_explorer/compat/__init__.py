"""Compatibility Ladder (Phase 3): honest per-bundle capability profiles.

Master-prompt §23's seven-rung ladder (L0 loadable -> L6 controlled
intervention), measured against a bundle's *actual data*. The public object is
a :class:`LadderProfile` — a bundle's **reached set** of rungs, never a single
rank. See :mod:`session_explorer.compat.ladder` for the rung definitions and
the "profiles, not rankings" rationale.
"""

from __future__ import annotations

from .ladder import (
    DEFAULT_ADAPTERS_ROOT,
    DEFAULT_DOC_PATH,
    DEFAULT_EXPERIMENTS_ROOT,
    LEVEL_META,
    LadderContext,
    LadderLevel,
    LadderProfile,
    LevelAssessment,
    assess_bundle,
    assess_fixtures,
    assess_l0,
    assess_l1,
    assess_l2,
    assess_l3,
    assess_l4,
    assess_l5,
    assess_l6,
    render_ladder_document,
    render_ladder_markdown,
)

__all__ = [
    "LadderLevel",
    "LEVEL_META",
    "LevelAssessment",
    "LadderProfile",
    "LadderContext",
    "assess_bundle",
    "assess_fixtures",
    "assess_l0",
    "assess_l1",
    "assess_l2",
    "assess_l3",
    "assess_l4",
    "assess_l5",
    "assess_l6",
    "render_ladder_markdown",
    "render_ladder_document",
    "DEFAULT_ADAPTERS_ROOT",
    "DEFAULT_EXPERIMENTS_ROOT",
    "DEFAULT_DOC_PATH",
]
