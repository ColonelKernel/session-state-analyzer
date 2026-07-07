# parameter_change — a controlled parameter-tweak intervention (P9, generalized)

The second "state-to-audio" demonstration, and the one that generalizes the
experiment past routing: **one** plug-in parameter is moved on **one** session,
traced end to end from the state delta, through a readable signal-flow
explanation, to the measured change in the sound.

## The experiment

A controlled A/B built from a tiny synthetic REAPER session:

- **before/** (`routing_a`) — a "Lead Vox" track with a **Delay** processor
  whose **Feedback** parameter is **0.2**.
- **after/** (`routing_b`) — the *same* session with exactly one change: the
  Delay's Feedback parameter is **0.7**. Nothing else differs.

Semantic intervention (DAW-agnostic):

> Increase the delay feedback from 0.2 to 0.7.

Native (REAPER) implementation:

> Set the JS delay's `Feedback` parameter on the Lead Vox track from 0.2 to
> 0.7. REAPER JS-plugin parameters are host-visible, so this is the *observable*
> parameter path.

## The state delta (measured, not asserted)

`snapshot_delta(before, after)` over the two frozen bundles finds exactly one
`ParameterChange` and nothing else:

| | count | detail |
|---|---|---|
| **Parameter change** | 1 | `Feedback` (role **FEEDBACK**) `0.2 → 0.7` on PROCESSOR `reaper:fx-delay`, channel `reaper:track-vox:channel` |
| Added / removed entities | 0 | a pure in-place value change |
| Added / removed relationships | 0 | routing is untouched |
| Added sends | 0 | this is not a routing change |
| Changed (generic view) | 1 | the same `Feedback` PARAMETER entity (whose `value`/`normalized_value` differ) |

The owning processor and its channel are resolved by walking the inverse
`CONTAINS` (`kind=parameter`) edge to the PROCESSOR and the inverse
`CHANNEL_PROCESSED_BY` edge to the CHANNEL — nothing is hardcoded to this
fixture.

## The chain: state → signal-flow → acoustic

**State delta** → **Signal-flow explanation** (read from the entities):

> The FEEDBACK of the 'Delay' on the vocal channel rose 0.20→0.70 — more
> repeats feed back, so the vocal gains a longer tail.
>
> path: `Lead Vox → Delay`

→ **Acoustic delta** (the two renders' descriptors):

| metric | before (fb 0.2) | after (fb 0.7) | change |
|---|---|---|---|
| RMS level | 0.03109 | 0.05006 | **+4.1 dB** (louder) |
| Peak | 0.2607 | 0.3452 | +2.4 dB (louder) |
| Integrated loudness | −21.94 LUFS | −20.44 LUFS | +1.5 LUFS (louder) |

More feedback genuinely sustains more energy: the tail is longer and the
overall level rises on both RMS and gated loudness.

## Honest labelling (SYNTHETIC — same policy as `effect_send` / the Logic demo)

Both the canonical bundles **and** the renders are **SYNTHETIC fixtures**:

- The bundles are emitted by the *real* `flatten_session` + `validate_snapshot`
  (so they cannot drift from the v0.2 contract) from a hand-built nested
  `CanonicalSession`; only the one Feedback value differs between them.
- The renders are *real* audio (mono, 44.1 kHz, 88 200 samples): a broadband
  excitation through an overlapping feedback comb at feedback 0.2 vs 0.7,
  measured with the analyzer's own `extract_descriptors`. It is genuine audio
  that reflects the parameter change, but it is not a captured recording.

**Honesty note (preserved, not worked around):** Cubase VST3 plug-in parameters
are opaque — the same feedback change made in Cubase would be **HIDDEN**, not
readable from the exported files. This experiment therefore stands on the
REAPER-style *observable* JS-parameter path and is demonstrated synthetically.
A real REAPER `.rpp` parameter A/B is the Phase-4 stretch that replaces this.

## Contents

    before/    the routing_a canonical bundle (canonical.snapshot.json + validation.json)
    after/     the routing_b canonical bundle (canonical.snapshot.json + validation.json)
    renders/   routing_a.descriptors.json, routing_b.descriptors.json
               — extract_descriptors() output on the two (uncommitted) WAVs
    intervention.json   the Intervention record (semantic + REAPER native +
                        the honesty note + the two before/after Observations)
    make_inputs.py      regenerates every file above deterministically

The WAVs themselves are **not committed** (descriptors only, like `effect_send`
and `logic_real`).

## Reproduce

From the repo root, with the analyzer venv:

    .venv/bin/python fixtures/experiments/parameter_change/make_inputs.py

`session_explorer.interventions.build_parameter_experiment()` loads this fixture
and returns the full `InterventionComparison`.
