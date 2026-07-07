"""The flat v0.2 wire format: ``CanonicalDAWSnapshot``.

A snapshot is entities + relationships + a deduplicated provenance store.
Nothing hides inside nested JSON: a REAPER track that is *both* an
organizational lane and a mixer signal path appears as a TRACK entity and a
CHANNEL entity joined by ``TRACK_USES_CHANNEL``, because the claim "these are
different concepts that some DAWs fuse" has to be visible in the data, not in
prose.

Honesty invariants, enforced by construction and by ``validation``:

- Every value's origin is resolvable: ``Entity.prov`` maps field names to
  ``ProvenanceRecord`` ids ("*" is the entity-level default).
- ``Entity.availability`` records only *non*-AVAILABLE fields — an exception
  ledger for what could not be observed, and why.
- Confidence appears only where it is meaningful (heuristics, annotations);
  a directly parsed value does not get to claim "confidence 1.0" as if that
  were a measurement.
- The DAW-native payload is never embedded: it travels as a sibling
  ``native.json`` in the bundle, referenced by path+hash in ``extensions``.

All models forbid unknown fields: a snapshot either matches the contract or
fails loudly at parse time (see ``validation.validate_snapshot``).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .capabilities import CapabilityManifest
from .enums import Availability, EntityType, Evidence, SourceStability

SCHEMA_VERSION = "0.2.0"


class _ContractModel(BaseModel):
    """Base for all wire models: unknown fields are a contract violation."""

    model_config = ConfigDict(extra="forbid")


class NativeRef(_ContractModel):
    """The DAW-native identity and vocabulary of one entity.

    Canonical entities never erase what a thing *was* in its DAW:
    ``native_type`` keeps the native noun ("Return Track", "FX Channel",
    "folder track"), ``properties`` keeps structured native values that the
    canonical core has no slot for.
    """

    daw: str
    native_type: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)


class ProvenanceRecord(_ContractModel):
    """One deduplicated statement of where values came from.

    Referenced by id from ``Entity.prov`` and ``Relationship.prov_ref``.
    ``confidence`` is populated only where it is meaningful — heuristics and
    annotations — never on directly observed values.
    """

    id: str
    evidence: Evidence
    capture_method: str = "unknown"
    source_stability: SourceStability = "COMMUNITY_DOCUMENTED"
    source_ref: Optional[str] = None
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class Entity(_ContractModel):
    """One node in the flat snapshot graph.

    ``semantic_roles`` supports multi-role entities (a group track is both a
    submix and a folder parent). ``prov`` maps field names to provenance
    record ids, with ``"*"`` as the entity-level default. ``availability``
    holds only fields that are *not* AVAILABLE — the explicit record of what
    this snapshot does not know.
    """

    id: str
    entity_type: EntityType
    name: Optional[str] = None
    semantic_roles: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    native: Optional[NativeRef] = None
    prov: dict[str, str] = Field(default_factory=dict)
    availability: dict[str, Availability] = Field(default_factory=dict)


class Relationship(_ContractModel):
    """One directed edge between entities.

    ``rel_type`` is a registry-validated string (see ``enums.CORE_REL_TYPES``)
    rather than an enum, so relationship vocabulary can grow additively.
    ``properties`` carries edge payload: send gain (``volume`` / ``volume_db``)
    and ordering (``index``, plus ``chain`` on ``PRECEDES``). On the routing
    edges ``CHANNEL_SENDS_TO`` / ``CHANNEL_ROUTES_TO`` it may also carry an
    explicit channel spec under these exact keys: ``source_channels`` and
    ``target_channels`` (0-based channel indices on each endpoint),
    ``channel_count`` (how many channels the connection carries), and
    ``channel_layout`` (a native layout label such as ``"stereo"`` or
    ``"mono"``). Those keys are present **only when the adapter observed
    channel routing**; when they are absent the connection is
    stereo-implicit — the honest default for adapters that do not decode
    channel offsets.
    """

    id: str
    rel_type: str
    source: str
    target: str
    properties: dict[str, Any] = Field(default_factory=dict)
    prov_ref: Optional[str] = None


class SourceInfo(_ContractModel):
    """Which instrument produced this snapshot, and from what."""

    daw: str
    daw_version: Optional[str] = None
    adapter: str = ""
    adapter_version: str = ""
    capture_modes: list[str] = Field(default_factory=list)


class DomainCoverage(_ContractModel):
    """Measured observation counts for one session-state domain.

    These are counts, not claims: how many applicable items existed, and how
    many arrived observed / inferred / hidden / unsupported. The observability
    atlas aggregates these across snapshots.
    """

    applicable: int = 0
    observed: int = 0
    inferred: int = 0
    hidden: int = 0
    unsupported: int = 0


class FailureRecord(_ContractModel):
    """One explicit acquisition/mapping failure.

    A degraded-but-honest snapshot ships its failures; it does not pretend
    they did not happen.
    """

    stage: str
    message: str
    detail: Optional[str] = None


class CanonicalDAWSnapshot(_ContractModel):
    """The v0.2 snapshot: one DAW session as one adapter observed it.

    ``project`` names the single PROJECT entity's id. ``automation`` and
    ``modulation`` are populated in P7: flat descriptors of the automation
    lanes and modulation sources that also appear as AUTOMATION / MODULATION
    entities (with their CONTROLS edges) in ``entities`` / ``relationships``.
    ``extensions`` is namespaced (by DAW or tool id) so DAW-specific richness
    survives without leaking into the canonical core. ``provenance`` is the
    deduplicated record store that ``Entity.prov`` / ``Relationship.prov_ref``
    reference by id.
    """

    schema_version: str = SCHEMA_VERSION
    snapshot_id: str = ""
    created_at: str = ""
    source: SourceInfo
    project: str = ""
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    temporal_state: dict[str, Any] = Field(default_factory=dict)
    automation: list[dict[str, Any]] = Field(default_factory=list)
    modulation: list[dict[str, Any]] = Field(default_factory=list)
    capabilities: Optional[CapabilityManifest] = None
    coverage: dict[str, DomainCoverage] = Field(default_factory=dict)
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    extensions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failures: list[FailureRecord] = Field(default_factory=list)

    # -- convenience accessors -------------------------------------------

    def entity_by_id(self, entity_id: str) -> Optional[Entity]:
        for entity in self.entities:
            if entity.id == entity_id:
                return entity
        return None

    def entities_of_type(self, entity_type: str) -> list[Entity]:
        return [e for e in self.entities if e.entity_type == entity_type]

    def relationships_of_type(self, rel_type: str) -> list[Relationship]:
        return [r for r in self.relationships if r.rel_type == rel_type]

    def provenance_by_id(self, prov_id: str) -> Optional[ProvenanceRecord]:
        for record in self.provenance:
            if record.id == prov_id:
                return record
        return None
