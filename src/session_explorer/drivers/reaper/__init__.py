"""The REAPER dialect driver package.

Public API re-exports. The driver instance is exported as ``driver`` but is
deliberately NOT self-registered here — the shared driver registry
(:mod:`session_explorer.drivers`) owns registration.
"""

from .colors import decode_color, swell_platform
from .driver import ReaperDriver, ReaperKnowledge
from .fx_knowledge import (
    FAMILY_STOCK_CANDIDATES,
    STOCK_FX,
    WORKFLOWS,
    Citation,
    StockFx,
    Workflow,
    lookup_stock_fx,
    workflow,
)
from .keywords import (
    REAPER_KEYWORDS,
    classify_fx_family,
    classify_track_role,
    is_ambience_fx,
    is_vocal_name,
)
from .mapper import to_canonical, to_native
from .native_models import (
    FxState,
    MediaItemState,
    ProjectState,
    RouteState,
    TrackState,
)
from .rpp_parser import parse_rpp
from .rules import REAPER_RULES

driver = ReaperDriver()

__all__ = [
    "Citation",
    "FAMILY_STOCK_CANDIDATES",
    "FxState",
    "MediaItemState",
    "ProjectState",
    "REAPER_KEYWORDS",
    "REAPER_RULES",
    "ReaperDriver",
    "ReaperKnowledge",
    "RouteState",
    "STOCK_FX",
    "StockFx",
    "TrackState",
    "WORKFLOWS",
    "Workflow",
    "classify_fx_family",
    "classify_track_role",
    "decode_color",
    "driver",
    "is_ambience_fx",
    "is_vocal_name",
    "lookup_stock_fx",
    "parse_rpp",
    "swell_platform",
    "to_canonical",
    "to_native",
    "workflow",
]
