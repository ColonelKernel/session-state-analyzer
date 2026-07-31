"""Adapter comparison dashboard (Phase 3): four instruments, side by side.

The Phase-3 packaging surface — the compatibility ladder + the metrics report,
read as a *per-DAW profiles dashboard*. Every loaded bundle becomes one column;
each row is one measurable facet of what that adapter's capture demonstrates:

    Schema valid                does it re-validate against the v0.2 contract
    Domain coverage             share recovered by any means (obs+inf+annot)
    Evidence mix                the epistemic mix bar (reuses the atlas bar)
    Provenance completeness     share of prov refs that resolve into the store
    Fixture conformance         load-time errors/warnings + shipped agreement
    Compatibility ladder        the L0..L6 reached-set chips (never a rank)
    Declared read capability    what the capability manifest claims it reads
    Alignment confidence        mean X04 cross-DAW alignment confidence

The load-bearing rule (master-prompt §50): this is **not a ranking**. The
columns are profiles, not a leaderboard — different instruments observe
different things, and "higher" is never "better". The ladder chips are the
clearest expression of that: a real profile is frequently non-contiguous.

Both the Expert "Adapter comparison" tab and the Guided "How the DAWs compare"
tab call the same private ``_dashboard`` body, so the two faces share the
computation and cannot drift — the atlas/guided reuse pattern. Everything is
read from an existing analyzer surface (the atlas, the ladder, the metrics
report, the X04 alignment engine), so the dashboard cannot disagree with the
pages that show those numbers on their own.
"""

from __future__ import annotations

from typing import List, Optional

import streamlit as st

from session_explorer.atlas import AtlasCell, MeasuredCoverage
from session_explorer.atlas.coverage import aggregate_mix
from session_explorer.compat import (
    LEVEL_META,
    LadderProfile,
    assess_bundle,
    render_ladder_markdown,
)
from session_explorer.loaders import SnapshotBundle, get_presentation
from session_explorer.metrics import metrics_report
from session_explorer.workbench import compute
from session_explorer.workbench import copy as wcopy
from session_explorer.workbench import state
from session_explorer.workbench.pages import alignment as alignment_page
from session_explorer.workbench.pages import atlas as atlas_page

# The concept the X04 alignment engine measures across the four native
# mechanisms; the dashboard reads its confidence as the alignment column.
_X04_CONCEPT = "effect_return"

# Ladder-chip colours: reached / reached-but-provisional / not-reached. Same
# green/amber/grey language the atlas and markdown ladder use.
_LADDER_REACHED = "#1E8449"
_LADDER_PROVISIONAL = "#B9770E"
_LADDER_ABSENT = "#9AA0A6"

_OK_GREEN = "#1E8449"
_NO_RED = "#C0392B"


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------


def _daw_label(daw: str) -> str:
    try:
        return get_presentation(daw).display_name
    except Exception:  # noqa: BLE001 - an unknown daw still gets a column
        return daw


def _pct(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:.0%}"


def _bool_html(ok: bool) -> str:
    color = _OK_GREEN if ok else _NO_RED
    return f"<span style='color:{color};font-weight:700;font-size:1.1rem'>{'✓' if ok else '✗'}</span>"


def _combined_coverage(mix: dict[str, int]) -> Optional[float]:
    """Whole-session recovered share: observed + inferred + annotated / applicable."""
    applicable = mix["applicable"]
    if applicable <= 0:
        return None
    return (mix["observed"] + mix["inferred"] + mix["annotated"]) / applicable


def _mix_cell(daw: str, mix: dict[str, int]) -> AtlasCell:
    """Wrap a whole-session :func:`aggregate_mix` dict as an ``AtlasCell``.

    Lets the dashboard reuse the atlas page's exact ``_bar_html`` for the
    whole-session evidence bar — the three honest-absence buckets fold into
    ``unsupported`` (the bar sums the trio into one grey tail anyway), so the
    rendered bar is identical to the per-domain atlas bars.
    """
    measured = MeasuredCoverage(
        applicable=mix["applicable"],
        observed=mix["observed"],
        inferred=mix["inferred"],
        annotated=mix["annotated"],
        hidden=mix["hidden"],
        unsupported=mix["absent"],
    )
    return AtlasCell(domain_name="(session)", daw=daw, measured=measured, declared=None)


