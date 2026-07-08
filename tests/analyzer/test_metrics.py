"""The metrics report (master-prompt §67) over the four real fixture bundles.

Asserts the report's schema round-trips, its ratios are bounded, its aggregate
is the honest sum of the per-bundle evidence buckets, and specific anchored
values verified against the frozen fixtures (reaper Structure fully observed;
cubase Processing partly hidden; provenance fully resolvable). Also checks the
cross-DAW alignment section carries the six X04 pairs and that the
compatibility-ladder reached-set is populated when ``compat.ladder`` is
importable (and honestly empty when it is not).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from session_explorer.atlas import build_atlas
from session_explorer.atlas.coverage import aggregate_mix
from session_explorer.loaders.bundle import load_bundle
from session_explorer.metrics import (
    LADDER_AVAILABLE,
    MetricsReport,
    compute_provenance_completeness,
    metrics_report,
    write_metrics,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "adapters"
DAWS = ("reaper", "ableton", "cubase", "logic")

# The source.daw id each fixture reports (bundle metrics are keyed by this).
DAW_ID = {
    "reaper": "reaper",
    "ableton": "ableton_live",
    "cubase": "cubase",
    "logic": "logic_pro",
}

_EVIDENCE_KEYS = ("observed", "inferred", "annotated", "hidden", "absent", "applicable")
_RATIO_KEYS = ("observed", "inferred", "annotated", "hidden", "absent")


def _bundle(daw: str):
    path = FIXTURES / daw
    if not (path / "canonical.snapshot.json").exists():
        pytest.skip(f"no frozen bundle for {daw}")
    return load_bundle(path)


@pytest.fixture(scope="module")
def bundles():
    return [_bundle(daw) for daw in DAWS]


@pytest.fixture(scope="module")
def x04_bundles():
    from session_explorer.workbench.pages import alignment as alignment_page

    return alignment_page.load_x04_bundles()


@pytest.fixture(scope="module")
def report(bundles, x04_bundles) -> MetricsReport:
    return metrics_report(
        bundles,
        x04_bundles=x04_bundles,
        experiment_ctx={"generated_from": "fixtures/adapters + X04_effect_return"},
    )


def _bundle_metric(report: MetricsReport, daw: str):
    return next(b for b in report.bundles if b.daw == DAW_ID[daw])


def _domain(bundle_metric, domain_name: str):
    return next(d for d in bundle_metric.domains if d.domain == domain_name)


# --- schema ---------------------------------------------------------------


def test_report_round_trips(report):
    """model_validate(model_dump()) reproduces the report exactly."""
    restored = MetricsReport.model_validate(report.model_dump())
    assert restored == report


def test_report_covers_the_four_bundles(report):
    assert report.aggregate.bundle_count == 4
    assert {b.daw for b in report.bundles} == set(DAW_ID.values())
    assert report.generated_from == "fixtures/adapters + X04_effect_return"


def test_every_bundle_has_ten_domain_metrics(report):
    for bundle_metric in report.bundles:
        assert len(bundle_metric.domains) == 10
        assert bundle_metric.schema_valid is True


# --- anchored measured values (verified against the fixtures) -------------


def test_reaper_structure_fully_observed(report):
    """1 PROJECT + 9 TRACK, all OBSERVED -> direct_observability == 1.0."""
    structure = _domain(_bundle_metric(report, "reaper"), "Structure")
    assert structure.direct_observability == 1.0
    assert structure.applicable == 10
    assert structure.status == "FULLY_OBSERVED"


def test_cubase_processing_partly_hidden(report):
    """Cubase inserts are INACCESSIBLE -> Processing hidden_ratio > 0."""
    processing = _domain(_bundle_metric(report, "cubase"), "Processing")
    assert processing.hidden_ratio is not None
    assert processing.hidden_ratio > 0


def test_provenance_completeness_bounded_and_full(report):
    """Every fixture's provenance references resolve into its store."""
    for bundle_metric in report.bundles:
        completeness = bundle_metric.provenance.completeness
        assert 0.0 <= completeness <= 1.0
        # The four frozen fixtures carry no dangling references.
        assert completeness == 1.0
        assert bundle_metric.provenance.entity_field_refs > 0


