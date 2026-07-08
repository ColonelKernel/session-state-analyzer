"""The Compatibility Ladder (Phase 3): honest per-bundle capability profiles.

Master-prompt §23 defines seven rungs, each a strictly stronger *claim about
what a bundle's data demonstrates* — from "it loads" (L0) to "a controlled
state change is paired with its measured acoustic outcome" (L6):

    L0  LOADABLE                 the snapshot re-validates with zero errors
    L1  STRUCTURAL               tracks + their channels or processors exist
    L2  SIGNAL-FLOW              routing edges connect the structure
    L3  TEMPORAL                 a timeline and/or automation over time exists
    L4  BEHAVIORAL               scenes / modulation / session variants exist
    L5  ACOUSTIC-OUTCOME-LINKED  the state is tied to a rendered outcome
    L6  CONTROLLED-INTERVENTION  a known state change is paired with an A/B

A rung is claimed **only when the bundle's actual data demonstrates it** — the
assessors read the snapshot, they do not trust the adapter's ambitions. Because
the rungs are independent measurements, a real profile is frequently
*non-contiguous*: the synthetic Logic bundle reaches L5 (acoustic outcome) yet
never reaches L2 (its routing is annotated, so no CHANNEL/routing edges exist).
That is the whole point.

**This module exposes a bundle's REACHED SET, never a single ordinal rank.**
:attr:`LadderProfile.highest_contiguous` exists only as a one-number headline;
the honest object is :attr:`LadderProfile.reached_set`. A ladder is a profile,
not a leaderboard: adapters observe different things, and "higher" is not
"better".

Every assessment is pure and evidence-bearing: a :class:`LevelAssessment`
carries the human-readable strings that justify ``reached`` (or the ``missing``
reason when it is not), plus optional ``refs`` (entity / relationship ids) for
drill-down. Rungs whose evidence base is still growing (L4 today) report
``provisional=True`` with a ``missing`` note, so a profile *degrades honestly*
now and *auto-upgrades* as later phases populate variant / modulation data.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional

from session_explorer.loaders.bundle import SnapshotBundle, load_bundle

# Repo-root-relative default: src/session_explorer/compat/ → parents[3].
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ADAPTERS_ROOT = _REPO_ROOT / "fixtures" / "adapters"
DEFAULT_EXPERIMENTS_ROOT = _REPO_ROOT / "fixtures" / "experiments"

# The routing relationships that constitute a signal graph (L2).
ROUTING_REL_TYPES: tuple[str, ...] = (
    "CHANNEL_SENDS_TO",
    "CHANNEL_ROUTES_TO",
    "TRACK_USES_CHANNEL",
    "SUMS_TO",
)

# The registry's ``scene`` concept surfaces on the wire as this native_type
# (see session_explorer.registry.concepts). Behavioral evidence (L4).
SCENE_WIRE_TYPES: tuple[str, ...] = ("scene",)


class LadderLevel(IntEnum):
    """The seven §23 rungs, low to high. Values double as the row index."""

    L0_LOADABLE = 0
    L1_STRUCTURAL = 1
    L2_SIGNAL_FLOW = 2
    L3_TEMPORAL = 3
    L4_BEHAVIORAL = 4
    L5_ACOUSTIC_OUTCOME_LINKED = 5
    L6_CONTROLLED_INTERVENTION = 6


# level -> (slug, title, description). The slug is a stable machine id; the
# title heads the markdown row; the description is the rung's §23 claim.
LEVEL_META: dict[int, tuple[str, str, str]] = {
    0: (
        "loadable",
        "Loadable",
        "The bundle parses and re-validates against the v0.2 contract with "
        "zero errors.",
    ),
    1: (
        "structural",
        "Structural",
        "Tracks plus their mixer channels or processors are recovered — the "
        "session's structure is present, not just a file that opened.",
    ),
    2: (
        "signal-flow",
        "Signal-flow",
        "Routing relationships (sends, outputs, track->channel) connect the "
        "structure into a signal graph.",
    ),
    3: (
        "temporal",
        "Temporal",
        "A timeline (temporal objects) and/or automation over time is present.",
    ),
    4: (
        "behavioral",
        "Behavioral",
        "Behavioral / performative state — scenes, modulation sources, or "
        "session variants — is present.",
    ),
    5: (
        "acoustic-outcome-linked",
        "Acoustic-outcome-linked",
        "The captured state is tied to a rendered acoustic outcome "
        "(render / observation evidence).",
    ),
    6: (
        "controlled-intervention",
        "Controlled intervention",
        "A controlled A/B pairs a known state change with its measured "
        "acoustic delta.",
    ),
}

_LEVEL_COUNT = len(LEVEL_META)


@dataclass
class LevelAssessment:
    """One rung's verdict for one bundle, with the evidence behind it.

    ``reached`` is the claim; ``evidence`` is the list of human-readable strings
    that justify it; ``missing`` states what is absent when ``reached`` is False
    (or, on a ``provisional`` rung, what would strengthen it). ``refs`` holds the
    entity / relationship ids the evidence points at, for drill-down. A
    ``provisional`` rung is one whose evidence base is still growing, so its
    verdict is honest-but-incomplete today and can auto-upgrade later.
    """

    level: int
    title: str
    reached: bool
    provisional: bool = False
    evidence: list[str] = field(default_factory=list)
    missing: Optional[str] = None
    refs: list[str] = field(default_factory=list)


@dataclass
class LadderProfile:
    """A bundle's full seven-rung profile — a *reached set*, never a rank.

    ``levels`` is always length 7, ordered L0..L6. The honest reading is
    :attr:`reached_set` (which rungs the data demonstrates);
    :attr:`highest_contiguous` is a one-number headline only, and deliberately
    collapses information a profile keeps.
    """

    daw: str
    bundle_name: str
    levels: list[LevelAssessment]

    @property
    def reached_set(self) -> set[int]:
        """The set of rung indices this bundle's data demonstrates."""
        return {a.level for a in self.levels if a.reached}

    @property
    def highest_contiguous(self) -> int:
        """Highest rung with every rung below it also reached (headline only).

        Returns ``-1`` when even L0 is not reached. This intentionally throws
        away the shape of a non-contiguous profile — use :attr:`reached_set`
        for anything but a one-line summary.
        """
        reached = self.reached_set
        highest = -1
        for level in range(_LEVEL_COUNT):
            if level in reached:
                highest = level
            else:
                break
        return highest


