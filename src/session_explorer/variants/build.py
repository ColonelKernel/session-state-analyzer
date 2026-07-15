"""Group snapshots into variant sets and draw their lineage graph.

Three entry points, each a pure function over loaded bundles:

* :func:`build_variant_set` groups bundles into :class:`~.models.VariantSet`s by
  the ``family`` their VARIANT entity declares, and resolves each member's
  lineage ``ordinal``.
* :func:`build_variant_graph` composes a set's snapshots side by side
  (:func:`~session_explorer.graph_layers.build.build_multi`) and then draws the
  cross-snapshot lineage the flattener left as properties only: ``DERIVED_FROM``
  along the derived-from chain, ``ALTERNATIVE_OF`` between same-ordinal
  siblings, and ``SHARES_SOURCE_WITH`` between members that reference the same
  media asset. Each edge carries a ``type`` attribute so the viz layer renders
  it in the shared visual language.
* :func:`variant_diff` reuses the intervention comparator's
  :func:`~session_explorer.interventions.compare.snapshot_delta`, so a
  version-to-version difference reads back with exactly the vocabulary a
  controlled A/B uses (added / removed / changed entities and relationships,
  ``added_sends``, ``parameter_changes``).

Node ids in the composed graph follow ``build_multi``'s scheme: every node is
relabelled ``s{i}:{original_id}`` where ``i`` is the member's position in the
(ordinal-sorted) set, and carries ``snapshot_ordinal=i`` and the original
``entity_id`` as node attributes. The lineage edges are added between the
relabelled VARIANT / MEDIA_ASSET nodes accordingly.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Optional

import networkx as nx

from canonical_snapshot import CanonicalDAWSnapshot, Entity

from session_explorer.graph_layers.build import build_multi
from session_explorer.interventions.compare import snapshot_delta
from session_explorer.interventions.models import StateDelta
from session_explorer.loaders.bundle import SnapshotBundle

from .models import VariantMember, VariantSet


# ---------------------------------------------------------------------------
# Reading the VARIANT entity a snapshot self-declares
# ---------------------------------------------------------------------------


def _variant_entity(snapshot: CanonicalDAWSnapshot) -> Optional[Entity]:
    """The single VARIANT entity a snapshot carries, or ``None``."""
    for entity in snapshot.entities:
        if entity.entity_type == "VARIANT":
            return entity
    return None


def _family_key(family: Optional[str], snapshot_id: str) -> str:
    """A grouping key for a member.

    A variant with no declared family cannot join a set; keep it in its own
    singleton keyed by snapshot id rather than silently merging every
    family-less variant into one bogus group.
    """
    return family if family else f"__ungrouped__:{snapshot_id}"


def _coerce_ordinal(value: Any) -> Optional[int]:
    """An explicit ordinal property coerced to ``int``, or ``None``."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _chain_depth(snapshot_id: str, by_sid: dict[str, dict]) -> int:
    """Number of ``derived_from`` hops from a member back to a root.

    A member whose ``derived_from`` is absent (or points outside the set, or at
    itself) is a root at depth 0; each resolvable hop adds one. The walk is
    guarded against a lineage cycle so a malformed set degrades to a finite
    ordinal instead of looping.
    """
    depth = 0
    seen: set[str] = set()
    current = snapshot_id
    while current in by_sid and current not in seen:
        seen.add(current)
        df = by_sid[current]["derived_from"]
        if df is None or df not in by_sid or df == current:
            break
        depth += 1
        current = df
    return depth


def _resolve_ordinal(raw: dict, by_sid: dict[str, dict]) -> int:
    """An explicit ordinal when present, else the derived-from chain depth."""
    explicit = raw["explicit_ordinal"]
    if explicit is not None:
        return explicit
    return _chain_depth(raw["snapshot_id"], by_sid)


def build_variant_set(bundles: Iterable[SnapshotBundle]) -> list[VariantSet]:
    """Group loaded bundles into variant sets, one per declared family.

    A bundle with no VARIANT entity is skipped (it does not belong to any
    set). Members are grouped by the VARIANT entity's ``family`` property, and
    each member's ``ordinal`` is resolved — an explicit ordinal property when
    the contract carries one, else the depth of its ``derived_from`` chain.
    Returned sets are sorted by family, their members sorted by ordinal.
    """
    raw_by_family: dict[str, list[dict]] = defaultdict(list)
    for bundle in bundles:
        variant = _variant_entity(bundle.snapshot)
        if variant is None:
            continue
        props = variant.properties
        family = props.get("family")
        snapshot_id = bundle.snapshot.snapshot_id
        raw_by_family[_family_key(family, snapshot_id)].append(
            {
                "snapshot_id": snapshot_id,
                "label": props.get("label") or variant.name,
                "family": family,
                "derived_from": props.get("derived_from_snapshot_id"),
                "explicit_ordinal": _coerce_ordinal(props.get("ordinal")),
                "bundle": bundle,
            }
        )

    sets: list[VariantSet] = []
    for key, raws in raw_by_family.items():
        by_sid = {r["snapshot_id"]: r for r in raws}
        members = [
            VariantMember(
                snapshot_id=r["snapshot_id"],
                label=r["label"],
                ordinal=_resolve_ordinal(r, by_sid),
                family=r["family"],
                derived_from_snapshot_id=r["derived_from"],
                bundle=r["bundle"],
            )
            for r in raws
        ]
        family_name = raws[0]["family"] or key
        sets.append(VariantSet(family=family_name, members=members))

    sets.sort(key=lambda s: s.family)
    return sets


