"""Observability Atlas page: measured per-domain observability, four DAWs.

The flagship research visual. Rows are the ten canonical atlas domains, columns
the loaded DAW bundles; each cell is a compact stacked bar of the epistemic
mix (observed / inferred+annotated / hidden / unsupported) over the domain's
applicable items, with the three headline ratios beneath. NOT_APPLICABLE cells
render a muted em-dash — the honest "nothing to see here", never hidden.

Click a domain x DAW below the grid to drill into the exact entities and
fields behind the numbers, and the adapter's *declared* read capabilities
alongside them: the measured reading and the claimed one, side by side. An
unknown-state map per DAW categorizes everything the snapshot admits it does
not plainly know.

Read-only, like the whole workbench: it presents adapter exports and the
atlas's arithmetic over them; it decides nothing silently.
"""

from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from session_explorer.atlas import (
    ATLAS_DOMAINS,
    AtlasCell,
    get_domain,
    unknown_state_map,
)
from session_explorer.loaders import SnapshotBundle
from session_explorer.workbench import compute
from session_explorer.workbench.ui import MIX_SEGMENT_COLORS, daw_label, require_bundle

# Bar segment colours reuse the shared evidence-mix palette (defined once in
# workbench.ui) so the atlas cell bars and the guided mini-bars cannot drift.
# inferred + annotation stay distinct bands; unsupported/unknown/not_present are
# the grey "honest absence" tail.
_SEG_OBSERVED = MIX_SEGMENT_COLORS["observed"]
_SEG_INFERRED = MIX_SEGMENT_COLORS["inferred"]
_SEG_ANNOTATION = MIX_SEGMENT_COLORS["annotated"]
_SEG_HIDDEN = MIX_SEGMENT_COLORS["hidden"]
_SEG_ABSENT = MIX_SEGMENT_COLORS["absent"]


def _bar_html(cell: AtlasCell) -> str:
    """A dependency-free stacked horizontal bar for one cell's epistemic mix."""
    m = cell.measured
    total = m.applicable
    if total <= 0:
        return (
            "<div style='color:#9AA0A6;font-size:1.4rem;text-align:center;"
            "padding:0.2rem 0'>&mdash;</div>"
        )
    segments = [
        (m.observed, _SEG_OBSERVED),
        (m.inferred, _SEG_INFERRED),
        (m.annotated, _SEG_ANNOTATION),
        (m.hidden, _SEG_HIDDEN),
        (m.unsupported + m.not_present + m.unknown, _SEG_ABSENT),
    ]
    spans = []
    for count, color in segments:
        if count <= 0:
            continue
        pct = 100.0 * count / total
        spans.append(
            f"<span style='display:inline-block;width:{pct:.2f}%;height:14px;"
            f"background:{color}' title='{count}'></span>"
        )
    return (
        "<div style='width:100%;line-height:0;border-radius:3px;overflow:hidden;"
        "background:#ECEFF1'>" + "".join(spans) + "</div>"
    )


def _ratio_caption(cell: AtlasCell) -> str:
    def fmt(value):
        return "—" if value is None else f"{value:.0%}"

    return (
        f"obs {fmt(cell.direct_observability)} · "
        f"rec {fmt(cell.combined_coverage)} · "
        f"hid {fmt(cell.hidden_ratio)}"
    )


def _column_labels(atlas) -> dict[str, str]:
    """Column-key -> display label, disambiguated when a DAW loads twice.

    One bundle per DAW keeps the plain display name; when the same ``daw`` backs
    more than one column (e.g. a synthetic and a real REAPER capture) each label
    is qualified by its bundle directory so the columns stay tellable apart.
    """
    daw_totals: dict[str, int] = {}
    for column in atlas.columns:
        daw_totals[column.daw] = daw_totals.get(column.daw, 0) + 1
    labels: dict[str, str] = {}
    for column in atlas.columns:
        name = daw_label(column.daw)
        if daw_totals[column.daw] > 1:
            name = f"{name} · {column.dir_name}"
        labels[column.key] = name
    return labels


