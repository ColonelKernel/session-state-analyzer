"""Small, dependency-free helpers shared across the product.

Deliberately avoids heavy imports so it can be used from tests and parsers
without pulling in audio or visualization libraries. DAW-specific value
conversions (e.g. REAPER's packed colour ints) live in the owning driver.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Optional


def linear_to_db(value: Optional[float]) -> Optional[float]:
    """Convert a linear gain to dB.

    Returns ``None`` for non-positive or missing values (``-inf`` is not useful
    in a table). Unity gain (1.0) maps to 0 dB.
    """
    if value is None or value <= 0:
        return None
    return round(20.0 * math.log10(value), 2)


def safe_float(token: Optional[str]) -> Optional[float]:
    """Parse a float, returning ``None`` instead of raising on bad input."""
    if token is None:
        return None
    try:
        return float(token)
    except (TypeError, ValueError):
        return None


def safe_int(token: Optional[str]) -> Optional[int]:
    """Parse an int (tolerating float-formatted text), returning ``None`` on failure."""
    if token is None:
        return None
    try:
        return int(token)
    except (TypeError, ValueError):
        parsed = safe_float(token)
        return int(parsed) if parsed is not None else None


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: Optional[str], fallback: str = "item") -> str:
    """Lowercase, hyphenated slug suitable for ids and filenames."""
    if not text:
        return fallback
    slug = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return slug or fallback


def to_pretty_json(payload: Any) -> str:
    """Serialize to human-readable JSON, tolerating numpy scalars."""

    def _default(obj: Any) -> Any:
        if hasattr(obj, "item"):
            return obj.item()
        if hasattr(obj, "tolist"):
            return obj.tolist()
        return str(obj)

    return json.dumps(payload, indent=2, default=_default)
