"""Dialect drivers and their registration.

Importing this package registers every wired dialect driver with the core
registry (:mod:`session_explorer.core.driver`), so the app and CLI can
auto-detect and enumerate them. This is the single registration point —
driver modules define their classes; registration happens here.

Wired dialects:

* **ableton** — Ableton-style session JSON + Extensions SDK export JSON; the
  high-observability reference adapter.
* **cubase** — Cubase-flavoured session JSON + Track Archive surface
  inspector; the hybrid-observability adapter.
* **reaper** — real ``.rpp`` project-file parsing; the project-file adapter.

Logic is not yet wired (native models and evidence inspectors exist under
``drivers/logic`` but there is no load path / driver class yet).
"""

from __future__ import annotations

from ..core.driver import all_drivers, get, register
from .ableton.driver import AbletonDriver
from .cubase.driver import CubaseDriver
from .reaper.driver import ReaperDriver

register(AbletonDriver())
register(CubaseDriver())
register(ReaperDriver())

__all__ = [
    "AbletonDriver",
    "CubaseDriver",
    "ReaperDriver",
    "all_drivers",
    "get",
    "register",
]