def _render_grid(atlas) -> None:
    st.subheader("The grid — ten domains, measured across every loaded DAW")
    st.caption(
        "Each bar is the epistemic mix over a domain's *applicable* items: "
        f"<span style='color:{_SEG_OBSERVED}'>■</span> observed · "
        f"<span style='color:{_SEG_INFERRED}'>■</span> inferred · "
        f"<span style='color:{_SEG_ANNOTATION}'>■</span> annotated · "
        f"<span style='color:{_SEG_HIDDEN}'>■</span> hidden (known, not "
        "recoverable) · "
        f"<span style='color:{_SEG_ABSENT}'>■</span> unsupported/unknown. "
        "Captions: obs = direct observability, rec = recovered (observed + "
        "inferred + annotated), hid = hidden share.",
        unsafe_allow_html=True,
    )

    labels = _column_labels(atlas)
    header = st.columns([1.4] + [1] * len(atlas.columns))
    header[0].markdown("**Domain**")
    for column, col in zip(header[1:], atlas.columns):
        column.markdown(f"**{labels[col.key]}**")

    for domain_name in atlas.domains:
        row = st.columns([1.4] + [1] * len(atlas.columns))
        with row[0]:
            st.markdown(f"**{domain_name}**")
            st.caption(get_domain(domain_name).description)
        for column, col in zip(row[1:], atlas.columns):
            cell = atlas.cell(domain_name, col.key)
            with column:
                if not cell.applicable_present:
                    st.markdown(_bar_html(cell), unsafe_allow_html=True)
                    label = "declared only" if cell.declared else "not applicable"
                    st.caption(f"{label} · {cell.status.replace('_', ' ').lower()}")
                else:
                    st.markdown(_bar_html(cell), unsafe_allow_html=True)
                    st.caption(_ratio_caption(cell))


def _refs_frame(
    refs, entity_col: str = "entity / source", field_col: str = "field"
) -> pd.DataFrame:
    return pd.DataFrame(
        [{entity_col: e, field_col: f} for e, f in refs]
    )


# The drill-down's research-voice wording. Guided passes
# ``wcopy.ATLAS_DRILLDOWN`` over these key-for-key (plus ``domain_labels`` for
# the friendly row names); Expert passes nothing and reads these verbatim.
# ``status_<STATUS>`` keys are optional — when absent the raw ``AtlasCell.status``
# is prettified instead — and ``support_<KEY>`` keys likewise fall back to the
# manifest's raw FULL/PARTIAL/NONE.
_DRILLDOWN_TEXT: dict[str, str] = {
    "header": "Drill-down — click a domain and DAW",
    "caption": (
        "The measured reading (which entities and fields, in which epistemic "
        "bucket) beside the adapter's *declared* read capability for the same "
        "domain."
    ),
    "pick_domain": "Domain",
    "pick_daw": "DAW",
    "metric_applicable": "Applicable",
    "metric_direct": "Direct observability",
    "metric_hidden": "Hidden",
    "profile_label": "Profile",
    "measured_header": "**Measured** — entities and fields behind the numbers",
    "bucket_observed": "observed",
    "bucket_inferred": "inferred",
    "bucket_annotated": "annotated",
    "bucket_hidden": "hidden",
    "bucket_absent": "unsupported / not-present / unknown",
    "measured_empty": (
        "No measured items — this domain has no scope in this snapshot."
    ),
    "declared_header": "**Declared** — the adapter's read capability manifest",
    "declared_none": (
        "The adapter declares no read capability that maps to this domain."
    ),
    "declared_caption": "{n} declared fields · support {tally}",
    "col_domain": "domain",
    "col_field": "field",
    "col_support": "support",
    "col_capture": "capture_method",
    "col_stability": "source_stability",
    "col_validation": "validation",
    "refs_entity": "entity / source",
    "refs_field": "field",
}


