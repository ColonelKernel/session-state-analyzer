# effect_send — a controlled state→audio intervention (P9)

The project's primary "state-to-audio" demonstration: **one** semantic change,
made to **one** session, traced end to end from the state delta, through a
readable signal-flow explanation, to the measured change in the sound.

## The experiment

A controlled A/B built from real material in the Cubase adapter repo
(`CubaseSessionStateExplorer`, `main @ eaa145f`):

- **before/** (`routing_a`) — a "Lead Vox" channel with a StudioEQ insert,
  routed straight to the Stereo Out. No sends.
- **after/** (`routing_b`) — the *same* session with exactly one change: a
  **post-fader send** added from the vocal channel to a shared **`FX 1 - Plate`**
  FX-return channel that carries a **REVerence** plate reverb and routes to the
  Stereo Out.

Semantic intervention (DAW-agnostic):

> Add a post-fader effect send from the vocal channel to a shared plate-reverb
> return.

Native (Cubase) implementation:

> `<Send destination="ch-fx1" type="post">` on the vox channel, feeding the
> `FX 1 - Plate` FX-return channel.

## The state delta (measured, not asserted)

`snapshot_delta(before, after)` over the two frozen bundles:

| | count | detail |
|---|---|---|
| **Added relationship** | 1 send | `CHANNEL_SENDS_TO` `Lead Vox → FX 1 - Plate` (post-fader) |
| Added relationships (support) | +2 | `FX 1 - Plate → REVerence` (processed-by), `FX 1 - Plate → Stereo Out` (routes-to) |
| Added entities | 2 | the `FX 1 - Plate` CHANNEL and the REVerence PROCESSOR the send points at |
| Removed | 0 | nothing removed — a pure addition |
| Changed (incidental) | 2 | the vocal track's `index` shifts 0→1 as the return channel is inserted; the PROJECT name/`source_file` differ (`routing_a` vs `routing_b`) |

The one added `CHANNEL_SENDS_TO` edge is the intervention; the two added
entities are simply the return it now points to. (`routing_a` has **zero**
`CHANNEL_SENDS_TO`; `routing_b` adds exactly one.)

## The chain: state → signal-flow → acoustic

**State delta** → **Signal-flow explanation** (read from the entities, not
hardcoded):

> The vocal channel now has a post-fader send to `'FX 1 - Plate'`, whose
> REVerence reverb sums back to the main output — so the vocal gains wet reverb
> it did not have before.
>
> path: `Lead Vox → FX 1 - Plate → REVerence → Stereo Out`

→ **Acoustic delta** (the two renders' descriptors):

| metric | before | after | change |
|---|---|---|---|
| RMS level | 0.0556 | 0.1057 | **+5.6 dB** (louder) |
| Peak | 0.277 | 0.732 | +8.4 dB (louder) |
| Spectral centroid | 332 Hz | 325 Hz | −6.9 Hz (slightly darker) |
| Integrated loudness | −23.9 LUFS | −17.3 LUFS | +6.6 LUFS (louder) |

Adding the reverb send genuinely raises the level and changes the spectrum: the
two renders are not identical (max abs sample diff ≈ 0.51).

## Honest labelling (same policy as the Logic synthetic demo)

The `.dawproject` inputs **and** their renders are **SYNTHETIC fixtures**: the
audio is fixture-generated, not printed from a human performance. It is real
audio (mono, 44.1 kHz, 88 200 samples) that genuinely reflects the routing
change, but it is not a captured recording. The whole chain is reproducible
from the Cubase adapter.

## Contents

    before/    the routing_a canonical bundle (5-file contract layout)
    after/     the routing_b canonical bundle (5-file contract layout)
    renders/   routing_a.descriptors.json, routing_b.descriptors.json
               — extract_descriptors() output on the two WAVs
    intervention.json   the Intervention record (semantic + Cubase native +
                        the two before/after Observations)

The WAVs themselves are **not committed** (descriptors only, like `logic_real`).

## Reproduce

From the Cubase adapter repo, re-export the two bundles and copy them here:

    cd CubaseSessionStateExplorer
    .venv/bin/python -m cubase_session_explorer.cli \
        export-canonical fixtures/cubase/routing_a.dawproject --out /tmp/ra
    .venv/bin/python -m cubase_session_explorer.cli \
        export-canonical fixtures/cubase/routing_b.dawproject --out /tmp/rb

Then, from this repo, extract the render descriptors from the two WAVs with
`session_explorer.core.audio.descriptors.extract_descriptors` (requires the
`audio` extra: `librosa`, `soundfile`, `pyloudnorm`).

`session_explorer.interventions.build_effect_send_experiment()` loads this
fixture and returns the full `InterventionComparison`; the workbench's
"State to audio" tab (both modes) renders it.
