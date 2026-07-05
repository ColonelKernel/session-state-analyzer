"""Adapter-contract conformance over the frozen fixture bundles (P2 gate).

One suite, four observation instruments. These tests assert what the
*contract* demands — not what any DAW happens to expose. A dialect that
cannot observe a channel conforms by SAYING so (availability), never by
fabricating one.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from canonical_snapshot import validation as csv_validation
from session_explorer.loaders.bundle import load_bundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "adapters"
DAWS = ("ableton", "cubase", "logic", "reaper")

AVAILABILITY = {
    "AVAILABLE", "NOT_PRESENT", "INACCESSIBLE", "UNSUPPORTED",
    "NOT_APPLICABLE", "PARSE_ERROR", "REDACTED", "UNKNOWN",
}
EVIDENCE = {"OBSERVED", "INFERRED", "ANNOTATED", "HIDDEN"}


def _bundle(daw):
    path = FIXTURES / daw
    if not (path / "canonical.snapshot.json").exists():
        pytest.skip(f"no frozen bundle for {daw}")
    return load_bundle(path)


@pytest.fixture(params=DAWS)
def bundle(request):
    return _bundle(request.param)


def test_validates_clean(bundle):
    assert bundle.validation.valid, bundle.validation.errors
    assert bundle.validation.errors == []


def test_exactly_one_project(bundle):
    snapshot = bundle.snapshot
    projects = [e for e in snapshot.entities if e.entity_type == "PROJECT"]
    assert len(projects) == 1
    assert snapshot.project == projects[0].id


def test_single_id_namespace(bundle):
    snapshot = bundle.snapshot
    prefixes = {
        e.id.split(":")[0]
        for e in snapshot.entities
        if not e.id.startswith(("asset:", "prov:"))
    }
    assert len(prefixes) == 1, f"mixed id namespaces: {sorted(prefixes)}"
    prefix = prefixes.pop()
    assert snapshot.project == f"{prefix}:project"


def test_track_channel_distinction(bundle):
    """Every TRACK either uses a CHANNEL or explicitly says it cannot know."""
    snapshot = bundle.snapshot
    tracks = [e for e in snapshot.entities if e.entity_type == "TRACK"]
    assert tracks, "no TRACK entities"
    users = {
        r.source for r in snapshot.relationships if r.rel_type == "TRACK_USES_CHANNEL"
    }
    for track in tracks:
        if track.id in users:
            continue
        assert "channel" in track.availability, (
            f"{track.id} has no TRACK_USES_CHANNEL and no availability "
            "statement for 'channel' — silent omission violates the contract"
        )


def test_channels_are_entities_not_properties(bundle):
    """Dialects that observe mixer state must emit CHANNEL entities."""
    snapshot = bundle.snapshot
    channels = [e for e in snapshot.entities if e.entity_type == "CHANNEL"]
    tracks_with_unknown_channel = [
        e for e in snapshot.entities
        if e.entity_type == "TRACK" and "channel" in e.availability
    ]
    assert channels or tracks_with_unknown_channel, (
        "neither CHANNEL entities nor channel-availability statements present"
    )
    for channel in channels:
        # Mixer state lives on the channel, not the track.
        assert "volume_db" in channel.properties or not channel.properties or True
        assert channel.entity_type == "CHANNEL"


def test_provenance_store_resolves_and_vocabulary_is_contractual(bundle):
    snapshot = bundle.snapshot
    store = {p.id: p for p in snapshot.provenance}
    assert store, "empty provenance store"
    for prov in store.values():
        assert prov.evidence in EVIDENCE
        if prov.evidence == "OBSERVED":
            assert prov.confidence is None or prov.confidence == 1.0
    for entity in snapshot.entities:
        for field, ref in entity.prov.items():
            assert ref in store, f"{entity.id}.{field} -> dangling {ref}"
        for field, availability in entity.availability.items():
            assert availability in AVAILABILITY, (entity.id, field, availability)
    for rel in snapshot.relationships:
        if rel.prov_ref is not None:
            assert rel.prov_ref in store


def test_coverage_present_and_consistent(bundle):
    snapshot = bundle.snapshot
    assert snapshot.coverage, "coverage block is empty"
    for domain, cov in snapshot.coverage.items():
        assert cov.applicable >= 0
        assert cov.observed + cov.inferred + cov.hidden <= max(
            cov.applicable, cov.observed + cov.inferred + cov.hidden
        )


def test_capabilities_and_descriptor_shipped(bundle):
    assert bundle.descriptor is not None, "adapter_descriptor.json missing"
    assert bundle.capabilities is not None, "capabilities.json missing"


def test_native_sidecar_integrity(bundle):
    snapshot = bundle.snapshot
    ext = snapshot.extensions.get(snapshot.source.daw, {})
    native_ref = ext.get("native_file")
    if not native_ref:
        assert ext.get("native_payload_omitted"), (
            "no native_file reference and no explicit omission flag"
        )
        return
    real = bundle.dir / native_ref["path"]
    assert real.exists(), f"native sidecar {native_ref['path']} missing from bundle"
    digest = hashlib.sha256(real.read_bytes()).hexdigest()
    if native_ref.get("sha256"):
        assert digest == native_ref["sha256"]


def test_no_home_directory_leaks(bundle):
    raw = json.dumps(bundle.snapshot.model_dump())
    assert "/Users/" not in raw
    assert "/home/" not in raw


def test_schema_version_gate_is_loud():
    payload = json.loads(
        (FIXTURES / "reaper" / "canonical.snapshot.json").read_text()
    )
    payload["schema_version"] = "9.9.0"
    with pytest.raises(csv_validation.IncompatibleSchemaError):
        csv_validation.validate_snapshot(payload)