def _ladder_chips_html(profile: LadderProfile, *, plain: bool) -> str:
    """The seven L0..L6 rungs as compact chips: ✓ reached · ~ provisional · · not.

    Chip tooltips carry the rung title — the research title in Expert, the
    friendly one-line gloss in Guided — so the reached *set* reads at a glance
    without ever collapsing to a single number.
    """
    chips: list[str] = []
    for assessment in profile.levels:
        if not assessment.reached:
            symbol, color = "·", _LADDER_ABSENT
        elif assessment.provisional:
            symbol, color = "~", _LADDER_PROVISIONAL
        else:
            symbol, color = "✓", _LADDER_REACHED
        if plain:
            title = wcopy.LADDER_RUNGS_PLAIN.get(assessment.level, assessment.title)
        else:
            title = LEVEL_META[assessment.level][1]
        chips.append(
            f"<span title='L{assessment.level} — {title}' "
            "style='display:inline-block;min-width:2.2rem;text-align:center;"
            f"margin:1px;padding:1px 4px;border-radius:5px;font-size:0.72rem;"
            f"color:{color};border:1px solid {color}55'>"
            f"L{assessment.level}{symbol}</span>"
        )
    return "<div style='line-height:1.9'>" + "".join(chips) + "</div>"


def _conformance_text(bundle: SnapshotBundle) -> str:
    """Load-time errors/warnings, and whether the shipped report agrees."""
    report = bundle.validation
    n_err = len(report.errors)
    n_warn = len(report.warnings)
    shipped = bundle.shipped_validation
    if shipped is None:
        agreement = "no shipped report"
    elif bool(shipped.get("valid")) == report.valid:
        agreement = "shipped agrees"
    else:
        agreement = "shipped disagrees"
    return f"{n_err} err · {n_warn} warn · {agreement}"


def _capability_text(bundle: SnapshotBundle) -> str:
    """A one-line read-capability summary from the adapter's manifest."""
    manifest = bundle.capabilities
    if manifest is None:
        return "no manifest shipped"
    support: dict[str, int] = {}
    field_count = 0
    for domain_capability in manifest.read.values():
        for capability in domain_capability.fields.values():
            field_count += 1
            support[capability.support] = support.get(capability.support, 0) + 1
    if field_count == 0:
        return "no read capability declared"
    tally = " · ".join(
        f"{key} {support[key]}" for key in ("FULL", "PARTIAL", "NONE") if key in support
    )
    return f"{field_count} read fields · {tally}"


def _alignment_confidence(
    bundle: SnapshotBundle, x04: dict[str, SnapshotBundle], rows: List[dict]
) -> Optional[float]:
    """Mean X04 alignment confidence over every pair this DAW participates in.

    The X04 dict is keyed by DAW slug (ableton/reaper/cubase/logic); the pair
    strings ("ableton → reaper") use those slugs. A dashboard column's DAW is
    the snapshot's ``source.daw`` (e.g. ``logic_pro``), so we map back to the
    slug through the X04 bundles before matching pairs.
    """
    if not x04 or not rows:
        return None
    daw = bundle.snapshot.source.daw
    slug = next(
        (k for k, b in x04.items() if b.snapshot.source.daw == daw), None
    )
    if slug is None:
        return None
    confidences = [
        row["confidence"]
        for row in rows
        if row.get("confidence") is not None
        and slug in [part.strip() for part in row["pair"].split("→")]
    ]
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


# ---------------------------------------------------------------------------
# Grid rendering (shared body)
# ---------------------------------------------------------------------------


def _header_row(bundles: List[SnapshotBundle], col_header: str) -> None:
    header = st.columns([1.5] + [1] * len(bundles))
    header[0].markdown(f"**{col_header}**")
    for column, bundle in zip(header[1:], bundles):
        column.markdown(f"**{_daw_label(bundle.snapshot.source.daw)}**")
        column.caption(bundle.dir.name)


def _text_row(
    bundles: List[SnapshotBundle],
    label: str,
    desc: str,
    values: List[str],
    *,
    html: bool = False,
) -> None:
    row = st.columns([1.5] + [1] * len(bundles))
    with row[0]:
        st.markdown(f"**{label}**")
        if desc:
            st.caption(desc)
    for column, value in zip(row[1:], values):
        with column:
            if html:
                st.markdown(value, unsafe_allow_html=True)
            else:
                st.markdown(value)