@dataclass
class LadderContext:
    """Experiment-level evidence a single bundle cannot carry on its own.

    A standalone adapter bundle knows nothing about renders or interventions;
    those live in an experiment that *pairs* bundles. This context supplies the
    L5 / L6 evidence for a bundle that participates in an experiment, without
    polluting the per-bundle assessors (which stay pure functions of the
    snapshot). ``intervention`` is the controlled change (any object; presence
    is what L6 checks); ``renders_present`` says a render of this state exists.
    """

    intervention: Optional[object] = None
    renders_present: bool = False


# --------------------------------------------------------------------------
# Small snapshot helpers (pure).
# --------------------------------------------------------------------------


def _type_counts(snapshot) -> Counter:
    return Counter(e.entity_type for e in snapshot.entities)


def _rel_types(snapshot) -> set[str]:
    return {r.rel_type for r in snapshot.relationships}


def _ids_of_type(snapshot, entity_type: str, limit: Optional[int] = None) -> list[str]:
    ids = [e.id for e in snapshot.entities if e.entity_type == entity_type]
    return ids if limit is None else ids[:limit]


def _scene_containers(snapshot) -> list:
    """STRUCTURAL_CONTAINER entities that are scenes (registry ``scene`` concept).

    Recognized by the wire native_type the registry maps the scene concept to,
    or by an explicit ``scene`` semantic role — either is honest scene evidence.
    """
    out = []
    for entity in snapshot.entities_of_type("STRUCTURAL_CONTAINER"):
        native_type = (entity.native.native_type or "") if entity.native else ""
        is_scene = native_type.lower() in SCENE_WIRE_TYPES or any(
            "scene" in role.lower() for role in entity.semantic_roles
        )
        if is_scene:
            out.append(entity)
    return out


# --------------------------------------------------------------------------
# Per-level pure assessors. Each returns a LevelAssessment with human evidence.
# --------------------------------------------------------------------------


