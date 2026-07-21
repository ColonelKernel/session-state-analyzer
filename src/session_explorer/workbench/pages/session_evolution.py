"""Session-evolution page: how one song changed across saved versions.

The P8 payoff, rendered: a variant *family* (v1, v2, v3 of the same song), the
lineage graph that connects them (DERIVED_FROM / ALTERNATIVE_OF /
SHARES_SOURCE_WITH), and a diff of each adjacent pair.

This page depends on the ``session_explorer.variants`` module and the
``fixtures/variants`` bundles. When either is absent it degrades honestly to an
``st.info`` note rather than crashing — the exhibit lights up automatically once
the variant data lands. The variants API used here:

- ``build_variant_set(bundles) -> list[VariantSet]`` (one per declared family);
- ``VariantSet.members`` — ``VariantMember``s (``.bundle`` / ``.label`` /
  ``.snapshot_id``), ordered by lineage ordinal;
- ``build_variant_graph(variant_set, layer=...) -> nx.MultiDiGraph``;
- ``variant_diff(a_bundle, b_bundle) -> StateDelta``.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import streamlit as st

from session_explorer.loaders import SnapshotBundle
from session_explorer.workbench import copy as wcopy
from session_explorer.workbench import state

from .canonical_graph import _embed_html
from .intervention import _fmt_value, _static_table

_REPO_ROOT = Path(__file__).resolve().parents[4]
_VARIANTS_ROOT = _REPO_ROOT / "fixtures" / "variants"
_LINEAGE_HEIGHT = 460


def _load_variants_module():
    """The variants API module, or ``None`` if the parallel workstream hasn't landed."""
    try:
        from session_explorer import variants  # type: ignore
    except Exception:  # noqa: BLE001 - absence is expected, not an error
        return None
    return variants


def _discover_variant_bundles() -> List[SnapshotBundle]:
    """Every variant bundle under ``fixtures/variants`` (any nesting depth)."""
    if not _VARIANTS_ROOT.is_dir():
        return []
    bundles: List[SnapshotBundle] = []
    for snapshot_path in sorted(_VARIANTS_ROOT.rglob("canonical.snapshot.json")):
        try:
            bundles.append(state.load_bundle_cached(snapshot_path.parent))
        except Exception:  # noqa: BLE001 - a bad bundle must not kill the page
            continue
    return bundles


def _member_label(member) -> str:
    return member.label or member.snapshot_id


def _diff_rows(diff) -> list[dict]:
    """Flatten a ``StateDelta`` version-to-version diff into table rows."""
    rows: list[dict] = []
    for record in diff.added_entities:
        rows.append({"change": "added", "what": record.type, "detail": record.label})
    for record in diff.removed_entities:
        rows.append({"change": "removed", "what": record.type, "detail": record.label})
    for record in diff.added_relationships:
        rows.append(
            {"change": "added edge", "what": record.type, "detail": record.label}
        )
    for record in diff.removed_relationships:
        rows.append(
            {"change": "removed edge", "what": record.type, "detail": record.label}
        )
    for record in diff.changed:
        rows.append({"change": "changed", "what": record.type, "detail": record.label})
    for pc in diff.parameter_changes:
        rows.append(
            {
                "change": "parameter",
                "what": pc.role or pc.name,
                "detail": f"{_fmt_value(pc.before_value)} → {_fmt_value(pc.after_value)}",
            }
        )
    return rows


def _render_lineage(variants, variant_set) -> None:
    st.subheader(wcopy.EVOLUTION["lineage_header"])
    try:
        from session_explorer.core.viz import build_pyvis_html

        # The ``variant`` layer keeps the graph to lineage: VARIANT / PROJECT /
        # MEDIA_ASSET nodes plus the cross-snapshot DERIVED_FROM /
        # ALTERNATIVE_OF / SHARES_SOURCE_WITH edges the builder adds.
        graph = variants.build_variant_graph(variant_set, layer="variant")
        html = build_pyvis_html(graph, height=f"{_LINEAGE_HEIGHT}px")
        _embed_html(html, height=_LINEAGE_HEIGHT)
    except Exception as exc:  # noqa: BLE001 - never blank-screen the exhibit
        st.caption(f"Lineage graph unavailable ({exc}).")


def _render_diffs(variants, members) -> None:
    st.subheader(wcopy.EVOLUTION["diff_header"])
    if len(members) < 2:
        st.caption("Only one version in this family — nothing to diff.")
        return
    for earlier, later in zip(members, members[1:]):
        st.markdown(f"**{_member_label(earlier)} → {_member_label(later)}**")
        try:
            diff = variants.variant_diff(earlier.bundle, later.bundle)
            rows = _diff_rows(diff)
            if rows:
                _static_table(rows)
            else:
                st.caption("No structural or parameter differences.")
        except Exception as exc:  # noqa: BLE001
            st.caption(f"Diff unavailable ({exc}).")


def _render(header: str, intro: str) -> None:
    st.header(header)
    st.markdown(intro)

    variants = _load_variants_module()
    variant_bundles = _discover_variant_bundles()
    if variants is None or not variant_bundles:
        st.info(wcopy.EVOLUTION["unavailable"])
        return

    try:
        sets = [s for s in variants.build_variant_set(variant_bundles) if len(s) >= 1]
    except Exception as exc:  # noqa: BLE001 - shape mismatch degrades honestly
        st.info(wcopy.EVOLUTION["unavailable"])
        st.caption(f"(variants module present but its output could not be read: {exc})")
        return

    if not sets:
        st.info(wcopy.EVOLUTION["unavailable"])
        return

    by_family = {s.family: s for s in sets}
    family = st.selectbox(
        wcopy.EVOLUTION["pick_family"], list(by_family), key="evolution_family"
    )
    variant_set = by_family[family]

    _render_lineage(variants, variant_set)
    _render_diffs(variants, variant_set.members)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def render(bundles: List[SnapshotBundle]) -> None:
    """Expert 'Session evolution' tab."""
    _render(wcopy.EVOLUTION["header"], wcopy.EVOLUTION["intro"])


def render_guided(bundles: List[SnapshotBundle]) -> None:
    """Guided 'How a song evolved' tab (same data, plain-language framing)."""
    _render(wcopy.EVOLUTION["guided_header"], wcopy.EVOLUTION["guided_intro"])
