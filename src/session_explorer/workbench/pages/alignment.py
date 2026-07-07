"""X04 alignment page: one production strategy, four native mechanisms.

The primary research screenshot. Four columns — one per DAW bundle from
``fixtures/cross-daw/X04_effect_return/bundles`` — each showing the *native*
implementation (native_type + entity name) above the shared canonical concept
badge. Below, the pairwise alignment table across the six DAW pairs for the
return/vocal strips, every row carrying the engine's human-readable reasons.

Read-only, like the whole workbench: it presents adapter exports and the
alignment engine's claims about them; it decides nothing silently.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import pandas as pd
import streamlit as st

from session_explorer.alignment import AlignmentResult, align, build_strips
from session_explorer.loaders import SnapshotBundle, get_presentation
from session_explorer.registry import get_registry
from session_explorer.workbench import state

REPO_ROOT = Path(__file__).resolve().parents[4]
X04_BUNDLES = REPO_ROOT / "fixtures" / "cross-daw" / "X04_effect_return" / "bundles"

# Presentation order for the four columns.
_DAW_ORDER = ("ableton", "reaper", "cubase", "logic")

_STATUS_COLORS = {
    "CONFIRMED": "#1E8449",
    "PROBABLE": "#239B56",
    "POSSIBLE": "#B9770E",
    "UNMATCHED": "#7B7D7D",
    "CONFLICTING": "#C0392B",
}

_BADGE_CSS = (
    "display:inline-block;padding:0.15rem 0.6rem;border-radius:1rem;"
    "background:#6C3483;color:white;font-size:0.85rem;font-weight:600;"
)
_NATIVE_CSS = (
    "display:inline-block;padding:0.1rem 0.5rem;border-radius:0.3rem;"
    "background:#EAECEE;color:#283747;font-family:monospace;font-size:0.85rem;"
)


def _load_x04_bundles() -> dict[str, SnapshotBundle]:
    bundles: dict[str, SnapshotBundle] = {}
    for name in _DAW_ORDER:
        path = X04_BUNDLES / name
        if (path / "canonical.snapshot.json").is_file():
            bundles[name] = state.load_bundle_cached(path)
    return bundles


def _concept_strip(bundle: SnapshotBundle, concept_id: str):
    for strip in build_strips(bundle.snapshot, get_registry()):
        if strip.concept_id == concept_id:
            return strip
    return None


def _column(bundle: SnapshotBundle, concept_id: str, concept_label: str) -> None:
    daw = bundle.snapshot.source.daw
    presentation = get_presentation(daw)
    st.markdown(f"**{presentation.display_name}**")
    strip = _concept_strip(bundle, concept_id)
    if strip is None:
        st.caption("no implementing entity found")
        return
    noun = get_registry().native_noun(concept_id, daw) or "/".join(
        sorted(strip.native_types)
    )
    equivalence = get_registry().equivalence(concept_id, daw)
    st.markdown(
        f"<span style='{_NATIVE_CSS}'>{noun}</span><br/>"
        f"<span style='font-size:1.05rem;font-weight:600'>{strip.name}</span><br/>"
        f"<code style='font-size:0.75rem'>{strip.primary_id}</code><br/>"
        f"<span style='{_BADGE_CSS}'>{concept_label}</span> "
        f"<span style='font-size:0.75rem;color:#6C3483'>{equivalence}</span>",
        unsafe_allow_html=True,
    )
    if strip.concept_detail:
        st.caption(strip.concept_detail)


def _pair_rows(
    bundles: dict[str, SnapshotBundle], concepts: tuple[str, ...]
) -> list[dict]:
    rows: list[dict] = []
    for a, b in combinations([n for n in _DAW_ORDER if n in bundles], 2):
        results = align(bundles[a].snapshot, bundles[b].snapshot)
        for result in results:
            if result.concept_id not in concepts and result.status != "CONFLICTING":
                continue
            rows.append(
                {
                    "pair": f"{a} → {b}",
                    "concept": result.concept_id or "—",
                    "source": f"{result.source_name} ({result.source_entity})",
                    "target": (
                        f"{result.target_name} ({result.target_entity})"
                        if result.target_entity
                        else "—"
                    ),
                    "status": result.status,
                    "confidence": result.confidence,
                    "reasons": " • ".join(result.reasons),
                }
            )
    return rows


def render() -> None:
    st.header("X04 — effect return, aligned across four DAWs")
    st.caption(
        "One semantic production strategy — *a vocal source sends to a shared "
        "reverb destination that routes to the main output* — implemented by "
        "four different native mechanisms, analyzed as one representation. "
        f"Bundles: `{X04_BUNDLES}`."
    )

    bundles = _load_x04_bundles()
    if not bundles:
        st.error(
            f"No X04 bundles found under {X04_BUNDLES}. Run the four adapter "
            "export-canonical commands (see the fixture's intent.md)."
        )
        return
    if len(bundles) < 4:
        st.warning(
            f"Only {len(bundles)} of 4 X04 bundles present: "
            + ", ".join(sorted(bundles))
        )

    st.subheader("The same strategy, four native mechanisms")
    columns = st.columns(len(bundles))
    for column, name in zip(columns, [n for n in _DAW_ORDER if n in bundles]):
        with column:
            _column(bundles[name], "effect_return", "Effect Return")

    st.divider()
    st.subheader("Pairwise alignment (six DAW pairs)")
    st.caption(
        "Every claim carries its reasons — registry concepts, name tokens, "
        "entity shape, local topology, media hashes. CONFIRMED exists only as "
        "a user annotation; the engine stops at PROBABLE."
    )

    concept_filter = st.multiselect(
        "Concepts",
        ("effect_return", "audio_source", "main_output"),
        default=["effect_return", "audio_source"],
    )
    rows = _pair_rows(bundles, tuple(concept_filter))
    if not rows:
        st.info("No alignment rows for the selected concepts.")
        return

    frame = pd.DataFrame(rows)
    st.dataframe(
        frame.style.map(
            lambda status: f"color: {_STATUS_COLORS.get(status, '#000')}; font-weight: 600",
            subset=["status"],
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "reasons": st.column_config.TextColumn("reasons", width="large"),
            "confidence": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    with st.expander("Reasons, in full"):
        for row in rows:
            st.markdown(
                f"**{row['pair']}** · {row['source']} → {row['target']} · "
                f"`{row['status']}` ({row['confidence']})"
            )
            for reason in row["reasons"].split(" • "):
                st.markdown(f"- {reason}")


# ---------------------------------------------------------------------------
# Public aliases — Guided mode (workbench/pages/guided.py) reuses these
# internals to tell the same X04 story in plain language. The aliases are the
# supported surface; the underscore names stay private to this page.
# ---------------------------------------------------------------------------

DAW_ORDER = _DAW_ORDER
load_x04_bundles = _load_x04_bundles
concept_strip = _concept_strip
pair_rows = _pair_rows