def assess_l0(bundle: SnapshotBundle) -> LevelAssessment:
    """L0 LOADABLE: the analyzer's own load-time re-validation has no errors."""
    title = LEVEL_META[0][1]
    errors = list(bundle.validation.errors)
    if not errors:
        return LevelAssessment(
            level=0,
            title=title,
            reached=True,
            evidence=[
                "re-validated against schema v0.2 with 0 errors "
                f"({len(bundle.validation.warnings)} warning(s))",
            ],
        )
    return LevelAssessment(
        level=0,
        title=title,
        reached=False,
        evidence=[],
        missing=f"{len(errors)} validation error(s); first: {errors[0]}",
    )


def assess_l1(snapshot) -> LevelAssessment:
    """L1 STRUCTURAL: a TRACK plus at least one CHANNEL or PROCESSOR."""
    title = LEVEL_META[1][1]
    counts = _type_counts(snapshot)
    tracks = counts.get("TRACK", 0)
    channels = counts.get("CHANNEL", 0)
    processors = counts.get("PROCESSOR", 0)
    reached = tracks > 0 and (channels > 0 or processors > 0)
    if reached:
        parts = [f"{tracks} TRACK"]
        if channels:
            parts.append(f"{channels} CHANNEL")
        if processors:
            parts.append(f"{processors} PROCESSOR")
        refs = _ids_of_type(snapshot, "TRACK", limit=3)
        refs += _ids_of_type(snapshot, "CHANNEL", limit=3)
        refs += _ids_of_type(snapshot, "PROCESSOR", limit=3)
        return LevelAssessment(
            level=1,
            title=title,
            reached=True,
            evidence=[f"structure recovered: {', '.join(parts)}"],
            refs=refs,
        )
    missing = (
        "no TRACK entities" if tracks == 0
        else "TRACK present but no CHANNEL or PROCESSOR to give it a mixer path"
    )
    return LevelAssessment(level=1, title=title, reached=False, missing=missing)


def assess_l2(snapshot) -> LevelAssessment:
    """L2 SIGNAL-FLOW: any routing relationship connects the structure."""
    title = LEVEL_META[2][1]
    present = [rt for rt in ROUTING_REL_TYPES if rt in _rel_types(snapshot)]
    if present:
        refs: list[str] = []
        for rt in present:
            refs += [r.id for r in snapshot.relationships_of_type(rt)][:3]
        counts = {rt: len(snapshot.relationships_of_type(rt)) for rt in present}
        evidence = [
            "routing graph present: "
            + ", ".join(f"{n}x {rt}" for rt, n in counts.items())
        ]
        return LevelAssessment(
            level=2, title=title, reached=True, evidence=evidence, refs=refs
        )
    return LevelAssessment(
        level=2,
        title=title,
        reached=False,
        missing=(
            "no routing relationships "
            f"({', '.join(ROUTING_REL_TYPES)}) — routing, if any, is annotated "
            "rather than materialized as edges"
        ),
    )


def assess_l3(snapshot) -> LevelAssessment:
    """L3 TEMPORAL: a timeline and/or automation over time is present.

    Evidence distinguishes a *timeline* (TEMPORAL_OBJECT / TIMELINE entities)
    from *automation* (AUTOMATION entities or the flat ``snapshot.automation`` /
    ``snapshot.temporal_state`` payloads) — a bundle can have one without the
    other (REAPER: timeline, no automation; Cubase: both).
    """
    title = LEVEL_META[3][1]
    counts = _type_counts(snapshot)
    temporal_objects = counts.get("TEMPORAL_OBJECT", 0)
    timelines = counts.get("TIMELINE", 0)
    automation_entities = counts.get("AUTOMATION", 0)
    flat_automation = len(snapshot.automation)
    temporal_state = bool(snapshot.temporal_state)

    evidence: list[str] = []
    refs: list[str] = []
    if temporal_objects or timelines:
        bits = []
        if temporal_objects:
            bits.append(f"{temporal_objects} TEMPORAL_OBJECT")
        if timelines:
            bits.append(f"{timelines} TIMELINE")
        evidence.append("timeline present: " + ", ".join(bits))
        refs += _ids_of_type(snapshot, "TEMPORAL_OBJECT", limit=3)
        refs += _ids_of_type(snapshot, "TIMELINE", limit=3)
    if automation_entities or flat_automation:
        bits = []
        if automation_entities:
            bits.append(f"{automation_entities} AUTOMATION entity")
        if flat_automation:
            bits.append(f"{flat_automation} lane(s) in snapshot.automation")
        evidence.append("automation present: " + ", ".join(bits))
        refs += _ids_of_type(snapshot, "AUTOMATION", limit=3)
    elif temporal_state:
        evidence.append("temporal_state payload present")

    reached = bool(evidence)
    if reached:
        return LevelAssessment(
            level=3, title=title, reached=True, evidence=evidence, refs=refs
        )
    return LevelAssessment(
        level=3,
        title=title,
        reached=False,
        missing=(
            "no timeline (TEMPORAL_OBJECT / TIMELINE) or automation "
            "(AUTOMATION entities, snapshot.automation, temporal_state)"
        ),
    )


