# X06 — Grouping depth (routing / grouping / processing contract exhibit)

## Semantic intent

**One session that makes every P6 depth distinction visible at once: a native
"group" is not one concept, routing carries channels, feedback is legal, and a
processing chain has an order.**

Unlike X04 (which states a single production strategy realized four ways), X06
is a *contract exhibit*: it is **synthetic**, hand-authored to pack every
grouping-honesty and routing-depth case the flattener now distinguishes into a
single session, so the analyzer's new machinery (cycle detection, group
decomposition, the processing layer) has one dense fixture to run against.

## Honesty note

There is **no DAW behind this fixture**. Every value is hand-written to
exercise the contract, run through the *real* `flatten_session` +
`validate_snapshot` pipeline (`inputs/make_inputs.py`) so the frozen bundle can
never drift from the code that produces it. Its source stability is `MANUAL`
throughout and its capabilities are `UNTESTED` — it demonstrates the contract
*shape*, not a captured pathway. It is `synthetic`, and this file says so.

## What it exercises

| # | Case | Native construct | Wire shape |
|---|------|------------------|------------|
| 1 | Organizational-only folder | folder with `extras.organizational_only` + 2 children | `CONTAINS` only — **no** `SUMS_TO` |
| 2 | Group-channel bus | folder with `extras.group_channel_enabled` + 2 children | `CONTAINS` **and** `SUMS_TO` (+ group-sum `CHANNEL_ROUTES_TO`) |
| 3 | VCA / edit group | a track whose `controls` list scales two faders | `CONTROLS` (`kind=vca_or_edit_group`), **never** `SUMS_TO` |
| 4 | Channel'd sends | a stereo send (`source_channels=[0,1]`, `channel_count=2`) and a mono send (`[2]`, count 1) | routing edges carry `source_channels` / `target_channels` / `channel_count` / `channel_layout` **only where observed**; the feedback sends omit them (stereo-implicit) |
| 5 | Feedback pair | send A→B and send B→A | a routing **cycle** — data surfaced by `detect_cycles`, never a validation error |
| 6 | Branching processing | an FX channel with an EQ→Delay main chain and a parallel Saturator→Chorus chain | chain-scoped `PRECEDES` (main links, parallel links, **no** cross-chain edge); the channel branches into both chains |

## The point

`decompose_group` reads cases 1–3 back off the snapshot as distinct facets
(*contains* / *sums* / *controls* / *routes-in*), proving one native "group" is
several canonical concepts: the group bus is `is_multi_concept()` (contains +
sums), while the organizational folder (contains only) and the VCA (controls
only) are single-concept. `detect_cycles` turns case 5 into an annotatable
finding. The `processing` graph layer renders case 6 with its order intact.

## Regenerating

```
python fixtures/cross-daw/X06_grouping_depth/inputs/make_inputs.py
```
