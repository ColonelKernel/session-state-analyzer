"""Computing a :class:`MetricsReport` from loaded bundles (master-prompt §67).

Every number here is derived from an existing analyzer surface, never
recomputed independently:

- **Coverage / evidence** come from the Observability Atlas
  (:func:`session_explorer.atlas.build_atlas`) and the shared
  :func:`session_explorer.atlas.aggregate_mix` — the same arithmetic the
  guided overview bars draw.
- **Provenance completeness** walks the snapshot's ``prov`` / ``prov_ref``
  references against its deduplicated ``provenance[]`` store.
- **Native preservation** reads the atlas Native-Features cell plus the
  ``extensions`` payload and the ``native.json`` sidecar.
- **The ladder reached-set** comes from ``compat.ladder.assess_bundle`` when
  that module is importable; until it lands the field degrades honestly to an
  empty list (see :data:`LADDER_AVAILABLE`).
- **Alignment** reuses the X04 page's ``pair_rows`` so the metric and the
  workbench table cannot disagree.
"""

from __future__ import annotations

from typing import Any, Optional

from session_explorer.atlas import Atlas, build_atlas
from session_explorer.atlas.coverage import aggregate_mix
from session_explorer.loaders import SnapshotBundle

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

# The compatibility ladder (Phase 3) is built by a parallel effort. Import it
# defensively: if it is not yet importable, the ladder reached-set degrades to
# an empty list rather than breaking the whole report — and auto-populates the
# moment the module lands. LADDER_AVAILABLE lets callers/tests report which.
try:  # pragma: no cover - availability depends on parallel work
    from session_explorer.compat.ladder import assess_bundle as _assess_bundle

    LADDER_AVAILABLE = True
except Exception:  # noqa: BLE001 - any import failure means "not ready yet"
    _assess_bundle = None
    LADDER_AVAILABLE = False


_MIX_RATIO_KEYS = ("observed", "inferred", "annotated", "hidden", "absent")


# --- per-DAW pieces -------------------------------------------------------


def compute_domain_metrics(atlas: Atlas, daw: str) -> list[DomainMetric]:
    """One :class:`DomainMetric` per atlas domain, for ``daw``."""
    metrics: list[DomainMetric] = []
    for domain_name in atlas.domains:
        cell = atlas.cell(domain_name, daw)
        metrics.append(
            DomainMetric(
                domain=domain_name,
                applicable=cell.measured.applicable,
                direct_observability=cell.direct_observability,
                combined_coverage=cell.combined_coverage,
                hidden_ratio=cell.hidden_ratio,
                status=cell.status,
            )
        )
    return metrics


def compute_evidence_ratios(atlas: Atlas, daw: str) -> EvidenceRatios:
    """The whole-session evidence mix for ``daw`` as bounded fractions.

    Reads the shared :func:`aggregate_mix` counts and normalizes each bucket by
    ``applicable`` (0.0 when there is nothing applicable).
    """
    mix = aggregate_mix(atlas, daw)
    applicable = mix["applicable"]

    def ratio(key: str) -> float:
        return mix[key] / applicable if applicable > 0 else 0.0

    return EvidenceRatios(
        observed=ratio("observed"),
        inferred=ratio("inferred"),
        annotated=ratio("annotated"),
        hidden=ratio("hidden"),
        absent=ratio("absent"),
        applicable=applicable,
    )


def compute_provenance_completeness(snap: Any) -> ProvenanceCompleteness:
    """Share of a snapshot's provenance references that resolve into its store.

    Counts every ``Entity.prov`` field->id ref and every non-null
    ``Relationship.prov_ref``, and how many of each land on a real
    ``ProvenanceRecord`` id. ``completeness`` is the combined resolved share
    (1.0 vacuously when a snapshot carries no references at all).
    """
    store = {record.id for record in snap.provenance}

    entity_field_refs = 0
    resolvable = 0
    for entity in snap.entities:
        for _field, prov_id in entity.prov.items():
            entity_field_refs += 1
            if prov_id in store:
                resolvable += 1

    rel_prov_refs = 0
    rel_resolvable = 0
    for rel in snap.relationships:
        if rel.prov_ref is not None:
            rel_prov_refs += 1
            if rel.prov_ref in store:
                rel_resolvable += 1

    total = entity_field_refs + rel_prov_refs
    resolved = resolvable + rel_resolvable
    completeness = resolved / total if total > 0 else 1.0

    return ProvenanceCompleteness(
        entity_field_refs=entity_field_refs,
        resolvable=resolvable,
        rel_prov_refs=rel_prov_refs,
        rel_resolvable=rel_resolvable,
        completeness=completeness,
    )


def compute_native_preservation(bundle: SnapshotBundle) -> NativePreservation:
    """Whether DAW-native richness survived alongside the canonical core.

    Standalone (builds a one-bundle atlas) so it can be called on its own; the
    Native-Features observed count is the atlas measurement of
    ``extensions[daw]`` key presence.
    """
    snap = bundle.snapshot
    daw = snap.source.daw
    atlas = build_atlas([bundle])
    observed = atlas.cell("Native Features", daw).measured.observed
    extension_keys = sum(len(payload) for payload in snap.extensions.values())
    native_json_present = (bundle.dir / "native.json").is_file()
    return NativePreservation(
        native_features_observed=observed,
        extension_keys=extension_keys,
        native_json_present=native_json_present,
    )


