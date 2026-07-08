"""The Compatibility Ladder (Phase 3) over the frozen fixture bundles.

Asserts each fixture's ACTUAL reached rung set — verified against the real
fixture data, not the design brief. The load-bearing assertion is that the
profiles genuinely *differ in shape*: the synthetic Logic bundle reaches L5
(acoustic outcome) while reaching neither L2 nor L3, so "highest rung" is not a
rank and a reached set is not a prefix.

Mirrors ``test_atlas.py``: a module-scoped ``load_bundle`` fixture per DAW plus
the aggregate ``assess_fixtures`` walk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from session_explorer.compat.ladder import (
    LEVEL_META,
    LadderContext,
    LadderLevel,
    LadderProfile,
    assess_bundle,
    assess_fixtures,
    render_ladder_markdown,
)
from session_explorer.interventions.experiment import build_effect_send_experiment
from session_explorer.loaders.bundle import load_bundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "adapters"
EFFECT_SEND = Path(__file__).resolve().parents[2] / "fixtures" / "experiments" / "effect_send"

# Standalone adapter bundles walked by assess_fixtures (empty context each).
ADAPTERS = ("reaper", "ableton", "cubase", "logic", "logic_real")


def _bundle(daw: str):
    path = FIXTURES / daw
    if not (path / "canonical.snapshot.json").exists():
        pytest.skip(f"no frozen bundle for {daw}")
    return load_bundle(path)


@pytest.fixture(scope="module")
def bundles():
    return {daw: _bundle(daw) for daw in ADAPTERS}


@pytest.fixture(scope="module")
def profiles(bundles):
    """Each standalone adapter bundle assessed with an empty context."""
    return {daw: assess_bundle(bundles[daw]) for daw in ADAPTERS}


@pytest.fixture(scope="module")
def all_profiles():
    """The full assess_fixtures() walk (adapters + injected L6 experiment member)."""
    return assess_fixtures()


# --- rung metadata --------------------------------------------------------


def test_seven_rungs_defined():
    assert [lvl.value for lvl in LadderLevel] == [0, 1, 2, 3, 4, 5, 6]
    assert set(LEVEL_META) == set(range(7))
    # Every rung has a (slug, title, description) triple.
    for level, meta in LEVEL_META.items():
        assert len(meta) == 3
        assert all(isinstance(part, str) and part for part in meta)
    assert LEVEL_META[0][0] == "loadable"
    assert LEVEL_META[6][0] == "controlled-intervention"


# --- per-fixture reached sets (verified against reality) ------------------


def test_reaper_structure_routing_timeline(profiles):
    """REAPER: L0-L3. Has TEMPORAL_OBJECT (timeline), routing edges, no L4/L5/L6."""
    p = profiles["reaper"]
    assert p.reached_set == {0, 1, 2, 3}
    # L3 is a *timeline* claim here, not automation (REAPER emits no AUTOMATION).
    l3 = p.levels[3]
    assert l3.reached
    assert any("timeline present" in e for e in l3.evidence)
    assert not any("automation present" in e for e in l3.evidence)
    for lvl in (4, 5, 6):
        assert not p.levels[lvl].reached


def test_ableton_scenes_light_l4_provisional(profiles):
    """Ableton: L0-L4, where L4 is reached *and provisional* on scene evidence."""
    p = profiles["ableton"]
    assert p.reached_set == {0, 1, 2, 3, 4}
    l4 = p.levels[4]
    assert l4.reached and l4.provisional
    assert any("scene" in e.lower() for e in l4.evidence)
    assert l4.missing  # the "strengthens as ... lands" grow-note
    for lvl in (5, 6):
        assert not p.levels[lvl].reached


def test_cubase_has_real_automation_at_l3(profiles):
    """Cubase: L0-L3, and L3 now carries real automation (the re-exported lane)."""
    p = profiles["cubase"]
    assert p.reached_set == {0, 1, 2, 3}
    l3 = p.levels[3]
    assert l3.reached
    assert any("automation present" in e for e in l3.evidence)
    for lvl in (4, 5, 6):
        assert not p.levels[lvl].reached


def test_logic_reaches_l5_but_not_l2_or_l3(profiles):
    """The load-bearing 'profiles, not ranks' fixture.

    The synthetic full-pipeline Logic bundle reaches L5 (OBSERVATION entities)
    while reaching NEITHER L2 (routing is annotated, no CHANNEL/routing edges)
    NOR L3. DEVIATION FROM BRIEF: the brief anticipated {L0,L1,L3,L5}, but the
    frozen fixture carries no TEMPORAL_OBJECT / AUTOMATION / temporal_state /
    snapshot.automation, so L3 is genuinely not demonstrated — the profile is
    {L0,L1,L5}. This makes the non-contiguity even starker (L5 without L2 *or*
    L3) and is asserted as the truth of the data.
    """
    p = profiles["logic"]
    assert p.reached_set == {0, 1, 5}
    assert not p.levels[2].reached  # no routing edges
    assert not p.levels[3].reached  # no timeline/automation in this bundle
    l5 = p.levels[5]
    assert l5.reached
    assert any("OBSERVATION" in e for e in l5.evidence)
    # A reached set that is not a prefix, and a headline that collapses it.
    assert p.highest_contiguous == 1


def test_logic_real_reaches_l5_via_observation(profiles):
    """logic_real: L5 reached via its single OBSERVATION entity."""
    p = profiles["logic_real"]
    assert 5 in p.reached_set
    assert p.reached_set == {0, 1, 5}
    assert any("OBSERVATION" in e for e in p.levels[5].evidence)


def test_effect_send_after_reaches_l6_only_with_context():
    """The effect-send `after` bundle: standalone it stops at L3; in an L6 context
    it reaches L5 (render supplied) and L6 (controlled intervention)."""
    after = load_bundle(EFFECT_SEND / "after")

    # Standalone (empty context): the bundle itself has no render / intervention.
    standalone = assess_bundle(after)
    assert standalone.reached_set == {0, 1, 2, 3}
    assert not standalone.levels[5].reached
    assert not standalone.levels[6].reached

    # In the experiment's L6 context: L5 + L6 light up from the context, not the
    # snapshot.
    comparison = build_effect_send_experiment(EFFECT_SEND)
    ctx = LadderContext(
        intervention=comparison.intervention,
        renders_present=comparison.acoustic_delta.available,
    )
    in_context = assess_bundle(after, context=ctx)
    assert in_context.reached_set == {0, 1, 2, 3, 5, 6}
    assert in_context.levels[6].reached
    assert in_context.levels[5].reached
    # L4 is not reached, so the contiguous headline stops at L3 even though L5/L6
    # are reached — the headline deliberately discards the profile's shape.
    assert in_context.highest_contiguous == 3


def test_assess_fixtures_injects_l6_member(all_profiles):
    """assess_fixtures walks the five adapters and injects the effect-send after."""
    by_name = {p.bundle_name: p for p in all_profiles}
    assert set(by_name) == {
        "reaper",
        "ableton",
        "cubase",
        "logic",
        "logic_real",
        "effect_send/after",
    }
    # Exactly one profile reaches L6: the injected experiment member.
    l6_reachers = [p.bundle_name for p in all_profiles if 6 in p.reached_set]
    assert l6_reachers == ["effect_send/after"]
    # The full reached-set map, asserted against reality.
    reached = {p.bundle_name: p.reached_set for p in all_profiles}
    assert reached == {
        "reaper": {0, 1, 2, 3},
        "ableton": {0, 1, 2, 3, 4},
        "cubase": {0, 1, 2, 3},
        "logic": {0, 1, 5},
        "logic_real": {0, 1, 5},
        "effect_send/after": {0, 1, 2, 3, 5, 6},
    }


# --- invariants -----------------------------------------------------------


def test_every_profile_has_seven_ordered_levels(all_profiles):
    for p in all_profiles:
        assert isinstance(p, LadderProfile)
        assert len(p.levels) == 7
        assert [a.level for a in p.levels] == [0, 1, 2, 3, 4, 5, 6]
        assert [a.title for a in p.levels] == [LEVEL_META[i][1] for i in range(7)]


def test_reached_sets_are_within_zero_to_six(all_profiles):
    for p in all_profiles:
        assert p.reached_set <= {0, 1, 2, 3, 4, 5, 6}
        # L0 is reached by every frozen fixture (all validate clean).
        assert 0 in p.reached_set


def test_provisional_only_on_l4(all_profiles):
    """Only L4 is a provisional rung today (scenes-only behavioral evidence)."""
    for p in all_profiles:
        for a in p.levels:
            if a.provisional:
                assert a.level == 4


def test_reached_levels_carry_evidence_unreached_carry_missing(all_profiles):
    for p in all_profiles:
        for a in p.levels:
            if a.reached:
                assert a.evidence, (p.bundle_name, a.level)
            else:
                assert a.missing, (p.bundle_name, a.level)


def test_markdown_renders_for_all_profiles(all_profiles):
    md = render_ladder_markdown(all_profiles)
    assert md.startswith("# Compatibility Ladder")
    # Every bundle is a column; every rung is a row.
    for p in all_profiles:
        assert p.bundle_name in md
    for level in range(7):
        assert f"L{level} {LEVEL_META[level][1]}" in md
    # The disclaimer and its cell legend are present.
    assert "Profiles, not rankings" in md
    assert "not a rank" in md
    assert "✓" in md and "·" in md and "~" in md
