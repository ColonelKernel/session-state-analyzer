"""Ableton dialect driver package.

Registration happens in ``session_explorer.drivers`` (the shared registry
module), not here — importing this package has no side effects beyond
defining ``driver``.
"""

from .als_inspector import AlsInspector, inspect_als_bytes
from .demo import (
    DEMO_SESSION_NAME,
    build_demo_session,
    build_demo_session_revision,
    compare_fingerprints,
    compute_session_fingerprint,
)
from .driver import AbletonDriver
from .keywords import classify_device_family, classify_track_role
from .mapper import to_canonical, to_native
from .native_models import ProjectState, validate_project_dict
from .rules import ABLETON_RULES, generate_recommendations

driver = AbletonDriver()

__all__ = [
    "ABLETON_RULES",
    "AbletonDriver",
    "AlsInspector",
    "DEMO_SESSION_NAME",
    "ProjectState",
    "build_demo_session",
    "build_demo_session_revision",
    "classify_device_family",
    "classify_track_role",
    "compare_fingerprints",
    "compute_session_fingerprint",
    "driver",
    "generate_recommendations",
    "inspect_als_bytes",
    "to_canonical",
    "to_native",
    "validate_project_dict",
]
