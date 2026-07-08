<!--
  GENERATED FILE — do not edit by hand.
  Regenerate with:
      .venv/bin/python -m session_explorer.compat.ladder
  (renders render_ladder_markdown(assess_fixtures()) over the frozen fixtures).
-->

# Compatibility Ladder

Each column is a **profile**, not a rank. A ladder records *what a bundle's data demonstrates*, rung by rung — it is not a leaderboard, and “higher” is not “better”.

| Rung | ableton | cubase | logic | logic_real | reaper | effect_send/after |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| L0 Loadable | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| L1 Structural | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| L2 Signal-flow | ✓ | ✓ | · | · | ✓ | ✓ |
| L3 Temporal | ✓ | ✓ | · | · | ✓ | ✓ |
| L4 Behavioral | ~ | · | · | · | · | · |
| L5 Acoustic-outcome-linked | · | · | ✓ | ✓ | · | ✓ |
| L6 Controlled intervention | · | · | · | · | · | ✓ |

Legend: `✓` reached · `~` reached (provisional, evidence base still growing) · `·` not reached.

| source.daw | ableton_live | cubase | logic_pro | logic_pro | reaper | cubase |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| reached set | {L0,L1,L2,L3,L4} | {L0,L1,L2,L3} | {L0,L1,L5} | {L0,L1,L5} | {L0,L1,L2,L3} | {L0,L1,L2,L3,L5,L6} |

## Rungs

- **L0 — Loadable**: The bundle parses and re-validates against the v0.2 contract with zero errors.
- **L1 — Structural**: Tracks plus their mixer channels or processors are recovered — the session's structure is present, not just a file that opened.
- **L2 — Signal-flow**: Routing relationships (sends, outputs, track->channel) connect the structure into a signal graph.
- **L3 — Temporal**: A timeline (temporal objects) and/or automation over time is present.
- **L4 — Behavioral**: Behavioral / performative state — scenes, modulation sources, or session variants — is present.
- **L5 — Acoustic-outcome-linked**: The captured state is tied to a rendered acoustic outcome (render / observation evidence).
- **L6 — Controlled intervention**: A controlled A/B pairs a known state change with its measured acoustic delta.

## Profiles, not rankings

The rungs are **independent measurements**, not a score to maximize. Real profiles are frequently non-contiguous: the synthetic Logic bundle reaches **L5** (its state is linked to a rendered acoustic outcome) yet never reaches **L2**, because its routing is carried as annotations rather than materialized as CHANNEL / routing edges. A bundle that reaches a lower rung is not “worse” than one that reaches a higher rung — the adapters observe different things. Read the whole reached set; the single-number `highest_contiguous` headline deliberately discards a profile's shape.

## Per-bundle evidence

### ableton  (`ableton_live`)  — reached {L0,L1,L2,L3,L4}

- `✓` **L0 Loadable**
    - re-validated against schema v0.2 with 0 errors (0 warning(s))
- `✓` **L1 Structural**
    - structure recovered: 6 TRACK, 9 CHANNEL, 22 PROCESSOR
- `✓` **L2 Signal-flow**
    - routing graph present: 6x TRACK_USES_CHANNEL
- `✓` **L3 Temporal**
    - timeline present: 12 TEMPORAL_OBJECT
- `~` **L4 Behavioral**
    - 3 scene container(s)
    - note: provisional rung: strengthens as variant-evolution / modulation data lands
- `·` **L5 Acoustic-outcome-linked**
    - missing: no RENDER / OBSERVATION entities and no render supplied
- `·` **L6 Controlled intervention**
    - missing: standalone bundle: no controlled intervention pairs this state with a known change

### cubase  (`cubase`)  — reached {L0,L1,L2,L3}

- `✓` **L0 Loadable**
    - re-validated against schema v0.2 with 0 errors (0 warning(s))
- `✓` **L1 Structural**
    - structure recovered: 5 TRACK, 7 CHANNEL, 8 PROCESSOR
- `✓` **L2 Signal-flow**
    - routing graph present: 1x CHANNEL_SENDS_TO, 6x CHANNEL_ROUTES_TO, 5x TRACK_USES_CHANNEL
- `✓` **L3 Temporal**
    - timeline present: 2 TEMPORAL_OBJECT
    - automation present: 1 AUTOMATION entity, 1 lane(s) in snapshot.automation
- `·` **L4 Behavioral**
    - missing: no scenes, MODULATION, or VARIANT entities; provisional rung: strengthens as variant-evolution / modulation data lands