def assess_l4(snapshot) -> LevelAssessment:
    """L4 BEHAVIORAL: scenes, modulation sources, or session variants.

    Provisional: scenes are the only behavioral evidence any current adapter
    emits; modulation and variant population land in later phases, so this rung
    reports ``provisional=True`` and auto-strengthens as that data arrives.
    """
    title = LEVEL_META[4][1]
    counts = _type_counts(snapshot)
    scenes = _scene_containers(snapshot)
    modulation = counts.get("MODULATION", 0)
    variants = counts.get("VARIANT", 0)
    grow_note = (
        "provisional rung: strengthens as variant-evolution / modulation data "
        "lands"
    )

    evidence: list[str] = []
    refs: list[str] = []
    if scenes:
        evidence.append(f"{len(scenes)} scene container(s)")
        refs += [e.id for e in scenes][:3]
    if modulation:
        evidence.append(f"{modulation} MODULATION entity(ies)")
        refs += _ids_of_type(snapshot, "MODULATION", limit=3)
    if variants:
        evidence.append(f"{variants} VARIANT entity(ies)")
        refs += _ids_of_type(snapshot, "VARIANT", limit=3)

    if evidence:
        return LevelAssessment(
            level=4,
            title=title,
            reached=True,
            provisional=True,
            evidence=evidence,
            missing=grow_note,
            refs=refs,
        )
    return LevelAssessment(
        level=4,
        title=title,
        reached=False,
        provisional=True,
        missing=(
            "no scenes, MODULATION, or VARIANT entities; " + grow_note
        ),
    )


def assess_l5(snapshot, context: "LadderContext") -> LevelAssessment:
    """L5 ACOUSTIC-OUTCOME-LINKED: RENDER / OBSERVATION entities, or a render.

    A bundle earns L5 either by carrying RENDER / OBSERVATION entities itself
    (the Logic bundles reconcile stem sums as OBSERVATION entities) or by
    participating in an experiment that supplies a render of this exact state
    (``context.renders_present``).
    """
    title = LEVEL_META[5][1]
    counts = _type_counts(snapshot)
    renders = counts.get("RENDER", 0)
    observations = counts.get("OBSERVATION", 0)

    evidence: list[str] = []
    refs: list[str] = []
    if observations:
        evidence.append(f"{observations} OBSERVATION entity(ies)")
        refs += _ids_of_type(snapshot, "OBSERVATION", limit=3)
    if renders:
        evidence.append(f"{renders} RENDER entity(ies)")
        refs += _ids_of_type(snapshot, "RENDER", limit=3)
    if context.renders_present:
        evidence.append("experiment supplies a render of this state")

    reached = bool(evidence)
    if reached:
        return LevelAssessment(
            level=5, title=title, reached=True, evidence=evidence, refs=refs
        )
    return LevelAssessment(
        level=5,
        title=title,
        reached=False,
        missing="no RENDER / OBSERVATION entities and no render supplied",
    )


def assess_l6(context: "LadderContext") -> LevelAssessment:
    """L6 CONTROLLED-INTERVENTION: only when a controlled change is supplied.

    A standalone bundle can never reach L6 on its own — the rung is *about* the
    pairing of two states with a known change between them, which lives in an
    experiment context, not a single snapshot.
    """
    title = LEVEL_META[6][1]
    if context.intervention is not None:
        return LevelAssessment(
            level=6,
            title=title,
            reached=True,
            evidence=[
                "participates in a controlled A/B intervention "
                "(known state change paired with its render)"
            ],
        )
    return LevelAssessment(
        level=6,
        title=title,
        reached=False,
        missing=(
            "standalone bundle: no controlled intervention pairs this state "
            "with a known change"
        ),
    )


