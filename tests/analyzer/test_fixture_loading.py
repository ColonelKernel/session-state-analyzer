"""Frozen adapter-bundle fixtures load cleanly (P1 gate).

Skips until ``fixtures/adapters/<daw>/`` bundles are exported and frozen; once
they exist, every bundle must load and validate with zero errors.
"""

from pathlib import Path

import pytest

from session_explorer.loaders import load_bundle

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "adapters"


def _bundle_dirs() -> list[Path]:
    if not FIXTURES_ROOT.is_dir():
        return []
    return sorted(
        candidate
        for daw_dir in FIXTURES_ROOT.iterdir()
        if daw_dir.is_dir()
        for candidate in [daw_dir, *daw_dir.iterdir()]
        if candidate.is_dir() and (candidate / "canonical.snapshot.json").is_file()
    )


BUNDLES = _bundle_dirs()


@pytest.mark.skipif(not BUNDLES, reason="no frozen adapter bundles under fixtures/adapters/ yet (P1)")
@pytest.mark.parametrize("bundle_dir", BUNDLES, ids=lambda p: p.name)
def test_frozen_bundle_loads_and_validates(bundle_dir):
    bundle = load_bundle(bundle_dir)
    assert bundle.validation.errors == []
    assert bundle.snapshot.project
    assert bundle.snapshot.entities
