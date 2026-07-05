"""X04 effect-return fixture: bundle validity + contract conformance (P4 gate).

The X04 bundles are adapter exports like any other, so they must clear the
same conformance bar as the frozen ``fixtures/adapters`` bundles. This module
re-runs the P2 conformance checks over the X04 bundles by importing them from
``test_conformance`` — one suite, one bar, more witnesses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from session_explorer.loaders.bundle import load_bundle
from tests.analyzer import test_conformance as conformance

X04_BUNDLES = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "cross-daw"
    / "X04_effect_return"
    / "bundles"
)
DAWS = ("ableton", "cubase", "logic", "reaper")

# The per-bundle conformance checks (everything except the module-scoped
# schema-gate test, which reads a specific adapters/ fixture).
CONFORMANCE_CHECKS = (
    conformance.test_validates_clean,
    conformance.test_exactly_one_project,
    conformance.test_single_id_namespace,
    conformance.test_track_channel_distinction,
    conformance.test_channels_are_entities_not_properties,
    conformance.test_provenance_store_resolves_and_vocabulary_is_contractual,
    conformance.test_coverage_present_and_consistent,
    conformance.test_capabilities_and_descriptor_shipped,
    conformance.test_native_sidecar_integrity,
    conformance.test_no_home_directory_leaks,
)


def _bundle(daw: str):
    path = X04_BUNDLES / daw
    if not (path / "canonical.snapshot.json").exists():
        pytest.skip(f"no X04 bundle for {daw} (run the adapter exporters)")
    return load_bundle(path)


@pytest.fixture(params=DAWS)
def bundle(request):
    return _bundle(request.param)


def test_all_four_bundles_present():
    missing = [
        daw for daw in DAWS if not (X04_BUNDLES / daw / "canonical.snapshot.json").exists()
    ]
    assert not missing, f"X04 bundles missing for: {missing}"


def test_bundle_validates(bundle):
    assert bundle.validation.valid, bundle.validation.errors


@pytest.mark.parametrize(
    "check", CONFORMANCE_CHECKS, ids=lambda fn: fn.__name__
)
def test_conformance_suite_over_x04(bundle, check):
    check(bundle)


# ---------------------------------------------------------------------------
# X04-specific shape: each capture implements the intent its own way.
# ---------------------------------------------------------------------------


def test_every_bundle_has_a_vocal_source(bundle):
    snapshot = bundle.snapshot
    vocal = [
        e
        for e in snapshot.entities
        if e.entity_type == "TRACK" and "vocal_source" in e.semantic_roles
    ]
    assert len(vocal) == 1
    assert vocal[0].name == "Lead Vox"


def test_declared_returns_where_the_daw_declares_them():
    """Ableton/Cubase/Logic declare the return; REAPER honestly cannot."""
    expectations = {
        "ableton": ("CHANNEL", "return"),
        "cubase": ("CHANNEL", "return"),
        "logic": ("TRACK", "inferred"),
    }
    for daw, (entity_type, native_type) in expectations.items():
        snapshot = _bundle(daw).snapshot
        returns = [
            e for e in snapshot.entities if "effect_return" in e.semantic_roles
        ]
        assert len(returns) == 1, f"{daw}: expected exactly one declared return"
        entity = returns[0]
        assert entity.entity_type == entity_type
        assert entity.native is not None and entity.native.native_type == native_type

    reaper = _bundle("reaper").snapshot
    assert not [
        e for e in reaper.entities if "effect_return" in e.semantic_roles
    ], "REAPER has no native return concept; a declared role would be fabricated"


def test_reaper_return_is_witnessed_topologically():
    """The REAPER capture carries the receive + reverb FX the engine derives from."""
    snapshot = _bundle("reaper").snapshot
    sends = snapshot.relationships_of_type("CHANNEL_SENDS_TO")
    assert len(sends) == 1
    send = sends[0]
    target = snapshot.entity_by_id(send.target)
    assert target is not None and target.name == "Reverb Bus"
    fx = [
        r
        for r in snapshot.relationships_of_type("CHANNEL_PROCESSED_BY")
        if r.source == target.id
    ]
    processors = [snapshot.entity_by_id(r.target) for r in fx]
    assert any(
        (p.properties.get("family") or "").lower() == "ambience" for p in processors
    )


def test_logic_return_is_annotated_not_observed():
    """The Logic pathway: sends/plug-ins arrive as ANNOTATED assertions."""
    snapshot = _bundle("logic").snapshot
    notes = [e for e in snapshot.entities if e.entity_type == "ANNOTATION"]
    by_name = {e.name: e for e in notes}
    assert "Lead Vox" in by_name and "Reverb Return" in by_name
    assert by_name["Lead Vox"].properties.get("sends") == ["Reverb"]
    assert by_name["Reverb Return"].properties.get("plugins") == ["Space Designer"]
    for note in notes:
        record = snapshot.provenance_by_id(note.prov["*"])
        assert record is not None and record.evidence == "ANNOTATED"
    # No fabricated routing: the Logic snapshot has no observed send edges.
    assert snapshot.relationships_of_type("CHANNEL_SENDS_TO") == []
    # And no fabricated channels: tracks state channel=UNKNOWN.
    for track in snapshot.entities_of_type("TRACK"):
        assert track.availability.get("channel") == "UNKNOWN"


def test_sends_reach_the_return_in_observing_dialects():
    for daw in ("ableton", "cubase"):
        snapshot = _bundle(daw).snapshot
        sends = snapshot.relationships_of_type("CHANNEL_SENDS_TO")
        assert len(sends) == 1, f"{daw}: expected exactly one send"
        target = snapshot.entity_by_id(sends[0].target)
        assert target is not None and "effect_return" in target.semantic_roles
