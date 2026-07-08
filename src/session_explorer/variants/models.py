"""The variant-set data model — a family of related session snapshots.

A *variant set* is a group of :class:`~session_explorer.loaders.bundle.
SnapshotBundle`s a producer treats as versions of one song: the mix printed on
Monday and its Tuesday revision, an "album" edit vs a "single" edit, a
``v5``/``v6``/``v7`` lineage. Each snapshot self-declares its place through the
VARIANT entity the contract emits (``label`` / ``family`` /
``derived_from_snapshot_id`` as *properties*). The analyzer reads those back
and materialises the cross-snapshot lineage the flattener deliberately could
not: a single snapshot has no way to know its siblings, so the edges live
here, where the whole family coexists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from session_explorer.loaders.bundle import SnapshotBundle


@dataclass
class VariantMember:
    """One snapshot's membership in a variant set.

    ``ordinal`` is the member's position in the lineage: an explicit ordinal
    property on the VARIANT entity when the contract ever carries one, else the
    depth of the ``derived_from`` chain (a root is 0, its child 1, ...). Two
    members with the same ordinal are *siblings* (alternatives), not a
    sequence. ``bundle`` is the full loaded bundle, so a caller can reach the
    snapshot, its validation report, and the native payload without re-loading.
    """

    snapshot_id: str
    label: Optional[str]
    ordinal: int
    family: Optional[str]
    derived_from_snapshot_id: Optional[str]
    bundle: SnapshotBundle


@dataclass
class VariantSet:
    """A family of related snapshots, its members ordered by ``ordinal``.

    ``members`` is kept sorted by ``(ordinal, snapshot_id)`` — the earliest
    version first, same-ordinal siblings in a stable order. The sort is
    enforced on construction, so no caller can hand back an out-of-order set.
    """

    family: str
    members: list[VariantMember] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.members.sort(key=lambda m: (m.ordinal, m.snapshot_id))

    def __len__(self) -> int:
        return len(self.members)

    def labels(self) -> list[str]:
        """The members' labels in order (falling back to the snapshot id)."""
        return [m.label or m.snapshot_id for m in self.members]
