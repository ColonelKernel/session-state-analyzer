"""The dataset export (master-prompt §57): tree shape, round-trips, leak scan.

Builds the full ``dataset/`` tree from the frozen fixtures into a tmp dir and
asserts the packaging contract:

- all eight §57 subdirs exist and hold what they should;
- every exported snapshot re-validates against the v0.2 contract;
- **the blocking leak scan**: no ``/Users/``, live username, ``/home/`` or
  ``/Volumes/`` anywhere in the tree, and no ``.wav`` at all — audio never
  travels, only descriptors;
- redacted asset paths surface as ``asset:sha256:`` tokens;
- the manifest and the metrics report both round-trip through their schemas;
- ``native.json`` absence is reported honestly (the parameter-change bundles
  ship no native payload);
- the build is deterministic (same bytes on a rebuild).
"""

from __future__ import annotations

import getpass
import json
import os
from pathlib import Path

import pytest

from canonical_snapshot import validate_snapshot
from session_explorer.dataset_export import (
    DatasetManifest,
    build_dataset,
    hash_asset_path,
    redact_paths,
    sanitize_snapshot,
)
from session_explorer.dataset_export.layout import SUBDIRS
from session_explorer.metrics import MetricsReport

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "fixtures"
_ADAPTERS = _FIXTURES / "adapters"
_X04 = _FIXTURES / "cross-daw" / "X04_effect_return"
_EXPERIMENTS = _FIXTURES / "experiments"


def _usernames() -> set[str]:
    """Every spelling of the live username the leak scan must block on."""
    names: set[str] = set()
    try:
        names.add(getpass.getuser())
    except Exception:  # noqa: BLE001
        pass
    try:
        names.add(os.getlogin())
    except Exception:  # noqa: BLE001
        pass
    try:
        import pwd

        names.add(pwd.getpwuid(os.getuid()).pw_name)
    except Exception:  # noqa: BLE001
        pass
    names.add(Path.home().name)
    for var in ("USER", "LOGNAME", "USERNAME"):
        value = os.environ.get(var)
        if value:
            names.add(value)
    return {n for n in names if n and len(n) >= 3}


