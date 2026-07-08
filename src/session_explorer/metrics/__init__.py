"""Measurable metrics over loaded bundles (master-prompt §67).

``metrics_report(bundles, x04_bundles, ctx)`` produces a :class:`MetricsReport`:
per-domain coverage, whole-session evidence ratios (via the shared
:func:`session_explorer.atlas.aggregate_mix`), provenance completeness,
native-feature preservation, the compatibility-ladder reached-set (when
``compat.ladder`` is importable), and cross-DAW alignment confidences. Every
number is read from an existing analyzer surface, so the report cannot disagree
with the workbench that shows the same figures. :func:`write_metrics` serializes
a report to ``metrics.json`` for the dataset export and a workbench download.
"""

from __future__ import annotations

from session_explorer.atlas.coverage import aggregate_mix

from .compute import (
    LADDER_AVAILABLE,
    compute_alignment_metrics,
    compute_bundle_metrics,
    compute_domain_metrics,
    compute_evidence_ratios,
    compute_native_preservation,
    compute_provenance_completeness,
    metrics_report,
)
from .export import write_metrics
from .models import (
    AggregateMetrics,
    AlignmentMetric,
    BundleMetrics,
    DomainMetric,
    EvidenceRatios,
    MetricsReport,
    NativePreservation,
    ProvenanceCompleteness,
)

__all__ = [
    "LADDER_AVAILABLE",
    "aggregate_mix",
    "metrics_report",
    "write_metrics",
    "compute_alignment_metrics",
    "compute_bundle_metrics",
    "compute_domain_metrics",
    "compute_evidence_ratios",
    "compute_native_preservation",
    "compute_provenance_completeness",
    "MetricsReport",
    "BundleMetrics",
    "AggregateMetrics",
    "DomainMetric",
    "EvidenceRatios",
    "ProvenanceCompleteness",
    "NativePreservation",
    "AlignmentMetric",
]
