"""Concept registry + explainable alignment engine (P4 gate).

The flagship claim: across all six DAW pairs of the X04 fixture, the four
native effect-return mechanisms align as one FUNCTIONAL concept, at PROBABLE
or better, with human-readable reasons — and the engine never resolves a
too-close call silently (CONFLICTING) or claims certainty (CONFIRMED is a
user annotation only).
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import pytest

from canonical_snapshot.models import (
    CanonicalDAWSnapshot,
    Entity,
    ProvenanceRecord,
    Relationship,
    SourceInfo,
)
from session_explorer import registry as registry_pkg
from session_explorer.alignment import align, build_strips, confirm
from session_explorer.alignment.models import AlignmentResult
from session_explorer.loaders.bundle import load_bundle
from session_explorer.registry import get_registry, to_yaml

X04_BUNDLES = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "cross-daw"
    / "X04_effect_return"
    / "bundles"
)
DAWS = ("ableton", "cubase", "logic", "reaper")


def _snapshot(daw: str) -> CanonicalDAWSnapshot:
    path = X04_BUNDLES / daw
    if not (path / "canonical.snapshot.json").exists():
        pytest.skip(f"no X04 bundle for {daw}")
    return load_bundle(path).snapshot


def _pairs():
    return list(combinations(DAWS, 2))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_effect_return_implementations_cover_all_four_daws():
    registry = get_registry()
    impls = registry.implementations("effect_return")
    assert impls["ableton_live"].native_type == "return_track"
    assert impls["cubase"].native_type == "fx_channel"
    assert impls["logic_pro"].native_type == "aux_channel_strip"
    assert impls["reaper"].native_type == "media_track"


def test_effect_return_is_functional_everywhere():
    registry = get_registry()
    for daw in ("ableton_live", "cubase", "logic_pro", "reaper"):
        assert registry.equivalence("effect_return", daw) == "FUNCTIONAL"


def test_reverse_native_type_lookup():
    registry = get_registry()
    assert registry.concepts_for_native("ableton_live", "return")[0] == "effect_return"
    assert registry.concepts_for_native("cubase", "return")[0] == "effect_return"
    assert registry.concepts_for_native("ableton_live", "master")[0] == "main_output"
    assert "audio_source" in registry.concepts_for_native("reaper", "audio")
    # REAPER deliberately has NO wire type for effect_return: every REAPER
    # track is native_type "audio", so recognition must be topological.
    assert "effect_return" not in registry.concepts_for_native("reaper", "audio")
    assert registry.concepts_for_native("logic_pro", "inferred")[0] == "audio_source"
    assert registry.concepts_for_native("reaper", None) == ()
    assert registry.concepts_for_native("unknown_daw", "return") == ()


def test_scene_is_ableton_only():
    registry = get_registry()
    scene = registry["scene"]
    assert registry.equivalence("scene", "ableton_live") == "EXACT"
    for daw in ("cubase", "logic_pro", "reaper"):
        assert scene.equivalence[daw] == "NONE"
        assert daw not in scene.implementations


def test_concepts_yaml_is_in_sync_with_python_source():
    """concepts.yaml is generated output; drift means someone edited it."""
    yaml_path = Path(registry_pkg.__file__).parent / "concepts.yaml"
    assert yaml_path.is_file(), "regenerate: python -m session_explorer.registry.concepts"
    assert yaml_path.read_text(encoding="utf-8") == to_yaml()


def test_equivalence_vocabulary_is_closed():
    registry = get_registry()
    for concept in registry:
        for daw, level in concept.equivalence.items():
            assert level in registry_pkg.EQUIVALENCE_LEVELS, (
                concept.concept_id,
                daw,
                level,
            )


# ---------------------------------------------------------------------------
# X04 alignment across all six pairs
# ---------------------------------------------------------------------------


def _result_for_concept(results: list[AlignmentResult], concept: str) -> AlignmentResult:
    matches = [r for r in results if r.concept_id == concept]
    assert matches, f"no alignment result for concept {concept}"
    assert len(matches) == 1, f"expected exactly one {concept} row, got {matches}"
    return matches[0]


@pytest.mark.parametrize("pair", _pairs(), ids=lambda p: f"{p[0]}-{p[1]}")
def test_return_aligns_probable_across_all_six_pairs(pair):
    a, b = pair
    results = align(_snapshot(a), _snapshot(b))
    result = _result_for_concept(results, "effect_return")
    assert result.status == "PROBABLE", (pair, result)
    assert result.target_entity is not None
    assert len(result.reasons) >= 2, result.reasons
    # The headline reason names the two native mechanisms.
    assert any("effect_return implementations" in r for r in result.reasons)
    # The registry says this match is FUNCTIONAL on both sides.
    registry = get_registry()
    assert registry.equivalence("effect_return", result.source_daw) == "FUNCTIONAL"
    assert registry.equivalence("effect_return", result.target_daw) == "FUNCTIONAL"


@pytest.mark.parametrize("pair", _pairs(), ids=lambda p: f"{p[0]}-{p[1]}")
def test_no_conflicting_on_the_return(pair):
    a, b = pair
    forward = align(_snapshot(a), _snapshot(b))
    backward = align(_snapshot(b), _snapshot(a))
    for results in (forward, backward):
        for result in results:
            if result.concept_id == "effect_return":
                assert result.status != "CONFLICTING", result


@pytest.mark.parametrize("pair", _pairs(), ids=lambda p: f"{p[0]}-{p[1]}")
def test_vocal_sources_match(pair):
    a, b = pair
    results = align(_snapshot(a), _snapshot(b))
    result = _result_for_concept(results, "audio_source")
    assert result.status == "PROBABLE", result
    assert result.source_name == "Lead Vox"
    assert result.target_name == "Lead Vox"


@pytest.mark.parametrize("pair", _pairs(), ids=lambda p: f"{p[0]}-{p[1]}")
def test_every_non_unmatched_result_has_reasons(pair):
    a, b = pair
    for result in align(_snapshot(a), _snapshot(b)):
        if result.status != "UNMATCHED":
            assert result.reasons, result
        assert result.status in ("PROBABLE", "POSSIBLE", "UNMATCHED", "CONFLICTING")


def test_logic_side_reasons_say_annotated():
    """The ANNOTATED pathway is visible in the explanation, not laundered."""
    results = align(_snapshot("ableton"), _snapshot("logic"))
    result = _result_for_concept(results, "effect_return")
    assert any("annotated" in reason.lower() for reason in result.reasons), (
        result.reasons
    )


def test_reaper_derivation_is_spelled_out():
    """REAPER's return is derived from topology and the reason says how."""
    results = align(_snapshot("cubase"), _snapshot("reaper"))
    result = _result_for_concept(results, "effect_return")
    headline = next(r for r in result.reasons if "effect_return implementations" in r)
    assert "derived" in headline and "receives" in headline, headline


