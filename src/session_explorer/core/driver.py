"""The dialect driver interface and registry.

A :class:`SessionDriver` is the single integration point for a DAW dialect:
it sniffs inputs, loads them into a :class:`CanonicalSession` (with the full
native model attached as the ``native`` payload), reconstructs the native
model for the native view, and contributes its rule pack, knowledge
catalogue, keyword sets, surface inspectors, and Streamlit panels.

Drivers register themselves at import time (``session_explorer.drivers``);
the registry powers auto-detection in the app and CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from pydantic import BaseModel

from .models import CanonicalSession, Recommendation


@dataclass
class UploadedFile:
    """One uploaded input: a name and its raw bytes."""

    name: str
    data: bytes


@dataclass
class DriverInputs:
    """Everything a driver may receive: files, an on-disk folder, options."""

    files: list[UploadedFile] = field(default_factory=list)
    folder: Optional[Path] = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class Rule:
    """One recommendation rule.

    ``requires`` names canonical state fields (see
    ``observability.SESSION_STATE_FIELDS``); the engine skips the rule — with
    an info note instead of silence — when the session's dialect hides one of
    them, turning partial observability into visible behavior.
    """

    rule_id: str
    fn: Callable[[CanonicalSession], list[Recommendation]]
    requires: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class InspectionReport:
    """Surface-inspection output (tag/class counting, never claimed as parsing)."""

    inspector: str
    file_name: str
    summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class SurfaceInspector:
    """A conservative file inspector (e.g. .als gzip/XML tag counter)."""

    name: str = "inspector"
    extensions: tuple[str, ...] = ()

    def matches(self, filename: str) -> bool:
        return filename.lower().endswith(self.extensions)

    def inspect(self, filename: str, data: bytes) -> InspectionReport:  # pragma: no cover
        raise NotImplementedError


class SessionDriver:
    """Base class for dialect drivers.

    Subclasses must set ``dialect``/``display_name`` and implement ``sniff``,
    ``load``, ``demo``, and ``to_native``. Everything else has a safe default
    so a minimal driver stays minimal.
    """

    dialect: str = ""
    display_name: str = ""
    #: file extensions this driver's primary input uses (hints for pickers)
    extensions: tuple[str, ...] = ()

    # -- required -----------------------------------------------------------

    def sniff(self, filename: str, head: bytes) -> float:
        """Confidence 0..1 that this driver can load the given file."""
        raise NotImplementedError

    def load(self, inputs: DriverInputs) -> CanonicalSession:
        raise NotImplementedError

    def demo(self) -> CanonicalSession:
        raise NotImplementedError

    def to_native(self, session: CanonicalSession) -> BaseModel:
        """Reconstruct the verbatim native model from ``session.native``."""
        raise NotImplementedError

    # -- optional hooks -------------------------------------------------------

    def demo_revision(self) -> Optional[CanonicalSession]:
        """A second demo revision for diff demos, when the dialect has one."""
        return None

    def rules(self) -> list[Rule]:
        return []

    def knowledge(self):
        """A knowledge catalogue (stock FX / plugin lookup) or ``None``."""
        return None

    def keywords(self) -> dict[str, Any]:
        """Dialect keyword-set overrides for role/family classification."""
        return {}

    def inspectors(self) -> list[SurfaceInspector]:
        return []

    def observation_matrix(self) -> dict[str, dict[str, list[str]]]:
        from . import observability

        return observability.OBSERVATION_MODEL.get(self.dialect, {})

    def ui_panels(self) -> list[Any]:
        """Native-view Streamlit panels; empty for headless-only drivers."""
        return []


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: dict[str, SessionDriver] = {}


def register(driver: SessionDriver) -> SessionDriver:
    """Register a driver instance (idempotent per dialect; last wins)."""
    if not driver.dialect:
        raise ValueError("driver.dialect must be a non-empty string")
    _registry[driver.dialect] = driver
    return driver


def get(dialect: str) -> SessionDriver:
    try:
        return _registry[dialect]
    except KeyError:
        raise KeyError(
            f"No driver registered for dialect {dialect!r}. "
            f"Available: {sorted(_registry)}"
        ) from None


def all_drivers() -> list[SessionDriver]:
    return [_registry[k] for k in sorted(_registry)]


def detect(filename: str, head: bytes) -> list[tuple[SessionDriver, float]]:
    """Rank registered drivers by sniff confidence for a file (best first).

    Drivers whose ``sniff`` raises are scored 0 rather than aborting
    detection — auto-detect must never crash on unfamiliar input.
    """
    scored = []
    for drv in all_drivers():
        try:
            score = float(drv.sniff(filename, head))
        except Exception:
            score = 0.0
        if score > 0:
            scored.append((drv, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def clear_registry() -> None:
    """Testing hook: forget all registered drivers."""
    _registry.clear()
