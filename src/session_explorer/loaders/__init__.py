"""Snapshot-bundle loading: the analyzer's only intake path.

The analyzer contains no DAW parsing or acquisition code. Everything it knows
arrives as an adapter-exported bundle (see ``bundle.load_bundle``); everything
it says about a DAW's presentation vocabulary comes from the data-only
``registry``.
"""

from .bundle import SnapshotBundle, load_bundle, load_snapshot
from .registry import DawPresentation, get_presentation, known_daws

__all__ = [
    "SnapshotBundle",
    "load_bundle",
    "load_snapshot",
    "DawPresentation",
    "get_presentation",
    "known_daws",
]