# ---------------------------------------------------------------------------
# Engine mechanics (synthetic snapshots)
# ---------------------------------------------------------------------------


def _mini_snapshot(daw: str, entities, relationships=()) -> CanonicalDAWSnapshot:
    return CanonicalDAWSnapshot(
        source=SourceInfo(daw=daw),
        project=f"{daw}:project",
        entities=list(entities),
        relationships=list(relationships),
        provenance=[ProvenanceRecord(id="prov:0001", evidence="OBSERVED")],
    )


def _track(daw: str, ident: str, name: str) -> Entity:
    return Entity(id=f"{daw}:{ident}", entity_type="TRACK", name=name)


def test_conflicting_when_two_candidates_are_too_close():
    a = _mini_snapshot("dawa", [_track("dawa", "t1", "Pad")])
    b = _mini_snapshot(
        "dawb", [_track("dawb", "t1", "Pad 1"), _track("dawb", "t2", "Pad 2")]
    )
    (result,) = align(a, b)
    assert result.status == "CONFLICTING"
    assert any("refusing to pick" in reason for reason in result.reasons)


def test_unmatched_below_the_floor():
    a = _mini_snapshot("dawa", [_track("dawa", "t1", "Kick")])
    b = _mini_snapshot(
        "dawb",
        [
            Entity(
                id="dawb:m1",
                entity_type="CHANNEL",
                name="Totally Different",
                semantic_roles=["main_output"],
            )
        ],
    )
    (result,) = align(a, b)
    assert result.status == "UNMATCHED"
    assert result.target_entity is None


def test_media_hash_equality_is_a_signal():
    def side(daw: str, track_name: str) -> CanonicalDAWSnapshot:
        entities = [
            _track(daw, "t1", track_name),
            Entity(id=f"{daw}:c1", entity_type="TEMPORAL_OBJECT", name="clip"),
            Entity(
                id="asset:shared",
                entity_type="MEDIA_ASSET",
                name="take.wav",
                properties={"sha256": "abc123def4567890"},
            ),
        ]
        rels = [
            Relationship(
                id=f"{daw}:r1",
                rel_type="TRACK_CONTAINS_TEMPORAL_OBJECT",
                source=f"{daw}:t1",
                target=f"{daw}:c1",
            ),
            Relationship(
                id=f"{daw}:r2",
                rel_type="REFERENCES_ASSET",
                source=f"{daw}:c1",
                target="asset:shared",
            ),
        ]
        return _mini_snapshot(daw, entities, rels)

    (result,) = align(side("dawa", "Alpha"), side("dawb", "Beta"))
    assert any("content hash" in reason for reason in result.reasons), result.reasons
    assert result.status in ("PROBABLE", "POSSIBLE")


def test_confirm_yields_annotated_provenance_payload():
    results = align(_snapshot("ableton"), _snapshot("cubase"))
    result = _result_for_concept(results, "effect_return")
    payload = confirm(result, confirmed_by="test-user")
    assert result.status == "CONFIRMED"
    assert payload["evidence"] == "ANNOTATED"
    assert payload["capture_method"] == "user_alignment_confirmation"
    assert payload["source_stability"] == "MANUAL"
    assert result.source_entity in payload["source_ref"]
    assert "test-user" in payload["explanation"]
    # The payload is a valid ProvenanceRecord on the wire.
    ProvenanceRecord.model_validate(payload)


def test_confirm_refuses_unmatched():
    result = AlignmentResult(
        source_entity="x:t1", target_entity=None, status="UNMATCHED", confidence=None
    )
    with pytest.raises(ValueError):
        confirm(result)


def test_strips_do_not_double_count_track_channel_pairs():
    """A TRACK and its CHANNEL are one strip, not two rival candidates."""
    snapshot = _snapshot("reaper")
    strips = build_strips(snapshot)
    ids = [strip.primary_id for strip in strips]
    assert len(ids) == len(set(ids))
    assert not any(pid.endswith(":channel") for pid in ids)
    by_name = {strip.name: strip for strip in strips}
    assert by_name["Reverb Bus"].has_channel
    assert by_name["Reverb Bus"].concept_id == "effect_return"
    assert by_name["Reverb Bus"].concept_declared is False  # derived, honestly
