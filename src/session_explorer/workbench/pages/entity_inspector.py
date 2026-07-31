"""Entity inspector: one entity, three truths — canonical, native, evidence.

The seed of the evidence inspector: every canonical value on screen is
visibly traceable to a provenance record, and every field the adapter could
*not* observe is stated (availability), never silently absent.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd
import streamlit as st

from canonical_snapshot import CanonicalDAWSnapshot, Entity
from session_explorer.loaders import SnapshotBundle, get_presentation
from session_explorer.workbench.ui import bundle_label, require_bundle

_AVAILABILITY_HIGHLIGHT = "background-color: #FDEBD0"  # amber: could-not-observe rows


def _entity_label(entity: Entity) -> str:
    name = entity.name or "(unnamed)"
    return f"{entity.entity_type} · {name} · {entity.id}"


def _sorted_entities(snapshot: CanonicalDAWSnapshot) -> List[Entity]:
    """Entities grouped by entity_type, then by name/id within a group."""
    return sorted(
        snapshot.entities,
        key=lambda e: (e.entity_type, (e.name or "").lower(), e.id),
    )


def _canonical_section(entity: Entity, daw: str) -> None:
    st.subheader("Canonical")
    vocab = get_presentation(daw).native_vocab
    native_noun = vocab.get(entity.entity_type)
    st.markdown(
        f"**{entity.name or '(unnamed)'}**  \n"
        f"type: `{entity.entity_type}`"
        + (f" — *{native_noun}* in this DAW's vocabulary" if native_noun else "")
    )
    if entity.semantic_roles:
        st.markdown("Semantic roles: " + ", ".join(f"`{r}`" for r in entity.semantic_roles))
    if entity.properties:
        st.caption("Properties")
        st.dataframe(
            pd.DataFrame(
                [(k, str(v)) for k, v in entity.properties.items()],
                columns=["property", "value"],
            ),
            hide_index=True,
            width="stretch",
        )
    if entity.availability:
        st.caption("Availability — what this snapshot does not know, and why")
        st.dataframe(
            pd.DataFrame(
                [(field, status) for field, status in entity.availability.items()],
                columns=["field", "availability"],
            ).style.apply(
                lambda row: [_AVAILABILITY_HIGHLIGHT] * len(row), axis=1
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Availability: all fields AVAILABLE (no exceptions recorded).")


def _native_section(entity: Entity) -> None:
    st.subheader("Native")
    if entity.native is None:
        st.caption("No native reference: the adapter recorded no DAW-native identity.")
        return
    st.markdown(
        f"DAW: `{entity.native.daw}`  \n"
        f"native type: `{entity.native.native_type or '—'}`"
    )
    if entity.native.properties:
        st.json(entity.native.properties, expanded=False)
    else:
        st.caption("No native properties beyond the canonical core.")


def _evidence_rows(
    entity: Entity, snapshot: CanonicalDAWSnapshot
) -> pd.DataFrame:
    rows = []
    for field, ref in sorted(entity.prov.items()):
        record = snapshot.provenance_by_id(ref)
        if record is None:
            rows.append(
                {
                    "field": field,
                    "kind": "provenance",
                    "record": ref,
                    "evidence": "DANGLING REFERENCE",
                    "capture_method": "",
                    "source_stability": "",
                    "confidence": None,
                    "explanation": "prov ref does not resolve in the store",
                }
            )
            continue
        rows.append(
            {
                "field": "* (entity default)" if field == "*" else field,
                "kind": "provenance",
                "record": record.id,
                "evidence": record.evidence,
                "capture_method": record.capture_method,
                "source_stability": record.source_stability,
                "confidence": record.confidence,
                "explanation": record.explanation or "",
            }
        )
    for field, status in sorted(entity.availability.items()):
        rows.append(
            {
                "field": field,
                "kind": "availability",
                "record": "",
                "evidence": status,
                "capture_method": "",
                "source_stability": "",
                "confidence": None,
                "explanation": "field not AVAILABLE — see availability status",
            }
        )
    return pd.DataFrame(rows)


def _evidence_section(entity: Entity, snapshot: CanonicalDAWSnapshot) -> None:
    st.subheader("Evidence")
    frame = _evidence_rows(entity, snapshot)
    if frame.empty:
        st.caption("No provenance references on this entity.")
        return
    styled = frame.style.apply(
        lambda row: [
            _AVAILABILITY_HIGHLIGHT if row["kind"] == "availability" else ""
        ]
        * len(row),
        axis=1,
    )
    st.dataframe(styled, hide_index=True, width="stretch")


def render(bundles: List[SnapshotBundle]) -> None:
    """Bundle → entity → canonical / native / evidence, side by side."""
    if not require_bundle(bundles):
        return

    bundle = st.selectbox(
        "Bundle",
        bundles,
        format_func=bundle_label,
        key="inspector_bundle",
    )
    if bundle is None:  # pragma: no cover - selectbox always yields with options
        return
    snapshot = bundle.snapshot

    entity: Optional[Entity] = st.selectbox(
        "Entity (grouped by type)",
        _sorted_entities(snapshot),
        format_func=_entity_label,
        key="inspector_entity",
    )
    if entity is None:  # pragma: no cover
        return

    canonical_col, native_col, evidence_col = st.columns(3)
    with canonical_col:
        _canonical_section(entity, snapshot.source.daw)
    with native_col:
        _native_section(entity)
    with evidence_col:
        _evidence_section(entity, snapshot)
