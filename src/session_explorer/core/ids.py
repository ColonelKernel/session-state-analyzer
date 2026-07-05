"""Re-export shim: id helpers moved to ``canonical_snapshot.ids``.

Sequential-id state is shared with the contract package (there is exactly one
counter table), so mixed imports of ``session_explorer.core.ids`` and
``canonical_snapshot.ids`` see the same sequence.
"""

from __future__ import annotations

from canonical_snapshot.ids import make_id, namespaced, reset_id_counters

__all__ = ["make_id", "reset_id_counters", "namespaced"]
