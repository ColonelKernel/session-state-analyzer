"""validate_snapshot: strict parse, referential checks, and loud version gate."""

import pytest

from canonical_snapshot import (
    CanonicalDAWSnapshot,
    Entity,
    IncompatibleSchemaError,
    ProvenanceRecord,
    Relationship,
    SourceInfo,
    validate_snapshot,
)


def _minimal_payload() -> dict:
    return CanonicalDAWSnapshot(
        snapshot_id="s1",
        source=SourceInfo(daw="reaper"),
        project="reaper:project",
        entities=[
            Entity(
                id="reaper:project",
                entity_type="PROJECT",
                name="Demo",
                prov={"*": "prov:0001"},
            ).model_dump(),
        ],
        provenance=[ProvenanceRecord(id="prov:0001", evidence="OBSERVED").model_dump()],
    ).model_dump()


def test_minimal_snapshot_validates_clean():
    report = validate_snapshot(_minimal_payload())
    assert report.valid
    assert report.errors == []
    assert report.stats["entities"] == 1
    assert report.stats["entities_by_type"] == {"PROJECT": 1}


def test_accepts_already_parsed_snapshot():
    snap = CanonicalDAWSnapshot.model_validate(_minimal_payload())
    assert validate_snapshot(snap).valid


@pytest.mark.parametrize("version", ["0.1.0", "0.3.0", "1.0.0", "2.2.0"])
def test_incompatible_schema_version_raises_loudly(version):
    payload = _minimal_payload()
    payload["schema_version"] = version
    with pytest.raises(IncompatibleSchemaError) as excinfo:
        validate_snapshot(payload)
    assert version in str(excinfo.value)


def test_patch_versions_within_0_2_are_accepted():
    payload = _minimal_payload()
    payload["schema_version"] = "0.2.7"
    assert validate_snapshot(payload).valid


def test_missing_schema_version_is_an_error():
    payload = _minimal_payload()
    del payload["schema_version"]
    report = validate_snapshot(payload)
    assert not report.valid
    assert any("schema_version" in e for e in report.errors)


def test_parse_errors_are_reported_not_raised():
    payload = _minimal_payload()
    payload["entities"][0]["entity_type"] = "NOT_A_TYPE"
    report = validate_snapshot(payload)
    assert not report.valid
    assert any(e.startswith("parse:") for e in report.errors)


def test_duplicate_entity_ids_rejected():
    payload = _minimal_payload()
    payload["entities"].append(payload["entities"][0].copy())
    report = validate_snapshot(payload)
    assert any("duplicate entity id" in e for e in report.errors)


def test_relationship_endpoints_must_exist():
    payload = _minimal_payload()
    payload["relationships"] = [
        Relationship(id="r1", rel_type="CONTAINS", source="reaper:project", target="ghost").model_dump()
    ]
    report = validate_snapshot(payload)
    assert any("ghost" in e for e in report.errors)


def test_prov_refs_must_resolve():
    payload = _minimal_payload()
    payload["entities"][0]["prov"]["color"] = "prov:9999"
    report = validate_snapshot(payload)
    assert any("prov:9999" in e for e in report.errors)

    payload = _minimal_payload()
    payload["entities"].append(
        Entity(id="t1", entity_type="TRACK", availability={"channel": "UNKNOWN"}).model_dump()
    )
    payload["relationships"] = [
        Relationship(
            id="r1", rel_type="CONTAINS", source="reaper:project", target="t1", prov_ref="prov:404"
        ).model_dump()
    ]
    report = validate_snapshot(payload)
    assert any("prov:404" in e for e in report.errors)


def test_exactly_one_project_required():
    payload = _minimal_payload()
    payload["entities"].append(
        Entity(id="p2", entity_type="PROJECT").model_dump()
    )
    report = validate_snapshot(payload)
    assert any("exactly one PROJECT" in e for e in report.errors)

    payload = _minimal_payload()
    payload["entities"][0]["entity_type"] = "TRACK"
    payload["entities"][0]["availability"] = {"channel": "UNKNOWN"}
    report = validate_snapshot(payload)
    assert any("exactly one PROJECT" in e for e in report.errors)


def test_project_pointer_must_match():
    payload = _minimal_payload()
    payload["project"] = "somewhere:else"
    report = validate_snapshot(payload)
    assert any("snapshot.project" in e for e in report.errors)


def test_unknown_rel_type_warns_but_passes():
    payload = _minimal_payload()
    payload["entities"].append(
        Entity(id="t1", entity_type="TRACK", availability={"channel": "UNKNOWN"}).model_dump()
    )
    payload["relationships"] = [
        Relationship(id="r1", rel_type="X_VENDORED", source="reaper:project", target="t1").model_dump()
    ]
    report = validate_snapshot(payload)
    assert report.valid
    assert any("X_VENDORED" in w for w in report.warnings)


def test_track_without_channel_warns_unless_availability_says_why():
    silent = Entity(id="t1", entity_type="TRACK").model_dump()
    honest = Entity(
        id="t2", entity_type="TRACK", availability={"channel": "UNKNOWN"}
    ).model_dump()
    payload = _minimal_payload()
    payload["entities"] += [silent, honest]
    report = validate_snapshot(payload)
    assert report.valid  # warning, not error
    assert any("'t1'" in w and "TRACK_USES_CHANNEL" in w for w in report.warnings)
    assert not any("'t2'" in w for w in report.warnings)


def test_observed_confidence_warns():
    payload = _minimal_payload()
    payload["provenance"][0]["confidence"] = 1.0
    report = validate_snapshot(payload)
    assert report.valid
    assert any("confidence" in w for w in report.warnings)


def test_feedback_cycle_validates_clean():
    """A→B and B→A routing feedback is legal data, never a validation error."""
    payload = _minimal_payload()
    payload["entities"] += [
        Entity(id="a", entity_type="CHANNEL").model_dump(),
        Entity(id="b", entity_type="CHANNEL").model_dump(),
    ]
    payload["relationships"] = [
        Relationship(id="r1", rel_type="CHANNEL_SENDS_TO", source="a", target="b").model_dump(),
        Relationship(id="r2", rel_type="CHANNEL_SENDS_TO", source="b", target="a").model_dump(),
    ]
    report = validate_snapshot(payload)
    assert report.valid
    assert report.errors == []


def test_new_lineage_rel_types_do_not_warn():
    """DERIVED_FROM / SHARES_SOURCE_WITH are now core registry members."""
    payload = _minimal_payload()
    payload["entities"] += [
        Entity(id="v1", entity_type="VARIANT").model_dump(),
        Entity(id="v2", entity_type="VARIANT").model_dump(),
    ]
    payload["relationships"] = [
        Relationship(id="r1", rel_type="DERIVED_FROM", source="v1", target="v2").model_dump(),
        Relationship(id="r2", rel_type="SHARES_SOURCE_WITH", source="v1", target="v2").model_dump(),
    ]
    report = validate_snapshot(payload)
    assert report.valid
    assert not any("DERIVED_FROM" in w for w in report.warnings)
    assert not any("SHARES_SOURCE_WITH" in w for w in report.warnings)