# ---------------------------------------------------------------------------
# Lineage graph
# ---------------------------------------------------------------------------


def build_variant_graph(variant_set: VariantSet, layer: str = "all") -> nx.MultiDiGraph:
    """Compose a set's snapshots and draw the cross-snapshot lineage.

    The members' snapshots are composed side by side with
    :func:`~session_explorer.graph_layers.build.build_multi` (per-snapshot
    ``s{i}:`` node prefixes, no invented cross-edges), then three families of
    lineage edge are added on top — ``DERIVED_FROM`` down the derived-from
    chain, ``ALTERNATIVE_OF`` between same-ordinal siblings, and
    ``SHARES_SOURCE_WITH`` between members that reference the same media path.
    Every added edge carries ``type`` so the viz layer colours it.
    """
    members = variant_set.members  # sorted by (ordinal, snapshot_id)
    snapshots = [m.bundle.snapshot for m in members]
    graph = build_multi(snapshots, layer=layer)

    # Recover each member's VARIANT node and its media-asset nodes from the
    # build_multi relabelling scheme (position i ⇒ prefix ``s{i}:``).
    variant_node: list[Optional[str]] = []
    asset_nodes_by_path: list[dict[str, str]] = []
    for i, snapshot in enumerate(snapshots):
        v_entity = _variant_entity(snapshot)
        node = f"s{i}:{v_entity.id}" if v_entity is not None else None
        variant_node.append(node if node is not None and graph.has_node(node) else None)

        paths: dict[str, str] = {}
        for entity in snapshot.entities:
            if entity.entity_type != "MEDIA_ASSET":
                continue
            path = entity.properties.get("path") or entity.name or entity.id
            node_id = f"s{i}:{entity.id}"
            if graph.has_node(node_id):
                paths[str(path)] = node_id
        asset_nodes_by_path.append(paths)

    _add_derived_from(graph, members, variant_node)
    _add_alternative_of(graph, members, variant_node)
    _add_shares_source_with(graph, asset_nodes_by_path)
    return graph


def _add_derived_from(
    graph: nx.MultiDiGraph,
    members: list[VariantMember],
    variant_node: list[Optional[str]],
) -> None:
    """DERIVED_FROM from a member's parent to the member.

    Ground truth is ``derived_from_snapshot_id``: when it names a sibling's
    snapshot, an edge is drawn parent → child. Only when *no* member in the set
    resolves a parent (a lineage with no declared derivation at all) does the
    builder fall back to connecting consecutive ordinals.
    """
    sid_to_index = {m.snapshot_id: i for i, m in enumerate(members)}
    linked = False
    for i, member in enumerate(members):
        df = member.derived_from_snapshot_id
        if df is None or df not in sid_to_index:
            continue
        parent = sid_to_index[df]
        src, dst = variant_node[parent], variant_node[i]
        if src is not None and dst is not None and src != dst:
            graph.add_edge(src, dst, type="DERIVED_FROM")
            linked = True
    if not linked:
        _add_consecutive_ordinal_chain(graph, members, variant_node)


def _add_consecutive_ordinal_chain(
    graph: nx.MultiDiGraph,
    members: list[VariantMember],
    variant_node: list[Optional[str]],
) -> None:
    """Fallback lineage: link each member to the next when its ordinal rises."""
    for i in range(len(members) - 1):
        if members[i + 1].ordinal > members[i].ordinal:
            src, dst = variant_node[i], variant_node[i + 1]
            if src is not None and dst is not None:
                graph.add_edge(src, dst, type="DERIVED_FROM")


def _add_alternative_of(
    graph: nx.MultiDiGraph,
    members: list[VariantMember],
    variant_node: list[Optional[str]],
) -> None:
    """ALTERNATIVE_OF between every pair of members sharing an ordinal."""
    by_ordinal: dict[int, list[int]] = defaultdict(list)
    for i, member in enumerate(members):
        by_ordinal[member.ordinal].append(i)
    for indices in by_ordinal.values():
        if len(indices) < 2:
            continue
        for a in range(len(indices)):
            for b in range(a + 1, len(indices)):
                src, dst = variant_node[indices[a]], variant_node[indices[b]]
                if src is not None and dst is not None:
                    graph.add_edge(src, dst, type="ALTERNATIVE_OF")


def _add_shares_source_with(
    graph: nx.MultiDiGraph, asset_nodes_by_path: list[dict[str, str]]
) -> None:
    """SHARES_SOURCE_WITH between asset nodes that resolve to the same path."""
    by_path: dict[str, list[str]] = defaultdict(list)
    for member_assets in asset_nodes_by_path:
        for path, node_id in member_assets.items():
            by_path[path].append(node_id)
    for node_ids in by_path.values():
        unique = list(dict.fromkeys(node_ids))  # dedupe, preserve order
        if len(unique) < 2:
            continue
        for a in range(len(unique)):
            for b in range(a + 1, len(unique)):
                graph.add_edge(unique[a], unique[b], type="SHARES_SOURCE_WITH")


# ---------------------------------------------------------------------------
# Version-to-version difference
# ---------------------------------------------------------------------------


def variant_diff(a: SnapshotBundle, b: SnapshotBundle) -> StateDelta:
    """The structural difference between two variants.

    A thin reuse of the intervention comparator's
    :func:`~session_explorer.interventions.compare.snapshot_delta`: comparing
    two versions of a song is the same structural diff as comparing the two
    sides of a controlled intervention, so it reads back with the same
    vocabulary (added / removed / changed, ``added_sends``,
    ``parameter_changes``).
    """
    return snapshot_delta(a.snapshot, b.snapshot)
