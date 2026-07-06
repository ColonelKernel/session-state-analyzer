"""Measured and declared observability, per atlas domain, per DAW.

Two independent readings sit behind every atlas cell, and the whole point of
the atlas is to keep them apart:

- **Measured** (:class:`MeasuredCoverage`) — what *this* snapshot actually
  carries. Computed by walking the entities in a domain's scope, resolving
  each entity's provenance references into the deduplicated ``provenance[]``
  store (the store is deduplicated, so evidence is counted by *resolving refs*,
  never by counting the store), and reading its availability ledger.
- **Declared** (:class:`DeclaredCoverage`) — what the adapter's capability
  manifest *claims* it can read for this domain, independent of any one
  capture. "We did not see automation here" and "this adapter cannot see
  automation" are different facts and get different dataclasses.

An :class:`AtlasCell` fuses the two into ratios and a headline status; an
:class:`Atlas` is the full domain x DAW grid.

Evidence buckets follow the contract's four ``Evidence`` values plus the
availability ledger:

- OBSERVED / INFERRED / ANNOTATED — the value entered the snapshot.
- HIDDEN evidence *and* INACCESSIBLE availability both mean "known to exist,
  not recoverable": both land in the ``hidden`` bucket.
- UNSUPPORTED / NOT_PRESENT (or a support-NONE availability) land in
  ``unsupported`` / ``not_present``; UNKNOWN lands in ``unknown``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from canonical_snapshot import CanonicalDAWSnapshot
from canonical_snapshot.capabilities import CapabilityManifest

from .domains import ATLAS_DOMAINS, AtlasDomain, atlas_domains, get_domain

# One (entity_id, field) reference into a bucket. field == "*" is the entity's
# baseline provenance; a real field name is a per-field provenance or an
# availability entry.
Ref = tuple[str, str]


@dataclass
class MeasuredCoverage:
    """What one snapshot actually carries for one domain.

    The integer counts are the atlas math; the parallel ``*_refs`` lists carry
    the (entity_id, field) pairs behind each count for click-through drill-down.
    ``applicable`` is the size of the domain's scope in this snapshot (in-scope
    entities plus their availability-flagged fields), the denominator for every
    ratio.
    """

    applicable: int = 0
    observed: int = 0
    inferred: int = 0
    annotated: int = 0
    hidden: int = 0
    unsupported: int = 0
    not_present: int = 0
    unknown: int = 0

    applicable_refs: list[Ref] = field(default_factory=list)
    observed_refs: list[Ref] = field(default_factory=list)
    inferred_refs: list[Ref] = field(default_factory=list)
    annotated_refs: list[Ref] = field(default_factory=list)
    hidden_refs: list[Ref] = field(default_factory=list)
    unsupported_refs: list[Ref] = field(default_factory=list)
    not_present_refs: list[Ref] = field(default_factory=list)
    unknown_refs: list[Ref] = field(default_factory=list)

    # Finer-grained, per-field provenance escalations for drill-down only. A
    # TRACK observed as an entity may still carry an INFERRED ``semantic_roles``
    # or a HIDDEN ``plugin_chain``: those live here so the drill-down shows them
    # without letting a single entity count as more than one applicable item
    # (which would push combined_coverage above 1.0). Keyed by bucket name.
    field_refs: dict[str, list[Ref]] = field(default_factory=dict)


@dataclass
class DeclaredFieldCapability:
    """One flattened capability row: domain field + its declared pathway."""

    capability_domain: str
    field_name: str
    support: str
    capture_method: Optional[str]
    source_stability: Optional[str]
    validation_status: str
    applicability: str


@dataclass
class DeclaredCoverage:
    """What the adapter's manifest declares it can *read* for one domain.

    Aggregated over every capability read-section field whose capability domain
    maps into this atlas domain (the union across dialect vocabularies).
    """

    field_count: int = 0
    support: dict[str, int] = field(default_factory=dict)
    source_stability: dict[str, int] = field(default_factory=dict)
    validation: dict[str, int] = field(default_factory=dict)
    fields: list[DeclaredFieldCapability] = field(default_factory=list)


# --- measured -------------------------------------------------------------

# Availability status -> the measured bucket it feeds. INACCESSIBLE is
# known-but-hidden (same as HIDDEN evidence); the rest are honest absences.
_AVAILABILITY_BUCKET = {
    "INACCESSIBLE": "hidden",
    "UNSUPPORTED": "unsupported",
    "NOT_PRESENT": "not_present",
    "UNKNOWN": "unknown",
    "NOT_APPLICABLE": "unsupported",
    "PARSE_ERROR": "hidden",
    "REDACTED": "hidden",
}

# Evidence value -> measured bucket.
_EVIDENCE_BUCKET = {
    "OBSERVED": "observed",
    "INFERRED": "inferred",
    "ANNOTATED": "annotated",
    "HIDDEN": "hidden",
}


def _add(cov: MeasuredCoverage, bucket: str, ref: Ref) -> None:
    setattr(cov, bucket, getattr(cov, bucket) + 1)
    getattr(cov, f"{bucket}_refs").append(ref)


def _native_features_coverage(snapshot: CanonicalDAWSnapshot) -> MeasuredCoverage:
    """Native Features: measured from ``extensions[daw]`` top-level key presence.

    Each top-level extension key is one applicable, observed feature payload —
    the DAW-specific richness that rode alongside the canonical core.
    """
    cov = MeasuredCoverage()
    daw = snapshot.source.daw
    payload = snapshot.extensions.get(daw, {})
    for key in payload:
        ref = (f"extensions:{daw}", key)
        cov.applicable += 1
        cov.applicable_refs.append(ref)
        _add(cov, "observed", ref)
    return cov


def measure_domain(
    snapshot: CanonicalDAWSnapshot, domain: AtlasDomain
) -> MeasuredCoverage:
    """Measure one snapshot's actual coverage for one atlas domain.

    Walks entities whose ``entity_type`` is in ``domain.entity_types``, buckets
    each by its resolved ``"*"`` provenance evidence, folds in per-field
    provenance and the availability ledger, and returns the counts + drill-down
    refs. Native Features is measured from extension payload presence instead.
    """
    if domain.name == "Native Features":
        return _native_features_coverage(snapshot)

    cov = MeasuredCoverage()
    store = {p.id: p for p in snapshot.provenance}
    # Availability fields already counted, so a field flagged both HIDDEN in
    # provenance and INACCESSIBLE in availability is one applicable thing.
    avail_seen: set[Ref] = set()

    for entity in snapshot.entities:
        if entity.entity_type not in domain.entity_types:
            continue

        # One entity == one applicable item, bucketed by its "*" evidence. This
        # keeps every ratio in [0, 1]: the primary buckets partition applicable.
        entity_ref: Ref = (entity.id, "*")
        cov.applicable += 1
        cov.applicable_refs.append(entity_ref)
        star_ref = entity.prov.get("*")
        star_record = store.get(star_ref) if star_ref else None
        if star_record is not None:
            bucket = _EVIDENCE_BUCKET.get(star_record.evidence)
            if bucket:
                _add(cov, bucket, entity_ref)

        # Per-field provenance escalations feed drill-down only, never the
        # applicable denominator (see MeasuredCoverage.field_refs).
        for fname, ref in entity.prov.items():
            if fname == "*":
                continue
            record = store.get(ref)
            if record is None:
                continue
            bucket = _EVIDENCE_BUCKET.get(record.evidence)
            if bucket:
                cov.field_refs.setdefault(bucket, []).append((entity.id, fname))

        # Availability ledger: each flagged field is an applicable-but-absent
        # item, counted once and bucketed by its honest reason.
        for fname, status in entity.availability.items():
            field_ref: Ref = (entity.id, fname)
            bucket = _AVAILABILITY_BUCKET.get(status)
            if bucket is None or field_ref in avail_seen:
                continue
            avail_seen.add(field_ref)
            cov.applicable += 1
            cov.applicable_refs.append(field_ref)
            _add(cov, bucket, field_ref)

    return cov


# --- declared -------------------------------------------------------------


def _bump(counter: dict[str, int], key: Optional[str]) -> None:
    if key is None:
        return
    counter[key] = counter.get(key, 0) + 1


def declared_domain(
    manifest: Optional[CapabilityManifest], domain: AtlasDomain
) -> Optional[DeclaredCoverage]:
    """Declared read-capability for one atlas domain, or ``None``.

    Returns ``None`` when the adapter shipped no manifest, or when no read
    capability domain maps into this atlas domain — the honest "this adapter
    makes no claim here". Aggregates support / source-stability / validation
    distributions across every mapped field.
    """
    if manifest is None or not domain.capability_domains:
        return None

    declared = DeclaredCoverage()
    for cap_domain_name in sorted(domain.capability_domains):
        cap_domain = manifest.read.get(cap_domain_name)
        if cap_domain is None:
            continue
        for field_name, cap in cap_domain.fields.items():
            declared.field_count += 1
            _bump(declared.support, cap.support)
            _bump(declared.source_stability, cap.source_stability)
            _bump(declared.validation, cap.validation_status)
            declared.fields.append(
                DeclaredFieldCapability(
                    capability_domain=cap_domain_name,
                    field_name=field_name,
                    support=cap.support,
                    capture_method=cap.capture_method,
                    source_stability=cap.source_stability,
                    validation_status=cap.validation_status,
                    applicability=cap.applicability,
                )
            )

    if declared.field_count == 0:
        return None
    return declared


# --- cell + atlas ---------------------------------------------------------


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


@dataclass
class AtlasCell:
    """One domain x DAW cell: measured + declared, fused into ratios and status."""

    domain_name: str
    daw: str
    measured: MeasuredCoverage
    declared: Optional[DeclaredCoverage]

    @property
    def applicable_present(self) -> bool:
        """Whether this domain has any measurable scope in this snapshot."""
        return self.measured.applicable > 0

    @property
    def direct_observability(self) -> Optional[float]:
        """Share of applicable items directly OBSERVED (None when no scope)."""
        return _ratio(self.measured.observed, self.measured.applicable)

    @property
    def combined_coverage(self) -> Optional[float]:
        """Share observed OR inferred OR annotated — recovered by any means."""
        m = self.measured
        return _ratio(m.observed + m.inferred + m.annotated, m.applicable)

    @property
    def hidden_ratio(self) -> Optional[float]:
        """Share of applicable items known-but-hidden (HIDDEN / INACCESSIBLE)."""
        return _ratio(self.measured.hidden, self.measured.applicable)

    @property
    def status(self) -> str:
        """A short headline profile for the cell.

        NOT_APPLICABLE when there is nothing to measure and nothing declared —
        an honest empty. Otherwise a coarse profile from the dominant reading.
        """
        if not self.applicable_present and not self.declared:
            return "NOT_APPLICABLE"
        if not self.applicable_present:
            # Declared but unmeasured in this capture.
            return "DECLARED_ONLY"
        direct = self.direct_observability or 0.0
        combined = self.combined_coverage or 0.0
        hidden = self.hidden_ratio or 0.0
        if hidden >= 0.5:
            return "MOSTLY_HIDDEN"
        if direct >= 0.999:
            return "FULLY_OBSERVED"
        if combined >= 0.999:
            return "FULLY_RECOVERED"
        if direct >= 0.5:
            return "MOSTLY_OBSERVED"
        if combined >= 0.5:
            return "MOSTLY_INFERRED"
        return "PARTIAL"


@dataclass
class Atlas:
    """The full observability atlas: ten domains x N DAWs of cells."""

    domains: list[str]
    daws: list[str]
    cells: dict[tuple[str, str], AtlasCell]

    def cell(self, domain_name: str, daw: str) -> AtlasCell:
        """The cell at (domain, daw) (KeyError if not built)."""
        return self.cells[(domain_name, daw)]


def _bundle_daw(bundle) -> str:
    return bundle.snapshot.source.daw


def build_atlas(bundles: list) -> Atlas:
    """Assemble the atlas over a list of loaded ``SnapshotBundle``s.

    Rows are always the ten :data:`ATLAS_DOMAINS`; columns are the DAWs of the
    given bundles, in the order supplied. Every (domain, daw) pair gets a cell,
    including NOT_APPLICABLE ones — the grid is dense on purpose.
    """
    daws = [_bundle_daw(b) for b in bundles]
    cells: dict[tuple[str, str], AtlasCell] = {}
    for bundle in bundles:
        daw = _bundle_daw(bundle)
        snapshot = bundle.snapshot
        manifest = bundle.capabilities
        for domain in atlas_domains():
            measured = measure_domain(snapshot, domain)
            declared = declared_domain(manifest, domain)
            cells[(domain.name, daw)] = AtlasCell(
                domain_name=domain.name,
                daw=daw,
                measured=measured,
                declared=declared,
            )
    return Atlas(domains=list(ATLAS_DOMAINS), daws=daws, cells=cells)


# --- unknown-state map ----------------------------------------------------

# The categories of "not plainly known" that the map surfaces, derived from the
# availability ledger, HIDDEN evidence, and recorded failures.
UNKNOWN_CATEGORIES = (
    "INACCESSIBLE",
    "UNSUPPORTED",
    "PARSE_ERROR",
    "HIDDEN",
    "UNKNOWN",
    "CONFLICTING",
)


def unknown_state_map(snapshot: CanonicalDAWSnapshot) -> dict[str, list[Ref]]:
    """Categorize everything this snapshot admits it does not plainly know.

    Draws from three honest sources: the per-entity availability ledger
    (INACCESSIBLE / UNSUPPORTED / NOT_APPLICABLE / PARSE_ERROR / UNKNOWN),
    fields carrying HIDDEN provenance evidence, and recorded acquisition
    ``failures`` (surfaced as CONFLICTING when a stage reports a conflict, else
    PARSE_ERROR). Returns category -> list of (entity_id / stage, field) refs.
    """
    result: dict[str, list[Ref]] = {cat: [] for cat in UNKNOWN_CATEGORIES}
    store = {p.id: p for p in snapshot.provenance}

    for entity in snapshot.entities:
        for fname, status in entity.availability.items():
            if status == "INACCESSIBLE":
                result["INACCESSIBLE"].append((entity.id, fname))
            elif status in ("UNSUPPORTED", "NOT_APPLICABLE"):
                result["UNSUPPORTED"].append((entity.id, fname))
            elif status == "PARSE_ERROR":
                result["PARSE_ERROR"].append((entity.id, fname))
            elif status == "UNKNOWN":
                result["UNKNOWN"].append((entity.id, fname))
        for fname, ref in entity.prov.items():
            record = store.get(ref)
            if record is not None and record.evidence == "HIDDEN":
                result["HIDDEN"].append((entity.id, fname))

    for failure in snapshot.failures:
        stage = failure.stage or "failure"
        message = (failure.message or "").lower()
        if "conflict" in message or "conflict" in stage.lower():
            result["CONFLICTING"].append((stage, failure.message))
        else:
            result["PARSE_ERROR"].append((stage, failure.message))

    return result