def _dashboard(
    bundles: List[SnapshotBundle],
    *,
    labels: dict[str, str],
    plain: bool,
    key_suffix: str,
) -> None:
    """The whole dashboard body — one column per bundle, one facet per row.

    Shared verbatim by Expert and Guided; the ``labels`` dict swaps research
    vocabulary for plain language, ``plain`` swaps the ladder-chip tooltips,
    and ``key_suffix`` keeps the two modes' download-button keys distinct.
    """
    atlas = compute.atlas_for(bundles)
    x04 = alignment_page.load_x04_bundles()
    align_rows = (
        alignment_page.x04_pair_rows((_X04_CONCEPT,)) if x04 else []
    )
    profiles = [assess_bundle(bundle) for bundle in bundles]
    # ``atlas`` was built from ``bundles`` in this order, so its column keys line
    # up by index — key each bundle's mix on its own column (not its ``daw``,
    # which repeats when a DAW loads twice) so duplicate-DAW columns don't
    # collapse onto one shared cell.
    mixes = [aggregate_mix(atlas, key) for key in atlas.column_keys]

    # The load-bearing disclaimer — prominent, master-prompt §50.
    st.info(labels["not_ranking"])

    _header_row(bundles, labels["col_header"])
    st.divider()

    # 1 · Schema valid ------------------------------------------------------
    _text_row(
        bundles,
        labels["row_schema"],
        labels["row_schema_desc"],
        [_bool_html(b.validation.valid) for b in bundles],
        html=True,
    )

    # 2 · Domain coverage ---------------------------------------------------
    _text_row(
        bundles,
        labels["row_coverage"],
        labels["row_coverage_desc"],
        [_pct(_combined_coverage(mix)) for mix in mixes],
    )

    # 3 · Evidence mix (reuse the atlas bar) --------------------------------
    _text_row(
        bundles,
        labels["row_evidence"],
        labels["row_evidence_desc"],
        [
            atlas_page._bar_html(_mix_cell(b.snapshot.source.daw, mix))
            for b, mix in zip(bundles, mixes)
        ],
        html=True,
    )
    st.markdown(labels["evidence_legend"], unsafe_allow_html=True)

    # 4 · Provenance completeness -------------------------------------------
    _text_row(
        bundles,
        labels["row_provenance"],
        labels["row_provenance_desc"],
        [_pct(_provenance(b)) for b in bundles],
    )

    # 5 · Fixture conformance -----------------------------------------------
    _text_row(
        bundles,
        labels["row_conformance"],
        labels["row_conformance_desc"],
        [_conformance_text(b) for b in bundles],
    )

    # 6 · Compatibility ladder (the reached set, never a rank) --------------
    _text_row(
        bundles,
        labels["row_ladder"],
        labels["row_ladder_desc"],
        [_ladder_chips_html(profile, plain=plain) for profile in profiles],
        html=True,
    )
    st.caption(labels["ladder_legend"])

    # 7 · Declared read capability ------------------------------------------
    _text_row(
        bundles,
        labels["row_capabilities"],
        labels["row_capabilities_desc"],
        [_capability_text(b) for b in bundles],
    )

    # 8 · Alignment confidence ----------------------------------------------
    _text_row(
        bundles,
        labels["row_alignment"],
        labels["row_alignment_desc"],
        [_pct(_alignment_confidence(b, x04, align_rows)) for b in bundles],
    )

    st.divider()
    _downloads(bundles, x04, labels=labels, key_suffix=key_suffix)


def _provenance(bundle: SnapshotBundle) -> Optional[float]:
    """Provenance completeness for one bundle (via the metrics surface)."""
    from session_explorer.metrics import compute_provenance_completeness

    return compute_provenance_completeness(bundle.snapshot).completeness


@st.cache_data(show_spinner=False)
def _metrics_json_cached(
    bundle_keys: tuple[tuple[str, int], ...],
    x04_signature: tuple[tuple[str, int], ...],
) -> str:
    """The full metrics report as JSON, memoized on the loaded inputs.

    ``metrics_report`` rebuilds the atlas and re-runs the six-pair alignment; it
    otherwise recomputed on every rerun purely to feed a download button.
    ``x04_signature`` participates in the key only — the X04 bundles are reloaded
    inside on a miss.
    """
    bundles = [state.load_bundle_cached(dir_str) for dir_str, _ in bundle_keys]
    x04 = alignment_page.load_x04_bundles()
    report = metrics_report(bundles, x04_bundles=x04 or None)
    return report.model_dump_json(indent=2)


