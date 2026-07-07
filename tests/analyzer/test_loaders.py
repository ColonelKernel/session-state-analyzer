"""Bundle loading over a synthetic 5-file layout."""

import json

import pytest

from canonical_snapshot import (
    AdapterDescriptor,
    CapabilityManifest,
    SourceInfo,
    flatten_session,
    nested,
)
from session_explorer.loaders import get_presentation, known_daws, load_bundle, load_snapshot
from session_explorer.loaders.bundle import (
    CAPABILITIES_FILE,
    DESCRIPTOR_FILE,
    NATIVE_FILE,
    SNAPSHOT_FILE,
    VALIDATION_FILE,
)


def _snapshot_payload():
    session = nested.CanonicalSession(
        dialect="reaper",
        name="Bundle Demo",
        tracks=[nested.Track(id="reaper:track-0", name="Vox", role="Vocal")],
        native=nested.NativePayload(dialect="reaper", model_name="ProjectState", model={"tracks": []}),
    )
    snapshot = flatten_session(
        session,
        SourceInfo(daw="reaper", adapter="reaper-explorer", capture_modes=["rpp_file"]),
        native_file=NATIVE_FILE,
        native_sha256="deadbeef",
    )
    return snapshot.model_dump()


def _write_bundle(tmp_path, *, with_sidecars=True):
    (tmp_path / SNAPSHOT_FILE).write_text(json.dumps(_snapshot_payload()))
    if with_sidecars:
        (tmp_path / DESCRIPTOR_FILE).write_text(
            json.dumps(
                AdapterDescriptor(
                    adapter_id="reaper-explorer",
                    daw="reaper",
                    capture_modes=["rpp_file"],
                    known_limitations=["plug-in internals hidden"],
                ).model_dump()
            )
        )
        (tmp_path / CAPABILITIES_FILE).write_text(
            json.dumps(CapabilityManifest(daw="reaper", adapter="reaper-explorer").model_dump())
        )
        (tmp_path / NATIVE_FILE).write_text(json.dumps({"tracks": [], "verbatim": True}))
        (tmp_path / VALIDATION_FILE).write_text(json.dumps({"valid": True, "errors": []}))
    return tmp_path


def test_load_full_bundle(tmp_path):
    bundle = load_bundle(_write_bundle(tmp_path))
    assert bundle.snapshot.source.daw == "reaper"
    assert bundle.validation.valid
    assert bundle.descriptor.adapter_id == "reaper-explorer"
    assert bundle.capabilities.daw == "reaper"
    assert bundle.shipped_validation == {"valid": True, "errors": []}
    assert bundle.load_warnings == []
    # native.json loads lazily and verbatim.
    assert bundle.native == {"tracks": [], "verbatim": True}


def test_load_degraded_bundle_warns_but_loads(tmp_path):
    bundle = load_bundle(_write_bundle(tmp_path, with_sidecars=False))
    assert bundle.snapshot.snapshot_id
    assert bundle.descriptor is None
    assert bundle.capabilities is None
    assert bundle.shipped_validation is None
    joined = " ".join(bundle.load_warnings)
    assert DESCRIPTOR_FILE in joined
    assert CAPABILITIES_FILE in joined
    assert VALIDATION_FILE in joined
    # Missing native.json degrades on access, not at load.
    assert bundle.native is None
    assert any(NATIVE_FILE in w for w in bundle.load_warnings)


def test_missing_snapshot_is_fatal(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_bundle(tmp_path)


def test_load_snapshot_single_file(tmp_path):
    path = tmp_path / SNAPSHOT_FILE
    path.write_text(json.dumps(_snapshot_payload()))
    snapshot = load_snapshot(path)
    assert snapshot.project == "reaper:project"


def test_load_snapshot_rejects_invalid(tmp_path):
    payload = _snapshot_payload()
    payload["project"] = "not:an:entity"
    path = tmp_path / SNAPSHOT_FILE
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_snapshot(path)


def test_presentation_registry_is_data_only():
    # Dialect ids the adapters actually report ("ableton_live", "logic_pro")
    # alias their short-form entries (P6 two-mode workbench).
    assert known_daws() == [
        "ableton",
        "ableton_live",
        "cubase",
        "logic",
        "logic_pro",
        "reaper",
    ]
    ableton = get_presentation("ableton")
    assert ableton.display_name == "Ableton Live"
    assert get_presentation("ableton_live").display_name == "Ableton Live"
    assert get_presentation("logic_pro").display_name == "Logic Pro"
    assert ableton.native_vocab["PROCESSOR"] == "Device"
    reaper = get_presentation("reaper")
    assert reaper.native_vocab["TEMPORAL_OBJECT"] == "Media Item"
    # Unknown DAWs get an honest generic presentation, not an error.
    other = get_presentation("bitwig")
    assert other.display_name == "Bitwig"
    assert other.native_vocab["TRACK"] == "Track"
