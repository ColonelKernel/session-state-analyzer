"""Guided mode: the plain-language, story-first face of the workbench.

Four tabs — an Overview with one friendly card per loaded DAW, the X04
"same idea in four DAWs" story, a plain-words observability atlas, and the
canonical graph — all in everyday language. Every sentence lives in
:mod:`session_explorer.workbench.copy`; this module only arranges measured
data. It reuses the expert pages' internals (the alignment helpers, the atlas
bars and drill-down, the canonical graph renderer) so Guided can never drift
from the research truth: same numbers, friendlier words.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd
import streamlit as st

from session_explorer.atlas import Atlas
from session_explorer.atlas.coverage import aggregate_mix
from session_explorer.core.viz import OBSERVABILITY_COLORS
from session_explorer.loaders import SnapshotBundle, get_presentation
from session_explorer.registry import get_registry
from session_explorer.workbench import compute
from session_explorer.workbench import copy as wcopy
from session_explorer.workbench.ui import MIX_SEGMENT_COLORS, daw_label
from session_explorer.workbench.pages import alignment as alignment_page
from session_explorer.workbench.pages import atlas as atlas_page
from session_explorer.workbench.pages import canonical_graph
from session_explorer.workbench.pages import comparison as comparison_page
from session_explorer.workbench.pages import depth as depth_page
from session_explorer.workbench.pages import intervention as intervention_page
from session_explorer.workbench.pages import session_evolution as evolution_page

_ROUTING_RELS = ("CHANNEL_SENDS_TO", "CHANNEL_ROUTES_TO")


# ---------------------------------------------------------------------------
# Shared little helpers
# ---------------------------------------------------------------------------


def _plural(count: int, unit: str) -> str:
    return f"{count} {unit}" + ("" if count == 1 else "s")


def _plain_legend_html(include_absent: bool) -> str:
    """Coloured squares + plain words, one line, dependency-free."""
    keys = ["observed", "inferred", "annotation", "hidden"]
    entries = []
    for key in keys:
        entries.append(
            f"<span style='color:{OBSERVABILITY_COLORS[key]}'>■</span> "
            f"{wcopy.OBS_PLAIN[key]}"
        )
    if include_absent:
        entries.append(
            f"<span style='color:{MIX_SEGMENT_COLORS['absent']}'>■</span> "
            f"{wcopy.OBS_PLAIN['absent']}"
        )
    return " &nbsp;·&nbsp; ".join(entries)


def _glossary_expander() -> None:
    with st.expander(wcopy.COPY["glossary_title"]):
        for term, definition in wcopy.GLOSSARY.items():
            st.markdown(f"**{term}** — {definition}")


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


def _counts_line(bundle: SnapshotBundle) -> str:
    """Plain-words entity counts: "9 tracks · 22 effects · 4 routing connections"."""
    counts = {"TRACK": 0, "PROCESSOR": 0, "TEMPORAL_OBJECT": 0}
    for entity in bundle.snapshot.entities:
        if entity.entity_type in counts:
            counts[entity.entity_type] += 1
    routing = sum(
        1 for rel in bundle.snapshot.relationships if rel.rel_type in _ROUTING_RELS
    )
    parts = [_plural(counts["TRACK"], wcopy.COPY["unit_track"])]
    if counts["PROCESSOR"]:
        parts.append(_plural(counts["PROCESSOR"], wcopy.COPY["unit_effect"]))
    if counts["TEMPORAL_OBJECT"]:
        parts.append(_plural(counts["TEMPORAL_OBJECT"], wcopy.COPY["unit_clip"]))
    if routing:
        parts.append(_plural(routing, wcopy.COPY["unit_routing"]))
    return " · ".join(parts)


def _aggregate_mix(atlas: Atlas, daw: str) -> dict[str, int]:
    """The whole-session epistemic mix: atlas counts summed across domains.

    Delegates to the shared :func:`session_explorer.atlas.aggregate_mix` so the
    guided overview bars and the metrics report read the same arithmetic and
    cannot drift.
    """
    return aggregate_mix(atlas, daw)


def _mix_bar_html(mix: dict[str, int]) -> str:
    """A mini stacked "how much can we see?" bar for one DAW card."""
    total = mix["applicable"]
    if total <= 0:
        return (
            "<div style='color:#9AA0A6;font-size:1.2rem;text-align:center;"
            "padding:0.2rem 0'>&mdash;</div>"
        )
    spans = []
    for key in ("observed", "inferred", "annotated", "hidden", "absent"):
        count = mix[key]
        if count <= 0:
            continue
        pct = 100.0 * count / total
        spans.append(
            f"<span style='display:inline-block;width:{pct:.2f}%;height:12px;"
            f"background:{MIX_SEGMENT_COLORS[key]}' title='{count}'></span>"
        )
    return (
        "<div style='width:100%;line-height:0;border-radius:3px;overflow:hidden;"
        "background:#ECEFF1'>" + "".join(spans) + "</div>"
    )


def _readout(mix: dict[str, int]) -> str:
    """One plain sentence per DAW, derived from the measured mix (never
    hardcoded per DAW): dominant evidence class decides the story."""
    total = mix["applicable"]
    if total <= 0:
        return wcopy.COPY["read_none"]
    observed = mix["observed"] / total
    helped = (mix["inferred"] + mix["annotated"]) / total
    hidden = mix["hidden"] / total
    if observed >= 0.9:
        return wcopy.COPY["read_direct"]
    if helped >= observed:
        return wcopy.COPY["read_reconstructed"]
    if hidden >= 0.2:
        return wcopy.COPY["read_hidden"]
    return wcopy.COPY["read_mixed"]


def _session_name(bundle: SnapshotBundle) -> str:
    for entity in bundle.snapshot.entities:
        if entity.entity_type == "PROJECT" and entity.name:
            return entity.name
    return bundle.dir.name


def _render_overview(
    bundles: List[SnapshotBundle],
    all_bundle_names: List[str],
    atlas: Optional[Atlas],
) -> None:
    st.header(wcopy.COPY["overview_title"])
    st.markdown(wcopy.COPY["overview_intro"])

    st.button(
        wcopy.COPY["load_examples"],
        type="primary",
        disabled=not all_bundle_names,
        on_click=lambda: st.session_state.update(
            bundle_select=list(all_bundle_names)
        ),
    )
    if bundles and set(all_bundle_names) <= {b.dir.name for b in bundles}:
        st.caption(wcopy.COPY["all_loaded"].format(n=len(all_bundle_names)))

    if not bundles or atlas is None:
        st.info(wcopy.COPY["no_bundles"])
        return

    st.markdown(_plain_legend_html(include_absent=True), unsafe_allow_html=True)

    # The atlas is built from ``bundles`` in this order, so its columns align by
    # index — use each bundle's own column key (not its ``daw``, which can
    # repeat) so a real and a synthetic capture of the same DAW read distinct
    # bars instead of colliding on one shared atlas cell.
    column_keys = atlas.column_keys
    for start in range(0, len(bundles), 4):
        chunk = bundles[start : start + 4]
        chunk_keys = column_keys[start : start + 4]
        columns = st.columns(4)
        for column, bundle, col_key in zip(columns, chunk, chunk_keys):
            daw = bundle.snapshot.source.daw
            mix = _aggregate_mix(atlas, col_key)
            with column, st.container(border=True):
                st.markdown(f"**🎛️ {daw_label(daw)}**")
                st.caption(_session_name(bundle))
                st.markdown(_counts_line(bundle))
                st.caption(wcopy.COPY["bar_question"])
                st.markdown(_mix_bar_html(mix), unsafe_allow_html=True)
                st.caption(_readout(mix))


# ---------------------------------------------------------------------------
# The same idea in four DAWs (guided X04)
# ---------------------------------------------------------------------------


def _plain_reason(reason: str) -> str:
    for prefix, plain in wcopy.REASON_PLAIN:
        if reason.startswith(prefix):
            if "{detail}" in plain:
                detail = reason.split(":", 1)[1].strip() if ":" in reason else ""
                return plain.format(detail=detail)
            return plain
    return reason


def _render_x04() -> None:
    st.header(wcopy.COPY["tab_x04"])
    st.markdown(wcopy.COPY["x04_intro"])

    bundles = alignment_page.load_x04_bundles()
    if not bundles:
        st.info(wcopy.COPY["x04_missing"])
        return

    order = [name for name in alignment_page.DAW_ORDER if name in bundles]
    registry = get_registry()

    # Four columns: what each DAW natively calls the same mechanism.
    columns = st.columns(len(order))
    display: dict[str, str] = {}
    noun: dict[str, str] = {}
    for column, name in zip(columns, order):
        bundle = bundles[name]
        daw = bundle.snapshot.source.daw
        display[name] = daw_label(daw)
        # The presentation vocabulary carries the friendly noun ("Return
        # Track"); the concept registry's native_noun is a machine-facing
        # native_type id ("return_track") and is only the fallback.
        noun[name] = (
            get_presentation(daw).native_vocab.get("effect_return")
            or registry.native_noun("effect_return", daw)
            or "—"
        )
        strip = alignment_page.concept_strip(bundle, "effect_return")
        with column, st.container(border=True):
            st.markdown(f"**{display[name]}**")
            st.markdown(
                wcopy.COPY["x04_calls_it"].format(daw=display[name])
                + f" **{noun[name]}**"
            )
            if strip is not None:
                st.caption(wcopy.COPY["x04_in_session"].format(name=strip.name))

    # One friendly sentence per DAW pair.
    st.subheader(wcopy.COPY["x04_matches_header"])
    rows = alignment_page.x04_pair_rows(("effect_return",))
    for row in rows:
        if row["concept"] != "effect_return":
            continue
        a_name, b_name = (part.strip() for part in row["pair"].split("→"))
        if row["status"] in ("PROBABLE", "POSSIBLE", "CONFIRMED"):
            reasons = [
                _plain_reason(r) for r in row["reasons"].split(" • ")[:2]
            ]
            while len(reasons) < 2:
                reasons.append("the evidence agrees")
            confidence = row["confidence"] or 0.0
            st.markdown(
                wcopy.COPY["x04_match_sentence"].format(
                    a_daw=display.get(a_name, a_name),
                    a_noun=noun.get(a_name, "—"),
                    b_daw=display.get(b_name, b_name),
                    b_noun=noun.get(b_name, "—"),
                    pct=round(confidence * 100),
                    r1=reasons[0],
                    r2=reasons[1],
                )
            )
        elif row["status"] == "CONFLICTING":
            st.markdown(
                wcopy.COPY["x04_match_conflicting"].format(
                    a_daw=display.get(a_name, a_name),
                    b_daw=display.get(b_name, b_name),
                )
            )
        else:
            st.markdown(
                wcopy.COPY["x04_match_unmatched"].format(
                    a_daw=display.get(a_name, a_name),
                    b_daw=display.get(b_name, b_name),
                )
            )

    with st.expander(wcopy.COPY["x04_table_expander"]):
        full = alignment_page.x04_pair_rows(("effect_return", "audio_source"))
        st.dataframe(pd.DataFrame(full), hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# What each DAW lets us see (guided atlas)
# ---------------------------------------------------------------------------


def _friendly_cell_caption(cell) -> str:
    if not cell.applicable_present:
        return (
            wcopy.COPY["cell_declared_only"]
            if cell.declared
            else wcopy.COPY["cell_na"]
        )
    direct = cell.direct_observability or 0.0
    combined = cell.combined_coverage or 0.0
    hidden = cell.hidden_ratio or 0.0
    parts = [wcopy.COPY["cell_direct"].format(pct=f"{direct:.0%}")]
    helped = combined - direct
    if helped > 0:
        parts.append(wcopy.COPY["cell_recovered"].format(pct=f"{helped:.0%}"))
    if hidden > 0:
        parts.append(wcopy.COPY["cell_locked"].format(pct=f"{hidden:.0%}"))
    return " · ".join(parts)


def _render_atlas(atlas: Optional[Atlas], bundles: List[SnapshotBundle]) -> None:
    st.header(wcopy.COPY["tab_atlas"])
    st.markdown(wcopy.COPY["atlas_intro"])

    if atlas is None or not bundles:
        st.info(wcopy.COPY["no_bundles"])
        return

    st.markdown(_plain_legend_html(include_absent=True), unsafe_allow_html=True)

    col_labels = atlas_page._column_labels(atlas)
    header = st.columns([1.6] + [1] * len(atlas.columns))
    header[0].markdown(f"**{wcopy.COPY['atlas_row_header']}**")
    for column, col in zip(header[1:], atlas.columns):
        column.markdown(f"**{col_labels[col.key]}**")

    for domain_name in atlas.domains:
        label, subtitle = wcopy.ATLAS_ROWS.get(domain_name, (domain_name, ""))
        row = st.columns([1.6] + [1] * len(atlas.columns))
        with row[0]:
            st.markdown(f"**{label}**")
            if subtitle:
                st.caption(subtitle)
        for column, col in zip(row[1:], atlas.columns):
            cell = atlas.cell(domain_name, col.key)
            with column:
                # Reuse the expert page's bar so the two modes cannot drift.
                st.markdown(atlas_page._bar_html(cell), unsafe_allow_html=True)
                st.caption(_friendly_cell_caption(cell))

    st.divider()
    st.subheader(wcopy.COPY["atlas_closer"])
    st.caption(wcopy.COPY["atlas_closer_caption"])
    _glossary_expander()
    # The expert drill-down, verbatim: same widgets, same numbers.
    atlas_page._render_drilldown(atlas, bundles)


# ---------------------------------------------------------------------------
# Explore the graph
# ---------------------------------------------------------------------------


def _render_graph(bundles: List[SnapshotBundle]) -> None:
    st.header(wcopy.COPY["tab_graph"])
    st.markdown(wcopy.COPY["graph_intro"])

    if not bundles:
        st.info(wcopy.COPY["no_bundles"])
        return

    labels = list(wcopy.GRAPH_LAYERS)
    label = st.radio(
        wcopy.COPY["graph_layer_question"],
        labels,
        index=len(labels) - 1,  # "Everything" by default
        horizontal=True,
        key="guided_graph_layer",
    )
    st.markdown(
        wcopy.COPY["graph_legend_title"]
        + "&nbsp; "
        + _plain_legend_html(include_absent=False),
        unsafe_allow_html=True,
    )
    canonical_graph.render(bundles, wcopy.GRAPH_LAYERS[label])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def render(bundles: List[SnapshotBundle], all_bundle_names: List[str]) -> None:
    """The whole Guided mode: eight story tabs over the loaded bundles."""
    atlas = compute.atlas_for(bundles) if bundles else None
    (
        overview_tab,
        x04_tab,
        atlas_tab,
        graph_tab,
        grouping_tab,
        intervention_tab,
        evolution_tab,
        comparison_tab,
    ) = st.tabs(
        [
            wcopy.COPY["tab_overview"],
            wcopy.COPY["tab_x04"],
            wcopy.COPY["tab_atlas"],
            wcopy.COPY["tab_graph"],
            wcopy.COPY["tab_grouping"],
            wcopy.COPY["tab_intervention"],
            wcopy.COPY["tab_evolution"],
            wcopy.COPY["tab_comparison"],
        ]
    )
    with overview_tab:
        _render_overview(bundles, all_bundle_names, atlas)
    with x04_tab:
        _render_x04()
    with atlas_tab:
        _render_atlas(atlas, bundles)
    with graph_tab:
        _render_graph(bundles)
    with grouping_tab:
        depth_page.render_guided(bundles)
    with intervention_tab:
        intervention_page.render_guided()
    with evolution_tab:
        evolution_page.render_guided(bundles)
    with comparison_tab:
        comparison_page.render_guided(bundles)
