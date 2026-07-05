"""Contract-shape tests for the flat v0.2 models and enums."""

import pytest
from pydantic import ValidationError

from canonical_snapshot import (
    CORE_REL_TYPES,
    SCHEMA_VERSION,
    AdapterDescriptor,
    CanonicalDAWSnapshot,
    CapabilityManifest,
    DomainCapability,
    DomainCoverage,
    Entity,
    FailureRecord,
    FieldCapability,
    NativeRef,
    ProvenanceRecord,
    Relationship,
    SourceInfo,
    is_known_rel_type,
)


def test_schema_version_is_frozen_at_0_2():
    assert SCHEMA_VERSION == "0.2.0"
    snap = CanonicalDAWSnapshot(source=SourceInfo(daw="reaper"))
    assert snap.schema_version == "0.2.0"


def test_core_rel_registry_contents():
    assert CORE_REL_TYPES == (
        "TRACK_USES_CHANNEL",
        "TRACK_CONTAINS_TEMPORAL_OBJECT",
        "CHANNEL_ROUTES_TO",
        "CHANNEL_SENDS_TO",
        "CHANNEL_PROCESSED_BY",
        "CONTAINS",
        "SUMS_TO",
        "CONTROLS",
        "LINKED_WITH",
        "ALTERNATIVE_OF",
        "PRECEDES",
        "REFERENCES_ASSET",
        "GENERATED_BY",
    )


def test_rel_type_registry_is_open_but_flagged():
    # Unknown rel_types are representable (additive evolution)...
    rel = Relationship(id="r1", rel_type="X_CUSTOM_LINK", source="a", target="b")
    assert rel.rel_type == "X_CUSTOM_LINK"
    # ...but distinguishable from the core registry.
    assert not is_known_rel_type("X_CUSTOM_LINK")
    assert is_known_rel_type("TRACK_USES_CHANNEL")


def test_entity_defaults_and_prov_convention():
    entity = Entity(id="t1", entity_type="TRACK")
    assert entity.semantic_roles == []
    assert entity.prov == {}
    assert entity.availability == {}
    entity2 = Entity(
        id="t2",
        entity_type="CHANNEL",
        prov={"*": "prov:0001", "volume_db": "prov:0002"},
        availability={"pan": "UNKNOWN"},
    )
    assert entity2.prov["*"] == "prov:0001"
    assert entity2.availability["pan"] == "UNKNOWN"


def test_entity_rejects_unknown_entity_type_and_extra_fields():
    with pytest.raises(ValidationError):
        Entity(id="x", entity_type="LANE")
    with pytest.raises(ValidationError):
        Entity(id="x", entity_type="TRACK", extras={})  # no such field in v0.2


def test_provenance_record_confidence_is_optional_not_defaulted():
    record = ProvenanceRecord(id="prov:0001", evidence="OBSERVED")
    assert record.confidence is None
    assert record.source_stability == "COMMUNITY_DOCUMENTED"
    with pytest.raises(ValidationError):
        ProvenanceRecord(id="p", evidence="derived")  # v0.1 vocabulary rejected


def test_availability_vocabulary_enforced():
    with pytest.raises(ValidationError):
        Entity(id="t", entity_type="TRACK", availability={"channel": "MISSING"})


def test_snapshot_round_trips_through_json():
    snap = CanonicalDAWSnapshot(
        snapshot_id="s1",
        source=SourceInfo(daw="ableton", adapter="ableton-explorer", capture_modes=["extension_json"]),
        project="ableton:project",
        entities=[
            Entity(id="ableton:project", entity_type="PROJECT", name="Demo"),
            Entity(
                id="ableton:track-1",
                entity_type="TRACK",
                native=NativeRef(daw="ableton", native_type="audio"),
            ),
        ],
        relationships=[
            Relationship(id="r1", rel_type="CONTAINS", source="ableton:project", target="ableton:track-1")
        ],
        coverage={"structure": DomainCoverage(applicable=1, observed=1)},
        provenance=[ProvenanceRecord(id="prov:0001", evidence="OBSERVED")],
        failures=[FailureRecord(stage="parse", message="degraded surface only")],
    )
    payload = snap.model_dump()
    again = CanonicalDAWSnapshot.model_validate(payload)
    assert again == snap


def test_capability_models_shape():
    cap = FieldCapability(
        applicability="APPLICABLE",
        support="PARTIAL",
        capture_method="rpp_file",
        source_stability="COMMUNITY_DOCUMENTED",
        validation_status="TESTED",
    )
    manifest = CapabilityManifest(
        daw="reaper",
        adapter="reaper-explorer",
        read={"routing": DomainCapability(fields={"sends": cap})},
    )
    assert manifest.read["routing"].fields["sends"].support == "PARTIAL"
    # The four operation modes stay separate.
    assert manifest.write == {}
    assert manifest.live_observation == {}
    assert manifest.render == {}
    with pytest.raises(ValidationError):
        FieldCapability(applicability="MAYBE")


def test_adapter_descriptor_shape():
    descriptor = AdapterDescriptor(
        adapter_id="reaper-explorer",
        daw="reaper",
        capture_modes=["rpp_file"],
        read="structure/routing/chains observed; plugin internals hidden",
        known_limitations=["plug-in internal state is not decoded"],
    )
    assert descriptor.write == ""
    assert descriptor.known_limitations