def assess_bundle(
    bundle: SnapshotBundle, *, context: LadderContext = LadderContext()
) -> LadderProfile:
    """Assess one bundle across all seven rungs into a :class:`LadderProfile`.

    Pure with respect to ``bundle`` and ``context`` — the same inputs always
    yield the same profile. ``context`` supplies experiment-level L5 / L6
    evidence; with the default (empty) context a bundle is judged purely on its
    own snapshot, which is how the standalone adapter fixtures are assessed.
    """
    snapshot = bundle.snapshot
    levels = [
        assess_l0(bundle),
        assess_l1(snapshot),
        assess_l2(snapshot),
        assess_l3(snapshot),
        assess_l4(snapshot),
        assess_l5(snapshot, context),
        assess_l6(context),
    ]
    return LadderProfile(
        daw=snapshot.source.daw,
        bundle_name=bundle.dir.name,
        levels=levels,
    )


def assess_fixtures(
    fixtures_root: Path | str = DEFAULT_ADAPTERS_ROOT,
    experiments_root: Path | str = DEFAULT_EXPERIMENTS_ROOT,
) -> list[LadderProfile]:
    """Profile every adapter fixture plus the effect-send experiment's L6 member.

    Walks ``fixtures_root`` (``fixtures/adapters/*``) assessing each standalone
    bundle with an empty context, then injects the effect-send experiment's
    ``after`` bundle assessed with an L6 context built from
    :func:`build_effect_send_experiment` — so the one bundle that *is* the tip of
    a controlled A/B is the one that reaches L6. Deterministic: sorted fixture
    order, everything read from disk.
    """
    root = Path(fixtures_root)
    profiles: list[LadderProfile] = []
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        if not (child / "canonical.snapshot.json").is_file():
            continue
        profiles.append(assess_bundle(load_bundle(child)))

    # Inject the effect-send experiment's `after` bundle with an L6 context.
    # Imported here to avoid a module-load dependency on the experiment fixture.
    from session_explorer.interventions.experiment import (
        build_effect_send_experiment,
    )

    effect_send_dir = Path(experiments_root) / "effect_send"
    after_dir = effect_send_dir / "after"
    if (after_dir / "canonical.snapshot.json").is_file():
        comparison = build_effect_send_experiment(effect_send_dir)
        context = LadderContext(
            intervention=comparison.intervention,
            renders_present=comparison.acoustic_delta.available,
        )
        profile = assess_bundle(load_bundle(after_dir), context=context)
        profile.bundle_name = "effect_send/after"
        profiles.append(profile)

    return profiles


# --------------------------------------------------------------------------
# Markdown rendering.
# --------------------------------------------------------------------------

# reached & solid / reached & provisional / not reached.
_CELL_REACHED = "✓"      # ✓
_CELL_PROVISIONAL = "~"
_CELL_NOT_REACHED = "·"  # ·


def _cell(assessment: LevelAssessment) -> str:
    if not assessment.reached:
        return _CELL_NOT_REACHED
    return _CELL_PROVISIONAL if assessment.provisional else _CELL_REACHED


