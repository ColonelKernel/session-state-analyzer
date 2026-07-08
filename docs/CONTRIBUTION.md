# Session State Analyzer — the contribution

*Four observation instruments, one analysis contract.*

This document consolidates what the system is and why it matters, tying the
flagship demonstrations together. It cites, rather than repeats, the per-DAW
research material in [`docs/ableton`](ableton/), [`docs/cubase`](cubase/),
[`docs/logic`](logic/), [`docs/reaper`](reaper/) and the evaluation in
[`docs/evaluation.md`](evaluation.md).

## The research question

Not *"can four DAWs emit the same JSON?"* — that erases what makes them
different. The question is:

> Can music-production state be represented across creative systems with
> different ontologies and **unequal observability** — supporting comparison,
> explanation, and controlled experiment — without erasing DAW-native
> semantics or pretending hidden state is known?

## The architecture

Four independently built explorers (Ableton Live, Cubase, REAPER, Logic Pro)
are **observation instruments**, each with its own acquisition pathway:
Ableton via a Live extension, REAPER via `.rpp` parsing, Cubase via
DAWproject/`.cpr`, Logic via exported evidence (stems, MIDI, notes). They stay
in their own repositories. This repository is a **deliberately separate
analytical layer** that consumes their serialized exports through one
versioned, validated contract ([`docs/CONTRACT.md`](CONTRACT.md),
[`packages/canonical_snapshot`](../packages/canonical_snapshot/)) and contains
**no DAW parsing of its own**.

The contract is unified but **lossless**: a small canonical core (19 entity
concepts, a registry of relationship types) carries the shared semantics,
while every DAW-native detail rides in each entity's `native` payload and
namespaced `extensions`. Three orthogonal dimensions describe every value:
**evidence** (observed / inferred / annotated / hidden), **availability** (an
explicit exception ledger, never a silent null), and **source stability** (how
durable the capture pathway is). TRACK and CHANNEL are distinct entities;
"group" decomposes into containment, summing, and control rather than
collapsing into one word.

## The flagship demonstrations

**1 — Four instruments, one graph.** All five frozen snapshots render in one
canonical graph. The parser/export dialects (Ableton, REAPER, Cubase) draw in
type colours; the Logic evidence bundle visibly shifts to the *epistemic*
palette — inferred roles, annotated chains, hidden project state — showing the
same contract accommodating four different ways of knowing. *(fig01)*

**2 — X04 effect return.** The same production move — a vocal sent to a shared
reverb — captured in all four DAWs through their real export pipelines: an
Ableton Return Track, a Cubase FX Channel, a Logic Aux (via annotation), a
REAPER receive track. The explainable alignment engine (no embeddings) matches
the reverb-return entity across **all six DAW pairs at PROBABLE, mean
confidence ≈ 0.93**, each with human-readable reasons. Same strategy, four
native mechanisms, one analyzable representation. *(fig02)*

**3 — The Observability Atlas.** Ten state domains × the DAWs, each cell
*measured* from the actual snapshot (resolving the deduplicated provenance
store, not trusting declared capability). Read down a column and you see a
distinct epistemic profile: REAPER/Ableton parse cleanly; Cubase carries
visible hidden state; Logic is inference- and annotation-driven with channels
never observed. Modulation and (until recently) Automation rows stay visible
even when empty — the gap is data. *(fig03)*

**4 — State → audio.** A single controlled intervention, traced end to end:
one change to session state → a signal-flow explanation read from the graph →
an acoustic delta measured from two renders. The system now handles both a
routing change (add a reverb send: +5.6 dB RMS) and a **parameter** change
(delay feedback 0.2 → 0.7: +4.1 dB RMS, +1.5 LUFS). This is the bridge from
representation to sound. *(fig04)*

**5 — Adapter comparison + compatibility ladder.** The dashboard puts the four
instruments side by side as **profiles, not a ranking**: schema validity,
domain coverage, evidence mix, provenance completeness, capability, alignment
confidence, and a compatibility ladder (L0 loadable → L6 controlled
intervention). The ladder's sharpest result:

| DAW | reached rungs |
|---|---|
| REAPER | L0 · L1 · L2 · L3 |
| Ableton | L0 · L1 · L2 · L3 · L4 |
| Cubase | L0 · L1 · L2 · L3 |
| Logic | L0 · L1 · **L5** |

Logic reaches **L5 (acoustic-outcome-linked) without L2 (signal flow) or L3
(temporal)** — a reached set that is *not a prefix*. A DAW can be observable
about *sound* while opaque about *routing*. No single ordinal could express
that; the profile does. *(fig05, fig06)*

## Honesty as the method

Across every layer the same discipline holds: absence is stated, not hidden. A
degraded `.als`/`.cpr` capture yields a PROJECT-only snapshot with explicit
failures, never a fabricated session. The real Logic capture
([`fixtures/adapters/logic_real`](../fixtures/adapters/logic_real/), "Lincoln's
Come in Fives") demonstrates every evidence class on real material — including
an **honest negative** stem-sum reconciliation, where the exported stems
provably do *not* explain the bounce, and the system says so. Cubase VST3
plug-in parameters are opaque, so a real Cubase feedback change is reported as
hidden rather than guessed. The "profiles not ranks" framing, the exception
ledger, and the measured (not declared) atlas are all expressions of the same
commitment.

## Reproducibility

- **Contract & validation:** `packages/canonical_snapshot` (pydantic, schema
  v0.2, `validate_snapshot`).
- **Metrics export:** [`docs/METRICS.md`](METRICS.md) — machine-readable
  coverage, evidence ratios, provenance completeness, ladder reached-sets, and
  alignment confidences (aggregate over the four distinct-DAW adapters:
  195 observed / 10 inferred / 6 annotated / 22 hidden of 242 applicable).
- **Compatibility ladder:** [`docs/COMPATIBILITY_LADDER.md`](COMPATIBILITY_LADDER.md)
  — regenerated from `session_explorer.compat`.
- **Research dataset export:** `session_explorer.dataset_export.build_dataset`
  writes the §57 tree (snapshots / native / renders / observations /
  interventions / alignments / fixtures / metrics), descriptors only, with a
  blocking privacy leak-scan. Infrastructure for later ML; no model here.
- **Workbench:** `streamlit run src/session_explorer/workbench/app.py` — a
  Guided (plain-language) and an Expert (research) mode over the same
  computations.

## Figures

Figures are captured from the live workbench (preview on port 8792) into
`docs/figures/` and refreshed once the Phase-4 real captures land, so the
published figures show real rather than synthetic data:

| File | View (Expert mode) |
|---|---|
| `fig01_four_daw_graph.png` | Graph — all bundles, layer "all" |
| `fig02_x04_alignment.png` | X04 alignment — four-column native mechanisms |
| `fig03_observability_atlas.png` | Observability atlas — the grid |
| `fig04_state_to_audio.png` | State to audio — one intervention, three panels |
| `fig05_adapter_comparison.png` | Adapter comparison — per-DAW profiles |
| `fig06_compatibility_ladder.png` | Adapter comparison — the ladder rows |

Capture procedure: `preview_start("workbench")` → `preview_resize(1600×1000)` →
switch the sidebar Mode radio to **Expert** → for each figure, click the target
tab (snapshot-then-click; Streamlit tab ids are unstable) and
`preview_screenshot` to the filename above.
