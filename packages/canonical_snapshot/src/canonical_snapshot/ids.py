"""Readable sequential id generation shared by all drivers.

Canonical entities are additionally namespaced by dialect (``reaper:track-1``)
so sessions from different DAWs can coexist in one graph or diff without id
collisions; native ids are preserved untouched inside the ``native`` payload.
"""

from __future__ import annotations

import itertools

_id_counters: dict[str, itertools.count] = {}


def make_id(prefix: str) -> str:
    """Generate a readable sequential id like ``track-3``."""
    counter = _id_counters.setdefault(prefix, itertools.count(1))
    return f"{prefix}-{next(counter)}"


def reset_id_counters() -> None:
    """Reset id counters (useful for deterministic tests and demo builds)."""
    _id_counters.clear()


def namespaced(dialect: str, raw_id: str) -> str:
    """Namespace a native id into canonical id space (``reaper:track-1``).

    Idempotent: an id already carrying this dialect prefix is returned as-is.
    """
    prefix = f"{dialect}:"
    if raw_id.startswith(prefix):
        return raw_id
    return f"{prefix}{raw_id}"
