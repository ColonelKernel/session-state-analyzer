"""Session variants (P8): families of related snapshots and their lineage.

A snapshot self-declares its place in a variant family through the VARIANT
entity the contract emits (``label`` / ``family`` /
``derived_from_snapshot_id`` as properties). This package reads those back:
:func:`build_variant_set` groups bundles into :class:`VariantSet`s and resolves
each member's lineage ordinal; :func:`build_variant_graph` composes a set into
one graph and draws the cross-snapshot ``DERIVED_FROM`` / ``ALTERNATIVE_OF`` /
``SHARES_SOURCE_WITH`` edges a single snapshot could not; :func:`variant_diff`
reuses the intervention comparator to read a version-to-version change back in
the same vocabulary as a controlled A/B.
"""

from __future__ import annotations

from .build import build_variant_graph, build_variant_set, variant_diff
from .models import VariantMember, VariantSet

__all__ = [
    "VariantMember",
    "VariantSet",
    "build_variant_set",
    "build_variant_graph",
    "variant_diff",
]