- `·` **L5 Acoustic-outcome-linked**
    - missing: no RENDER / OBSERVATION entities and no render supplied
- `·` **L6 Controlled intervention**
    - missing: standalone bundle: no controlled intervention pairs this state with a known change

### logic  (`logic_pro`)  — reached {L0,L1,L5}

- `✓` **L0 Loadable**
    - re-validated against schema v0.2 with 0 errors (0 warning(s))
- `✓` **L1 Structural**
    - structure recovered: 8 TRACK, 6 PROCESSOR
- `·` **L2 Signal-flow**
    - missing: no routing relationships (CHANNEL_SENDS_TO, CHANNEL_ROUTES_TO, TRACK_USES_CHANNEL, SUMS_TO) — routing, if any, is annotated rather than materialized as edges
- `·` **L3 Temporal**
    - missing: no timeline (TEMPORAL_OBJECT / TIMELINE) or automation (AUTOMATION entities, snapshot.automation, temporal_state)
- `·` **L4 Behavioral**
    - missing: no scenes, MODULATION, or VARIANT entities; provisional rung: strengthens as variant-evolution / modulation data lands
- `✓` **L5 Acoustic-outcome-linked**
    - 2 OBSERVATION entity(ies)
- `·` **L6 Controlled intervention**
    - missing: standalone bundle: no controlled intervention pairs this state with a known change

### logic_real  (`logic_pro`)  — reached {L0,L1,L5}

- `✓` **L0 Loadable**
    - re-validated against schema v0.2 with 0 errors (0 warning(s))
- `✓` **L1 Structural**
    - structure recovered: 4 TRACK, 14 PROCESSOR
- `·` **L2 Signal-flow**
    - missing: no routing relationships (CHANNEL_SENDS_TO, CHANNEL_ROUTES_TO, TRACK_USES_CHANNEL, SUMS_TO) — routing, if any, is annotated rather than materialized as edges
- `·` **L3 Temporal**
    - missing: no timeline (TEMPORAL_OBJECT / TIMELINE) or automation (AUTOMATION entities, snapshot.automation, temporal_state)
- `·` **L4 Behavioral**
    - missing: no scenes, MODULATION, or VARIANT entities; provisional rung: strengthens as variant-evolution / modulation data lands
- `✓` **L5 Acoustic-outcome-linked**
    - 1 OBSERVATION entity(ies)
- `·` **L6 Controlled intervention**
    - missing: standalone bundle: no controlled intervention pairs this state with a known change

### reaper  (`reaper`)  — reached {L0,L1,L2,L3}

- `✓` **L0 Loadable**
    - re-validated against schema v0.2 with 0 errors (0 warning(s))
- `✓` **L1 Structural**
    - structure recovered: 9 TRACK, 9 CHANNEL, 22 PROCESSOR
- `✓` **L2 Signal-flow**
    - routing graph present: 3x CHANNEL_SENDS_TO, 1x CHANNEL_ROUTES_TO, 9x TRACK_USES_CHANNEL
- `✓` **L3 Temporal**
    - timeline present: 7 TEMPORAL_OBJECT
- `·` **L4 Behavioral**
    - missing: no scenes, MODULATION, or VARIANT entities; provisional rung: strengthens as variant-evolution / modulation data lands
- `·` **L5 Acoustic-outcome-linked**
    - missing: no RENDER / OBSERVATION entities and no render supplied
- `·` **L6 Controlled intervention**
    - missing: standalone bundle: no controlled intervention pairs this state with a known change

### effect_send/after  (`cubase`)  — reached {L0,L1,L2,L3,L5,L6}

- `✓` **L0 Loadable**
    - re-validated against schema v0.2 with 0 errors (0 warning(s))
- `✓` **L1 Structural**
    - structure recovered: 1 TRACK, 3 CHANNEL, 2 PROCESSOR
- `✓` **L2 Signal-flow**
    - routing graph present: 1x CHANNEL_SENDS_TO, 2x CHANNEL_ROUTES_TO, 1x TRACK_USES_CHANNEL
- `✓` **L3 Temporal**
    - timeline present: 1 TEMPORAL_OBJECT
- `·` **L4 Behavioral**
    - missing: no scenes, MODULATION, or VARIANT entities; provisional rung: strengthens as variant-evolution / modulation data lands
- `✓` **L5 Acoustic-outcome-linked**
    - experiment supplies a render of this state
- `✓` **L6 Controlled intervention**
    - participates in a controlled A/B intervention (known state change paired with its render)