def _ladder_reached(bundle: SnapshotBundle, context: Any = None) -> list[int]:
    """The compatibility-ladder reached-set, or ``[]`` when unavailable.

    Defensive against the ladder's exact profile shape (it is built elsewhere):
    tries the common reached-set accessors, then a per-level scan, and falls
    back to ``[]`` rather than guessing wrong.
    """
    if _assess_bundle is None:
        return []
    try:
        try:
            profile = _assess_bundle(bundle, context)
        except TypeError:
            profile = _assess_bundle(bundle)
    except Exception:  # noqa: BLE001 - never let the ladder break the report
        return []

    for attr in ("reached", "reached_set", "reached_levels", "levels_reached"):
        value = getattr(profile, attr, None)
        if value is not None:
            try:
                return sorted({int(level) for level in value})
            except (TypeError, ValueError):
                continue

    levels = getattr(profile, "levels", None)
    if levels is not None:
        reached: set[int] = set()
        for assessment in levels:
            if getattr(assessment, "reached", False):
                number = getattr(
                    assessment, "level", getattr(assessment, "index", None)
                )
                if number is not None:
                    reached.add(int(number))
        return sorted(reached)

    return []


# --- assembly -------------------------------------------------------------


def compute_bundle_metrics(
    bundle: SnapshotBundle, atlas: Atlas, context: Any = None
) -> BundleMetrics:
    """Assemble one bundle's full :class:`BundleMetrics` from a built atlas."""
    snap = bundle.snapshot
    daw = snap.source.daw
    warnings = list(bundle.validation.warnings) + list(bundle.load_warnings)
    return BundleMetrics(
        daw=daw,
        bundle=bundle.dir.name,
        schema_valid=bundle.validation.valid,
        warnings=warnings,
        native_preservation=compute_native_preservation(bundle),
        ladder_reached=_ladder_reached(bundle, context),
        domains=compute_domain_metrics(atlas, daw),
        evidence_ratios=compute_evidence_ratios(atlas, daw),
        provenance=compute_provenance_completeness(snap),
    )


def compute_alignment_metrics(
    x04_bundles: Optional[dict[str, SnapshotBundle]],
    concepts: tuple[str, ...] = ("effect_return",),
) -> list[AlignmentMetric]:
    """Cross-DAW alignment metrics over the X04 bundles (six DAW pairs).

    Reuses the X04 page's ``pair_rows`` verbatim so the metric and the
    workbench alignment table can never drift. The import is lazy: metrics that
    do not ask for alignment never pull in the workbench (Streamlit) layer.
    """
    if not x04_bundles:
        return []
    from session_explorer.workbench.pages import alignment as alignment_page

    rows = alignment_page.pair_rows(x04_bundles, concepts)
    return [
        AlignmentMetric(
            pair=row["pair"],
            concept=row["concept"],
            status=row["status"],
            confidence=row["confidence"],
        )
        for row in rows
    ]


def _aggregate(
    atlas: Atlas, bundle_metrics: list[BundleMetrics], alignment: list[AlignmentMetric]
) -> AggregateMetrics:
    totals = {key: 0 for key in ("observed", "inferred", "annotated", "hidden", "absent", "applicable")}
    for daw in atlas.daws:
        mix = aggregate_mix(atlas, daw)
        for key in totals:
            totals[key] += mix[key]

    confidences = [a.confidence for a in alignment if a.confidence is not None]
    mean_conf = sum(confidences) / len(confidences) if confidences else None

    return AggregateMetrics(
        bundle_count=len(bundle_metrics),
        alignment_pairs=len(alignment),
        mean_alignment_confidence=mean_conf,
        **totals,
    )


def metrics_report(
    bundles: list[SnapshotBundle],
    x04_bundles: Optional[dict[str, SnapshotBundle]] = None,
    experiment_ctx: Optional[dict[str, Any]] = None,
) -> MetricsReport:
    """Build the full :class:`MetricsReport` over ``bundles``.

    ``x04_bundles`` (when given) drive the cross-DAW alignment section;
    ``experiment_ctx`` may carry a ``generated_from`` label and is otherwise
    passed to the ladder as its assessment context.
    """
    atlas = build_atlas(bundles)
    context = experiment_ctx if isinstance(experiment_ctx, dict) else None
    bundle_metrics = [compute_bundle_metrics(b, atlas, context) for b in bundles]
    alignment = compute_alignment_metrics(x04_bundles)
    aggregate = _aggregate(atlas, bundle_metrics, alignment)

    generated_from = None
    if isinstance(experiment_ctx, dict):
        generated_from = experiment_ctx.get("generated_from")
    if not generated_from:
        generated_from = ", ".join(bm.bundle for bm in bundle_metrics) or "(no bundles)"

    return MetricsReport(
        generated_from=generated_from,
        bundles=bundle_metrics,
        alignment=alignment,
        aggregate=aggregate,
    )