def test_provenance_completeness_detects_a_dangling_ref(bundles):
    """A ref that points nowhere drops completeness below 1.0 (sanity check)."""
    snap = bundles[0].snapshot.model_copy(deep=True)
    snap.entities[0].prov["__broken__"] = "prov:does-not-exist"
    prov = compute_provenance_completeness(snap)
    assert prov.completeness < 1.0
    assert prov.resolvable < prov.entity_field_refs


# --- bounded ratios -------------------------------------------------------


def test_evidence_ratios_bounded(report):
    for bundle_metric in report.bundles:
        ratios = bundle_metric.evidence_ratios
        for key in _RATIO_KEYS:
            value = getattr(ratios, key)
            assert 0.0 <= value <= 1.0, (bundle_metric.daw, key, value)
        assert ratios.applicable > 0


def test_domain_ratios_bounded_or_none(report):
    for bundle_metric in report.bundles:
        for domain in bundle_metric.domains:
            for ratio in (
                domain.direct_observability,
                domain.combined_coverage,
                domain.hidden_ratio,
            ):
                assert ratio is None or 0.0 <= ratio <= 1.0


# --- aggregate is the honest sum of the bundle buckets --------------------


def test_aggregate_is_sum_of_bundle_buckets(report, bundles):
    """AggregateMetrics counts == sum over DAWs of aggregate_mix buckets."""
    atlas = build_atlas(bundles)
    expected = {key: 0 for key in _EVIDENCE_KEYS}
    for daw in atlas.daws:
        mix = aggregate_mix(atlas, daw)
        for key in _EVIDENCE_KEYS:
            expected[key] += mix[key]

    aggregate = report.aggregate
    for key in _EVIDENCE_KEYS:
        assert getattr(aggregate, key) == expected[key], key

    # Verified totals for the current frozen fixtures.
    assert aggregate.observed == 195
    assert aggregate.applicable == 242
    assert aggregate.hidden == 22


# --- cross-DAW alignment --------------------------------------------------


def test_alignment_metric_for_the_six_x04_pairs(report):
    """The six directed DAW pairs each carry one effect_return alignment row."""
    alignment = report.alignment
    assert len(alignment) == 6
    assert report.aggregate.alignment_pairs == 6
    pairs = {a.pair for a in alignment}
    assert pairs == {
        "ableton → reaper",
        "ableton → cubase",
        "ableton → logic",
        "reaper → cubase",
        "reaper → logic",
        "cubase → logic",
    }
    for row in alignment:
        assert row.concept == "effect_return"
        assert row.status in ("PROBABLE", "POSSIBLE", "CONFIRMED", "CONFLICTING")
        assert row.confidence is None or 0.0 <= row.confidence <= 1.0


def test_alignment_empty_without_x04(bundles):
    """No X04 bundles -> no alignment rows (and the report still builds)."""
    report = metrics_report(bundles, x04_bundles=None)
    assert report.alignment == []
    assert report.aggregate.alignment_pairs == 0
    assert report.aggregate.mean_alignment_confidence is None


# --- native preservation --------------------------------------------------


def test_native_preservation(report):
    """Every fixture ships native.json and a non-empty extensions payload,
    and the atlas Native-Features count equals the extension key count."""
    for bundle_metric in report.bundles:
        native = bundle_metric.native_preservation
        assert native.native_json_present is True
        assert native.extension_keys > 0
        assert native.native_features_observed == native.extension_keys


# --- compatibility ladder (degrades honestly) -----------------------------


def test_ladder_reached_populated_or_empty(report):
    """When compat.ladder is importable the reached-set is populated (and
    always contains L0=validates); when it is not, it degrades to []."""
    for bundle_metric in report.bundles:
        reached = bundle_metric.ladder_reached
        assert isinstance(reached, list)
        assert all(isinstance(level, int) for level in reached)
        # Sorted and de-duplicated.
        assert reached == sorted(set(reached))
        if LADDER_AVAILABLE:
            # All four fixtures validate, so L0 (and L1: track + channel|proc)
            # are always demonstrated.
            assert 0 in reached
            assert 1 in reached
        else:
            assert reached == []


# --- export ---------------------------------------------------------------


def test_write_metrics_round_trips(report, tmp_path):
    path = write_metrics(report, tmp_path)
    assert path.is_file()
    restored = MetricsReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert restored == report