def _downloads(
    bundles: List[SnapshotBundle],
    x04: dict[str, SnapshotBundle],
    *,
    labels: dict[str, str],
    key_suffix: str,
) -> None:
    st.subheader(labels["downloads_header"])
    st.caption(labels["downloads_caption"])
    metrics_col, ladder_col = st.columns(2)

    with metrics_col:
        try:
            metrics_json = _metrics_json_cached(
                tuple(state.bundle_key(b) for b in bundles),
                alignment_page._x04_signature(),
            )
        except Exception as exc:  # noqa: BLE001 - a download must not kill the page
            st.caption(f"Metrics report unavailable: {exc}")
        else:
            st.download_button(
                labels["download_metrics"],
                data=metrics_json,
                file_name="metrics.json",
                mime="application/json",
                key=f"cmp_dl_metrics_{key_suffix}",
            )

    with ladder_col:
        try:
            ladder_md = render_ladder_markdown(
                [assess_bundle(bundle) for bundle in bundles]
            )
        except Exception as exc:  # noqa: BLE001 - a download must not kill the page
            st.caption(f"Ladder document unavailable: {exc}")
        else:
            st.download_button(
                labels["download_ladder"],
                data=ladder_md,
                file_name="COMPATIBILITY_LADDER.md",
                mime="text/markdown",
                key=f"cmp_dl_ladder_{key_suffix}",
            )


# ---------------------------------------------------------------------------
# Label sets — Expert (research) and Guided (plain), both from copy.py
# ---------------------------------------------------------------------------


def _expert_labels() -> dict[str, str]:
    C = wcopy.COMPARISON
    return {
        "not_ranking": C["caption_not_ranking"],
        "col_header": C["col_header"],
        "row_schema": C["row_schema"],
        "row_schema_desc": C["row_schema_desc"],
        "row_coverage": C["row_coverage"],
        "row_coverage_desc": C["row_coverage_desc"],
        "row_evidence": C["row_evidence"],
        "row_evidence_desc": C["row_evidence_desc"],
        "evidence_legend": C["evidence_legend"],
        "row_provenance": C["row_provenance"],
        "row_provenance_desc": C["row_provenance_desc"],
        "row_conformance": C["row_conformance"],
        "row_conformance_desc": C["row_conformance_desc"],
        "row_ladder": C["row_ladder"],
        "row_ladder_desc": C["row_ladder_desc"],
        "ladder_legend": C["ladder_legend"],
        "row_capabilities": C["row_capabilities"],
        "row_capabilities_desc": C["row_capabilities_desc"],
        "row_alignment": C["row_alignment"],
        "row_alignment_desc": C["row_alignment_desc"],
        "downloads_header": C["downloads_header"],
        "downloads_caption": C["downloads_caption"],
        "download_metrics": C["download_metrics"],
        "download_ladder": C["download_ladder"],
    }


def _guided_labels() -> dict[str, str]:
    C = wcopy.COMPARISON
    return {
        "not_ranking": C["caption_not_ranking"],
        "col_header": C["guided_col_header"],
        "row_schema": C["grow_schema"],
        "row_schema_desc": C["grow_schema_desc"],
        "row_coverage": C["grow_coverage"],
        "row_coverage_desc": C["grow_coverage_desc"],
        "row_evidence": C["grow_evidence"],
        "row_evidence_desc": C["grow_evidence_desc"],
        "evidence_legend": C["evidence_legend"],
        "row_provenance": C["grow_provenance"],
        "row_provenance_desc": C["grow_provenance_desc"],
        "row_conformance": C["grow_conformance"],
        "row_conformance_desc": C["grow_conformance_desc"],
        "row_ladder": C["grow_ladder"],
        "row_ladder_desc": C["grow_ladder_desc"],
        "ladder_legend": C["guided_ladder_legend"],
        "row_capabilities": C["grow_capabilities"],
        "row_capabilities_desc": C["grow_capabilities_desc"],
        "row_alignment": C["grow_alignment"],
        "row_alignment_desc": C["grow_alignment_desc"],
        "downloads_header": C["guided_downloads_header"],
        "downloads_caption": C["guided_downloads_caption"],
        "download_metrics": C["download_metrics"],
        "download_ladder": C["download_ladder"],
    }


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def render(bundles: List[SnapshotBundle]) -> None:
    """Expert 'Adapter comparison' tab: per-DAW profiles, side by side."""
    st.header(wcopy.COMPARISON["header"])
    st.markdown(wcopy.COMPARISON["intro"])

    if not bundles:
        st.info("Select at least one bundle in the sidebar.")
        return

    _dashboard(bundles, labels=_expert_labels(), plain=False, key_suffix="expert")


def render_guided(bundles: List[SnapshotBundle]) -> None:
    """Guided 'How the DAWs compare' tab: the same grid in plain language.

    Reuses the exact ``_dashboard`` body (same atlas, ladder, metrics, and
    alignment computation) with plain-language labels — so Guided and Expert
    can never drift, only the words differ.
    """
    st.header(wcopy.COMPARISON["guided_header"])
    st.markdown(wcopy.COMPARISON["guided_intro"])

    if not bundles:
        st.info(wcopy.COPY["no_bundles"])
        return

    _dashboard(bundles, labels=_guided_labels(), plain=True, key_suffix="guided")