def _render_drilldown(
    atlas,
    bundles: List[SnapshotBundle],
    *,
    text: dict[str, str] | None = None,
    domain_labels: dict[str, str] | None = None,
) -> None:
    t = {**_DRILLDOWN_TEXT, **(text or {})}
    domain_labels = domain_labels or {}

    st.divider()
    st.subheader(t["header"])
    st.caption(t["caption"])

    labels = _column_labels(atlas)
    pick_domain, pick_daw = st.columns(2)
    # Keys are shared across the two modes (only one renders per run), so the
    # picked cell survives a Guided <-> Expert switch; options stay the raw
    # domain ids with the friendly name applied as a format_func.
    domain_name = pick_domain.selectbox(
        t["pick_domain"],
        ATLAS_DOMAINS,
        format_func=lambda name: domain_labels.get(name, name),
        key="atlas_dd_domain",
    )
    column_key = pick_daw.selectbox(
        t["pick_daw"],
        atlas.column_keys,
        format_func=lambda key: labels.get(key, key),
        key="atlas_dd_daw",
    )
    cell = atlas.cell(domain_name, column_key)

    obs_col, ratio_col, hid_col = st.columns(3)
    obs_col.metric(t["metric_applicable"], cell.measured.applicable)
    ratio_col.metric(
        t["metric_direct"],
        "—" if cell.direct_observability is None else f"{cell.direct_observability:.0%}",
    )
    hid_col.metric(
        t["metric_hidden"],
        "—" if cell.hidden_ratio is None else f"{cell.hidden_ratio:.0%}",
    )
    status_text = t.get(f"status_{cell.status}") or cell.status.replace(
        "_", " "
    ).lower()
    st.caption(f"{t['profile_label']}: **{status_text}**")

    measured_col, declared_col = st.columns(2)

    with measured_col:
        st.markdown(t["measured_header"])
        m = cell.measured
        buckets = [
            (t["bucket_observed"], m.observed_refs, m.field_refs.get("observed", [])),
            (t["bucket_inferred"], m.inferred_refs, m.field_refs.get("inferred", [])),
            (t["bucket_annotated"], m.annotated_refs, m.field_refs.get("annotated", [])),
            (t["bucket_hidden"], m.hidden_refs, m.field_refs.get("hidden", [])),
            (
                t["bucket_absent"],
                m.unsupported_refs + m.not_present_refs + m.unknown_refs,
                [],
            ),
        ]
        any_shown = False
        for label, primary, field_extra in buckets:
            combined = list(primary) + list(field_extra)
            if not combined:
                continue
            any_shown = True
            with st.expander(f"{label} ({len(combined)})"):
                st.dataframe(
                    _refs_frame(combined, t["refs_entity"], t["refs_field"]),
                    hide_index=True,
                    width="stretch",
                )
        if not any_shown:
            st.info(t["measured_empty"])

    with declared_col:
        st.markdown(t["declared_header"])
        declared = cell.declared
        if declared is None:
            st.info(t["declared_none"])
        else:
            tally = ", ".join(
                f"{t.get(f'support_{k}', k)} {v}"
                for k, v in sorted(declared.support.items())
            )
            st.caption(
                t["declared_caption"].format(n=declared.field_count, tally=tally)
            )

            # With the "plain_values" marker (Guided), the table's cell values
            # are translated too — support through the support_* words, the
            # other manifest tokens prettified from SHOUTY_SNAKE — so the table
            # never shows "FULL" one line under a caption that said "fully".
            # Expert has no marker and shows the manifest tokens verbatim.
            plain = "plain_values" in t

            def _value(token: str | None) -> str:
                if not token:
                    return "—"
                return token.replace("_", " ").lower() if plain else token

            def _support_value(token: str) -> str:
                if plain:
                    return t.get(f"support_{token}", _value(token))
                return token

            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            t["col_domain"]: _value(row.capability_domain),
                            t["col_field"]: _value(row.field_name),
                            t["col_support"]: _support_value(row.support),
                            t["col_capture"]: _value(row.capture_method),
                            t["col_stability"]: _value(row.source_stability),
                            t["col_validation"]: _value(row.validation_status),
                        }
                        for row in declared.fields
                    ]
                ),
                hide_index=True,
                width="stretch",
            )


def _render_unknown_map(bundles: List[SnapshotBundle]) -> None:
    st.divider()
    st.subheader("Unknown-state map")
    st.caption(
        "Everything a snapshot admits it does not plainly know, categorized "
        "from the availability ledger, HIDDEN-evidence fields, and recorded "
        "failures."
    )
    for bundle in bundles:
        daw = bundle.snapshot.source.daw
        usm = unknown_state_map(bundle.snapshot)
        total = sum(len(v) for v in usm.values())
        with st.expander(f"{daw_label(daw)} — {total} unknown/hidden items"):
            if total == 0:
                st.caption("This snapshot claims nothing hidden or unknown.")
                continue
            for category, refs in usm.items():
                if not refs:
                    continue
                st.markdown(f"**{category}** ({len(refs)})")
                st.dataframe(_refs_frame(refs), hide_index=True, width="stretch")


def render(bundles: List[SnapshotBundle]) -> None:
    """The observability atlas over the selected bundles."""
    st.header("Observability atlas")
    st.caption(
        "Measured per-domain observability across the loaded DAWs — honest "
        "profiles, not a single score. Two readings kept apart: what each "
        "snapshot *measured*, and what its adapter *declares* it can read."
    )

    if not require_bundle(bundles):
        return

    atlas = compute.atlas_for(bundles)
    _render_grid(atlas)
    _render_drilldown(atlas, bundles)
    _render_unknown_map(bundles)