def render_ladder_markdown(profiles: list[LadderProfile]) -> str:
    """Render a rungs x bundles reached-set table with definitions + disclaimer.

    The table is the profile matrix (one column per bundle); ``✓`` = reached,
    ``~`` = reached but provisional, ``·`` = not reached. Followed by the rung
    definitions and the load-bearing "profiles, not rankings" disclaimer.
    """
    lines: list[str] = []
    lines.append("# Compatibility Ladder")
    lines.append("")
    lines.append(
        "Each column is a **profile**, not a rank. A ladder records *what a "
        "bundle's data demonstrates*, rung by rung — it is not a leaderboard, "
        "and “higher” is not “better”."
    )
    lines.append("")

    # --- matrix -----------------------------------------------------------
    header = ["Rung"] + [p.bundle_name for p in profiles]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] + [":--:"] * len(profiles)) + "|")
    for level in range(_LEVEL_COUNT):
        slug, title, _desc = LEVEL_META[level]
        row_label = f"L{level} {title}"
        cells = [_cell(p.levels[level]) for p in profiles]
        lines.append("| " + " | ".join([row_label] + cells) + " |")
    lines.append("")
    lines.append(
        f"Legend: `{_CELL_REACHED}` reached · "
        f"`{_CELL_PROVISIONAL}` reached (provisional, evidence base still "
        f"growing) · `{_CELL_NOT_REACHED}` not reached."
    )
    lines.append("")

    # --- daw row for context ---------------------------------------------
    daw_header = ["source.daw"] + [p.daw for p in profiles]
    lines.append("| " + " | ".join(daw_header) + " |")
    lines.append("|" + "|".join(["---"] + [":--:"] * len(profiles)) + "|")
    lines.append(
        "| reached set | "
        + " | ".join(
            "{" + ",".join(f"L{i}" for i in sorted(p.reached_set)) + "}"
            for p in profiles
        )
        + " |"
    )
    lines.append("")

    # --- rung definitions -------------------------------------------------
    lines.append("## Rungs")
    lines.append("")
    for level in range(_LEVEL_COUNT):
        _slug, title, desc = LEVEL_META[level]
        lines.append(f"- **L{level} — {title}**: {desc}")
    lines.append("")

    # --- disclaimer -------------------------------------------------------
    lines.append("## Profiles, not rankings")
    lines.append("")
    lines.append(
        "The rungs are **independent measurements**, not a score to maximize. "
        "Real profiles are frequently non-contiguous: the synthetic Logic "
        "bundle reaches **L5** (its state is linked to a rendered acoustic "
        "outcome) yet never reaches **L2**, because its routing is carried as "
        "annotations rather than materialized as CHANNEL / routing edges. A "
        "bundle that reaches a lower rung is not “worse” than one that "
        "reaches a higher rung — the adapters observe different things. Read "
        "the whole reached set; the single-number "
        "`highest_contiguous` headline deliberately discards a profile's shape."
    )
    lines.append("")

    # --- per-bundle evidence ---------------------------------------------
    lines.append("## Per-bundle evidence")
    lines.append("")
    for profile in profiles:
        reached = ",".join(f"L{i}" for i in sorted(profile.reached_set))
        lines.append(
            f"### {profile.bundle_name}  (`{profile.daw}`)  — reached "
            f"{{{reached}}}"
        )
        lines.append("")
        for assessment in profile.levels:
            symbol = _cell(assessment)
            lines.append(f"- `{symbol}` **L{assessment.level} {assessment.title}**")
            for item in assessment.evidence:
                lines.append(f"    - {item}")
            if assessment.missing and not assessment.reached:
                lines.append(f"    - missing: {assessment.missing}")
            elif assessment.missing and assessment.provisional:
                lines.append(f"    - note: {assessment.missing}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------
# Regeneration entrypoint: writes docs/COMPATIBILITY_LADDER.md so the committed
# doc is byte-identical to render_ladder_markdown(assess_fixtures()).
# --------------------------------------------------------------------------

DEFAULT_DOC_PATH = _REPO_ROOT / "docs" / "COMPATIBILITY_LADDER.md"

_DOC_HEADER = (
    "<!--\n"
    "  GENERATED FILE — do not edit by hand.\n"
    "  Regenerate with:\n"
    "      .venv/bin/python -m session_explorer.compat.ladder\n"
    "  (renders render_ladder_markdown(assess_fixtures()) over the frozen "
    "fixtures).\n"
    "-->\n\n"
)


def render_ladder_document(profiles: Optional[list[LadderProfile]] = None) -> str:
    """The full committed doc: the generated-file header + the rendered ladder."""
    if profiles is None:
        profiles = assess_fixtures()
    return _DOC_HEADER + render_ladder_markdown(profiles)


def main() -> None:
    """Regenerate ``docs/COMPATIBILITY_LADDER.md`` from the frozen fixtures."""
    DEFAULT_DOC_PATH.write_text(render_ladder_document(), encoding="utf-8")
    print(f"wrote {DEFAULT_DOC_PATH}")


if __name__ == "__main__":
    main()
