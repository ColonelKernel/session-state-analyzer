"""Group decomposition: proving a native "group" is several canonical concepts.

A DAW "group" (a folder, a submix bus, a VCA) fuses concepts the canonical
model deliberately keeps apart:

- **containment** — ``CONTAINS``: which lanes live inside the group;
- **summing** — ``SUMS_TO``: whose signal is mixed into the group channel;
- **control** — ``CONTROLS`` (VCA / edit group): what the group scales in level
  without carrying audio;
- **incoming routing** — ``CHANNEL_SENDS_TO`` / ``CHANNEL_ROUTES_TO`` into the
  group channel from outside its membership.

:func:`decompose_group` reads those four facets off a snapshot for one group
entity, so the workbench can show a single native noun fanning out into the
distinct edges that actually constitute it — and :meth:`GroupDecomposition.
is_multi_concept` proves the point quantitatively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from canonical_snapshot import CanonicalDAWSnapshot

# Semantic roles that mark an entity as some kind of native "group".
_GROUP_ROLES = frozenset({"submix", "folder_parent", "vca"})


@dataclass
class GroupDecomposition:
    """The distinct canonical concepts one native "group" entity fuses.

    Each list holds the *other* endpoints of the group's edges of that facet:
    contained members, summed channels, controlled targets, and the sources
    routing in. A native "group" that is really only a folder decomposes to
    ``contains`` alone; a summing bus adds ``sums``; a VCA is ``controls``.
    """

    group_id: str
    contains: List[str] = field(default_factory=list)
    sums: List[str] = field(default_factory=list)
    controls: List[str] = field(default_factory=list)
    routes_in: List[str] = field(default_factory=list)

    def concept_count(self) -> int:
        """How many of the four group facets are actually present."""
        return sum(
            1
            for facet in (self.contains, self.sums, self.controls, self.routes_in)
            if facet
        )

    def is_multi_concept(self) -> bool:
        """Whether this "group" is genuinely more than one canonical concept."""
        return self.concept_count() >= 2


def group_channel_id(
    snapshot: CanonicalDAWSnapshot, group_entity_id: str
) -> Optional[str]:
    """The CHANNEL entity that carries a group's summed signal, or ``None``.

    A group TRACK joins its channel via ``TRACK_USES_CHANNEL``; a channel-like
    group (a return/master kind) *is* its own channel, and a channel id passed
    in resolves to itself. Returns ``None`` when no channel can be resolved.
    """
    entity = snapshot.entity_by_id(group_entity_id)
    if entity is None:
        return None
    if entity.entity_type == "CHANNEL":
        return entity.id
    for rel in snapshot.relationships_of_type("TRACK_USES_CHANNEL"):
        if rel.source == group_entity_id:
            return rel.target
    return None


def find_group_entities(snapshot: CanonicalDAWSnapshot) -> List[str]:
    """Every entity that behaves like a native group, by role or by edge.

    The order-stable, de-duplicated union of: entities whose ``semantic_roles``
    intersect ``{submix, folder_parent, vca}``, the *targets* of ``SUMS_TO``
    (the group channels being summed into), and the *sources* of VCA/edit-group
    ``CONTROLS`` edges (the controllers).
    """
    found: List[str] = []
    seen: set[str] = set()

    def _push(entity_id: Optional[str]) -> None:
        if entity_id and entity_id not in seen:
            seen.add(entity_id)
            found.append(entity_id)

    for entity in snapshot.entities:
        if _GROUP_ROLES.intersection(entity.semantic_roles):
            _push(entity.id)
    for rel in snapshot.relationships_of_type("SUMS_TO"):
        _push(rel.target)
    for rel in snapshot.relationships_of_type("CONTROLS"):
        if rel.properties.get("kind") == "vca_or_edit_group":
            _push(rel.source)
    return found


def decompose_group(
    snapshot: CanonicalDAWSnapshot, group_entity_id: str
) -> GroupDecomposition:
    """Split one native "group" entity into its four canonical facets.

    ``group_entity_id`` may name either the group's TRACK (organizational lane)
    or its CHANNEL (signal path); both sides are resolved so the decomposition
    is the same whichever id the caller holds. ``routes_in`` deliberately
    excludes the group-sum ``CHANNEL_ROUTES_TO`` edges (they duplicate
    ``SUMS_TO``) so summing and genuine incoming routing stay distinct.
    """
    channel_id = group_channel_id(snapshot, group_entity_id)

    # The set of ids that are "this group", on either side of the TRACK≠CHANNEL
    # split, so an edge anchored on either resolves.
    group_ids: set[str] = {group_entity_id}
    if channel_id is not None:
        group_ids.add(channel_id)
    for rel in snapshot.relationships_of_type("TRACK_USES_CHANNEL"):
        if rel.target == channel_id:
            group_ids.add(rel.source)
        if rel.source == group_entity_id:
            group_ids.add(rel.target)

    contains = [
        rel.target
        for rel in snapshot.relationships_of_type("CONTAINS")
        if rel.source in group_ids and rel.properties.get("kind") == "group_member"
    ]
    sums = [
        rel.source
        for rel in snapshot.relationships_of_type("SUMS_TO")
        if rel.target in group_ids
    ]
    controls = [
        rel.target
        for rel in snapshot.relationships_of_type("CONTROLS")
        if rel.source in group_ids
        and rel.properties.get("kind") == "vca_or_edit_group"
    ]
    routes_in = [
        rel.source
        for rel in snapshot.relationships_of_type("CHANNEL_SENDS_TO")
        if rel.target in group_ids
    ]
    routes_in += [
        rel.source
        for rel in snapshot.relationships_of_type("CHANNEL_ROUTES_TO")
        if rel.target in group_ids and rel.properties.get("via") != "group_sum"
    ]

    return GroupDecomposition(
        group_id=group_entity_id,
        contains=contains,
        sums=sums,
        controls=controls,
        routes_in=routes_in,
    )
