"""Group decomposition (P6): one native "group" is several canonical concepts.

Run against the X06 grouping-depth fixture, which packs an organizational-only
folder (contains only), a summing group bus (contains + sums), and a VCA
(controls only) into one snapshot — so ``decompose_group`` can be shown reading
each facet apart, and ``is_multi_concept`` distinguishing the bus from the rest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from session_explorer.graph_layers import (
    decompose_group,
    find_group_entities,
    group_channel_id,
)
from session_explorer.loaders.bundle import load_bundle

X06 = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "cross-daw"
    / "X06_grouping_depth"
    / "bundles"
    / "synthetic"
)

FOLDER = "synthetic:folder-org"
BUS = "synthetic:bus-drum"
VCA = "synthetic:vca-drums"


@pytest.fixture(scope="module")
def snapshot():
    if not (X06 / "canonical.snapshot.json").exists():
        pytest.skip("X06 fixture not generated")
    return load_bundle(X06).snapshot


def test_find_group_entities_includes_folder_bus_and_vca(snapshot):
    found = find_group_entities(snapshot)
    # The role-bearing tracks are all present (channels ride along via the
    # SUMS_TO / CONTROLS endpoints, which is fine — decompose resolves both).
    assert FOLDER in found
    assert BUS in found
    assert VCA in found


def test_group_channel_id_resolves_track_and_channel(snapshot):
    assert group_channel_id(snapshot, BUS) == "synthetic:bus-drum:channel"
    # A channel id resolves to itself.
    assert (
        group_channel_id(snapshot, "synthetic:bus-drum:channel")
        == "synthetic:bus-drum:channel"
    )


def test_organizational_folder_is_contains_only(snapshot):
    d = decompose_group(snapshot, FOLDER)
    assert len(d.contains) == 2
    assert d.sums == []
    assert d.controls == []
    assert d.routes_in == []
    assert d.concept_count() == 1
    assert not d.is_multi_concept()


def test_group_bus_is_multi_concept(snapshot):
    d = decompose_group(snapshot, BUS)
    assert len(d.contains) == 2
    assert len(d.sums) == 2
    assert d.controls == []
    assert d.concept_count() == 2
    assert d.is_multi_concept()


def test_vca_is_controls_only(snapshot):
    d = decompose_group(snapshot, VCA)
    assert d.contains == []
    assert d.sums == []
    assert len(d.controls) == 2
    assert d.concept_count() == 1
    assert not d.is_multi_concept()


def test_decompose_from_channel_id_matches_track_id(snapshot):
    """Given the group's CHANNEL id, decomposition is identical."""
    from_track = decompose_group(snapshot, BUS)
    from_channel = decompose_group(snapshot, "synthetic:bus-drum:channel")
    assert set(from_channel.contains) == set(from_track.contains)
    assert set(from_channel.sums) == set(from_track.sums)
    assert from_channel.is_multi_concept()
