"""Unified DAW Session State Explorer.

One product over four DAW dialects (Ableton Live, Cubase, REAPER, Logic Pro):
interpretable, partially observable session-state graphs with explainable,
caveated recommendations.

The canonical schema is unified but lossless: every driver keeps its full
native model attached to the canonical session, so nothing a DAW exposes is
ever dropped, and every session can be viewed in "unified" or "native" mode.
"""

__version__ = "1.0.0"

SCHEMA_VERSION = "1.0.0"