@pytest.fixture(scope="module")
def dataset(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("dataset_out") / "dataset"
    build_dataset(
        out,
        fixtures_root=_ADAPTERS,
        x04_root=_X04,
        experiments_root=_EXPERIMENTS,
    )
    return out


# --------------------------------------------------------------------------
# Tree shape.
# --------------------------------------------------------------------------


def test_all_eight_subdirs_exist(dataset: Path) -> None:
    assert len(SUBDIRS) == 8
    for subdir in SUBDIRS:
        assert (dataset / subdir).is_dir(), f"missing subdir {subdir}"


def test_each_subdir_has_expected_content(dataset: Path) -> None:
    def n_json(sub: str) -> int:
        return len(list((dataset / sub).glob("*.json")))

    # 5 adapters + 4 X04 + 2x2 experiment bundles = 13 snapshots.
    assert n_json("snapshots") == 13
    # Every bundle with a native payload (the parameter-change pair has none).
    assert n_json("native") == 11
    # 2 experiments x 2 render descriptors.
    assert n_json("renders") == 4
    assert n_json("observations") >= 3
    assert n_json("interventions") == 2
    assert n_json("alignments") == 1
    assert n_json("fixtures") == 1
    assert n_json("metrics") == 1


# --------------------------------------------------------------------------
# Snapshots re-validate.
# --------------------------------------------------------------------------


def test_every_exported_snapshot_revalidates(dataset: Path) -> None:
    snapshots = sorted((dataset / "snapshots").glob("*.json"))
    assert snapshots, "no snapshots exported"
    for path in snapshots:
        report = validate_snapshot(json.loads(path.read_text(encoding="utf-8")))
        assert not report.errors, f"{path.name} failed to re-validate: {report.errors}"


# --------------------------------------------------------------------------
# The blocking leak scan.
# --------------------------------------------------------------------------


def test_leak_scan_finds_no_paths_username_or_wav(dataset: Path) -> None:
    forbidden = ["/Users/", "/home/", "/Volumes/", "\\Users\\", ".wav"]
    forbidden += sorted(_usernames())

    offenders: dict[str, list[str]] = {}
    for path in dataset.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for token in forbidden:
            if token and token in text:
                offenders.setdefault(token, []).append(
                    str(path.relative_to(dataset))
                )

    assert not offenders, f"LEAK SCAN FAILED — forbidden tokens present: {offenders}"


def test_hashed_asset_paths_are_present(dataset: Path) -> None:
    # The frozen fixtures carry media references (e.g. audio/vox.wav); after
    # sanitization they must surface as asset:sha256: tokens somewhere.
    blob = "".join(
        p.read_text(encoding="utf-8")
        for p in (dataset / "snapshots").glob("*.json")
    )
    assert "asset:sha256:" in blob


# --------------------------------------------------------------------------
# Manifest + metrics round-trip.
# --------------------------------------------------------------------------


def test_manifest_round_trips(dataset: Path) -> None:
    payload = json.loads(
        (dataset / "fixtures" / "manifest.json").read_text(encoding="utf-8")
    )
    manifest = DatasetManifest.model_validate(payload)
    assert manifest.counts["snapshots"] == 13
    assert manifest.counts["native"] == 11
    assert manifest.generated_at is None  # no wall-clock in serialized content
    # The parameter-change bundles ship no native.json — reported honestly.
    missing_native = [b.name for b in manifest.bundles if not b.native_present]
    assert set(missing_native) == {
        "experiment_parameter_change_before",
        "experiment_parameter_change_after",
    }
    # Ladder reached-sets differ per DAW (a profile, not a rank): logic reaches
    # L5 without L2, cubase reaches L2 without L5.
    by_name = {b.name: b for b in manifest.bundles}
    assert 2 not in by_name["adapter_logic"].ladder_reached
    assert 2 in by_name["adapter_cubase"].ladder_reached


def test_metrics_round_trips_through_metrics_report(dataset: Path) -> None:
    payload = json.loads(
        (dataset / "metrics" / "metrics.json").read_text(encoding="utf-8")
    )
    report = MetricsReport.model_validate(payload)
    assert report.bundles, "metrics report carries no bundles"
    assert report.aggregate.applicable >= 0


# --------------------------------------------------------------------------
# Determinism.
# --------------------------------------------------------------------------


def test_build_is_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    for out in (a, b):
        build_dataset(
            out,
            fixtures_root=_ADAPTERS,
            x04_root=_X04,
            experiments_root=_EXPERIMENTS,
        )
    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert files_a == files_b
    for rel in files_a:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"nondeterministic: {rel}"


# --------------------------------------------------------------------------
# Sanitizer units.
# --------------------------------------------------------------------------


def test_redact_paths_scrubs_home_volume_and_username() -> None:
    assert redact_paths("/Users/alice/session/x.als") == "<redacted>/session/x.als"
    assert redact_paths("/home/bob/mix") == "<redacted>/mix"
    assert redact_paths("/Volumes/BigDisk/audio") == "<redacted>/audio"
    assert "<redacted>" in redact_paths(str(Path.home() / "proj"))


def test_hash_asset_path_is_stable_and_prefixed() -> None:
    token = hash_asset_path("audio/vox.wav")
    assert token.startswith("asset:sha256:")
    assert len(token) == len("asset:sha256:") + 12
    assert token == hash_asset_path("audio/vox.wav")


def test_sanitize_snapshot_does_not_mutate_input_and_removes_wav() -> None:
    raw = {
        "entities": [
            {"id": "m1", "name": "vox.wav", "properties": {"path": "audio/vox.wav"}}
        ]
    }
    original = json.dumps(raw, sort_keys=True)
    out = sanitize_snapshot(raw)
    assert json.dumps(raw, sort_keys=True) == original  # input untouched
    blob = json.dumps(out)
    assert ".wav" not in blob
    assert "asset:sha256:" in blob
