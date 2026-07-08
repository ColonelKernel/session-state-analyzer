"""The metrics report schema (master-prompt §67).

A :class:`MetricsReport` is the measurable evidence-and-coverage profile of a
set of loaded bundles: per-domain observability, whole-session evidence ratios,
provenance completeness, native-feature preservation, the compatibility-ladder
reached-set, and cross-DAW alignment confidences. Every model forbids unknown
fields, so a report either matches this schema or fails loudly — the same
contract discipline the snapshot itself follows.

Nothing here computes anything: these are the pure data shapes. The arithmetic
lives in :mod:`session_explorer.metrics.compute`, which reuses the atlas, the
provenance store, and the alignment engine so the metrics can never disagree
with the workbench that displays the same numbers.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class _MetricsModel(BaseModel):
    """Base for every metrics model: unknown fields are a schema violation."""

    model_config = ConfigDict(extra="forbid")


class DomainMetric(_MetricsModel):
    """One atlas domain's observability, for one DAW.

    The three ratios mirror :class:`~session_explorer.atlas.AtlasCell`
    exactly (``None`` when the domain has no measurable scope in this
    snapshot); ``status`` is the cell's headline profile.
    """

    domain: str
    applicable: int
    direct_observability: Optional[float] = None
    combined_coverage: Optional[float] = None
    hidden_ratio: Optional[float] = None
    status: str


class EvidenceRatios(_MetricsModel):
    """The whole-session epistemic mix for one DAW, as fractions.

    ``observed`` / ``inferred`` / ``annotated`` / ``hidden`` / ``absent`` are
    each that bucket's share of ``applicable`` (so every one is in ``[0, 1]``);
    ``applicable`` is the integer denominator that produced them. Derived from
    the shared :func:`session_explorer.atlas.aggregate_mix` — the same counts
    the guided overview bars draw.
    """

    observed: float
    inferred: float
    annotated: float
    hidden: float
    absent: float
    applicable: int


class ProvenanceCompleteness(_MetricsModel):
    """How much of a snapshot's provenance actually resolves.

    Every value in the snapshot points at a ``ProvenanceRecord`` id, through
    ``Entity.prov`` (field -> id, ``"*"`` for the entity default) or
    ``Relationship.prov_ref``. ``completeness`` is the share of those refs that
    resolve into the deduplicated ``provenance[]`` store — a dangling ref is a
    broken evidence chain, and this measures how honest the chain is.
    """

    entity_field_refs: int
    resolvable: int
    rel_prov_refs: int
    rel_resolvable: int
    completeness: float


class NativePreservation(_MetricsModel):
    """Whether the DAW-native richness survived alongside the canonical core.

    ``native_features_observed`` is the atlas Native-Features cell's observed
    count; ``extension_keys`` counts the top-level keys under
    ``snapshot.extensions[*]``; ``native_json_present`` records whether the
    verbatim ``native.json`` sidecar rode along in the bundle.
    """

    native_features_observed: int
    extension_keys: int
    native_json_present: bool


class AlignmentMetric(_MetricsModel):
    """One cross-DAW alignment claim, reduced to its measurable head.

    ``pair`` is the directed DAW pair ("ableton → reaper"), ``concept`` the
    registry concept both sides implement, ``status`` the engine verdict, and
    ``confidence`` its composite score (``None`` only when no candidate existed).
    """

    pair: str
    concept: str
    status: str
    confidence: Optional[float] = None


class BundleMetrics(_MetricsModel):
    """The full measured profile of one loaded bundle."""

    daw: str
    bundle: str
    schema_valid: bool
    warnings: list[str]
    native_preservation: NativePreservation
    ladder_reached: list[int]
    domains: list[DomainMetric]
    evidence_ratios: EvidenceRatios
    provenance: ProvenanceCompleteness


class AggregateMetrics(_MetricsModel):
    """Roll-up across every bundle in the report.

    The six evidence buckets are the *sum* of each bundle's whole-session
    counts (not an average) — the report-wide tally of what was observed,
    inferred, annotated, hidden, or honestly absent. ``alignment_pairs`` and
    ``mean_alignment_confidence`` summarize the cross-DAW alignment rows.
    """

    bundle_count: int
    observed: int
    inferred: int
    annotated: int
    hidden: int
    absent: int
    applicable: int
    alignment_pairs: int
    mean_alignment_confidence: Optional[float] = None


class MetricsReport(_MetricsModel):
    """The top-level metrics report over a set of bundles."""

    generated_from: str
    bundles: list[BundleMetrics]
    alignment: list[AlignmentMetric]
    aggregate: AggregateMetrics
