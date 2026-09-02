# Session State Analyzer

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://session-state-analyzer-n2lj2kmjjijdzta7oarpyt.streamlit.app/)

**[Live demo](https://session-state-analyzer-n2lj2kmjjijdzta7oarpyt.streamlit.app/)** — the two-mode workbench with all six example sessions preloaded, no install needed.

> **A DAW session is a structured record of creative intent — thousands of
> decisions about tracks, effect chains, routing, and automation that together
> produce a sound. This project represents that state in a single, open,
> DAW-agnostic form, measures how much of it each DAW actually lets you see,
> and traces how a change to the state changes the audio.**

Music-information-retrieval datasets almost always hold only the *rendered
audio* — never the session that produced it. Session State Explorer takes the
other side of the problem. Four per-DAW adapters (**Ableton, REAPER, Logic,
Cubase**) each read a session and serialize it to one shared **canonical
snapshot** schema; this repository is the analytical layer over those
snapshots. Two results are worth 30 seconds:

### 1 · The observability atlas — what each DAW will and won't tell you

Every value in a snapshot carries its own **evidence** tag, so partial
observability is a first-class, queryable fact rather than a missing field:

| Evidence | Meaning |
|---|---|
| **observed** | read directly from the project |
| **inferred** | reconstructed from exported audio, MIDI, or notes |
| **annotated** | supplied by the user |
| **hidden** | exists, but the DAW won't expose it |
| **unsupported** | the mechanism doesn't exist in this DAW |

The atlas rolls this up across ten canonical domains (tracks & layout, signal
routing, effects, automation, …) for all four DAWs at once. The DAWs land in
very different places — REAPER's `.rpp` is read almost entirely **directly**;
Logic's project is opaque, so its state is largely **reconstructed** from
exported stems, MIDI, MusicXML, and channel-strip notes, with everything it
cannot recover marked **hidden** rather than silently dropped. The gaps are the
point, and they are shown, not hidden.

### 2 · State → audio — one change, measured

A controlled intervention adds a single post-fader send (a lead vocal into a
plate reverb) and traces it end to end: the **state delta** (the new routing
edge), the **signal-flow path** it creates
(`Lead Vox → FX 1 · Plate → REVerence → Stereo Out`), and the **acoustic
delta** measured between the two renders (louder, with a wet tail). It is a
small, reproducible template for the core question behind assistive music
production — *how does a change to the session change the sound?*

Everything above is browsable in the **Streamlit workbench** (a plain-language
Guided mode and a research Expert mode); the six example sessions load on
first visit — one per adapter, plus a real captured session for Logic and for
REAPER alongside their synthetic ones. The canonical schema lives in `packages/canonical_snapshot/`
(v0.2). Adapters: [REAPER](https://github.com/ColonelKernel/session-state-explorer-reaper),
[Cubase](https://github.com/ColonelKernel/session-state-explorer-cubase),
[Ableton](https://github.com/ColonelKernel/session-state-explorer-ableton),
[Logic](https://github.com/ColonelKernel/session-state-explorer-logic).

---

**New here? Start with the [User Manual](docs/MANUAL.md)** — install, run the
workbench, a tour of every page (both modes), the Python API, and how a new
session becomes a bundle. This repository contains no DAW parsing code; see
`docs/PIVOT.md` for the architecture and `packages/canonical_snapshot/` for the
v0.2 contract the adapters emit. The distribution is `session-state-analyzer`;
the import package stays `session_explorer` (decision D1 in the pivot plan).

## Development setup

The contract package is a standalone pip package vendored as a subdirectory
(no sixth repo, decision D3). Dev setup installs both editable:

```
python -m venv .venv
.venv/bin/pip install -e packages/canonical_snapshot -e ".[dev]"
```

Adapters depend on `canonical-snapshot` from this repo, pinned by git
subdirectory at the contract tag:

```
pip install "canonical-snapshot @ git+https://github.com/ColonelKernel/session-state-analyzer@schema-v0.2.0#subdirectory=packages/canonical_snapshot"
```

An editable path to `packages/canonical_snapshot` works too. The tag moves only
when the wire contract changes, so a pinned adapter keeps building against the
schema it was written for.

## Workbench

The Streamlit workbench renders adapter-exported bundles — it never parses a
DAW artifact. Install the UI extras and run the single entry point:

```
.venv/bin/pip install -e ".[ui]"
.venv/bin/python -m streamlit run src/session_explorer/workbench/app.py
```

Navigation is a sidebar table of contents (`st.navigation`); a **Mode** radio
switches the *wording* of the page tree, not the tree itself. Switching mode
stays on the same page — re-worded — and every exhibit is deep-linkable from
the live demo. Shared pages keep the same address in both modes, with one
exception: the graph page is Expert's home, so its address there is `/`
(Guided: `/graph`).

### Guided mode (default)

A plain-language, story-first tour — no research vocabulary. Eight pages, in
tour order:

- **Overview** (`/`) — what the tool is, one card per loaded session (plain
  entity counts, a "how much can we see?" mini bar with a one-line readout
  derived from the measured atlas mix), and the load-all affordance when
  something is deselected.
- **The same idea in four DAWs** (`/same-idea`) — the effect-return story:
  what each DAW calls the same mechanism, one friendly sentence per DAW pair
  with match confidence, and the full comparison table in an expander.
- **What each DAW lets us see** (`/atlas`) — the observability atlas with
  friendly row labels and a plain-words legend, plus the plain-language
  drill-down under "Look closer".
- **Explore the graph** (`/graph`) — the canonical graph with relabeled
  layers ("How things are organized" / "How audio flows" / "Everything").
- **Groups & feedback** (`/routing-depth`) — what a native "group" fuses
  (containment, summing, VCA control, incoming routing), split into four
  plain columns, plus the feedback-loop explanation.
- **What one change does to the sound** (`/state-to-audio`) — the state→audio
  experiment in plain language, with a selector for either frozen experiment
  (reverb send or delay feedback), walking three beats: what changed, the
  path the signal travels, how the sound changed.
- **How a song evolved** (`/evolution`) — a variant family, its lineage
  graph, and a diff of each adjacent pair.
- **How the DAWs compare** (`/comparison`) — the per-DAW profiles dashboard
  in plain words. Explicitly *not* a ranking.

A "What do these words mean?" glossary lives in the Guided sidebar. All
Guided wording is in `src/session_explorer/workbench/copy.py`.

### Expert mode

The research workbench: eleven pages in two sidebar sections — the shared
pages re-worded (Overview is Guided-only) plus four Expert-only pages. The
sidebar gains the **Bundles** multiselect (discovered under
`fixtures/adapters/`).

- **Canonical:** *Graph* (`/`; the layered canonical graph with the
  graph-layer radio and per-observability-class filters) · *Entity inspector*
  (`/inspector`) · *X04 alignment* (`/same-idea`) · *Observability atlas*
  (`/atlas`) · *State to audio* (`/state-to-audio`) · *Routing depth*
  (`/routing-depth`) · *Parameter influence* (`/parameter-influence`) ·
  *Session evolution* (`/evolution`) · *Adapter comparison* (`/comparison`).
- **Source:** *Native payload* (`/native`) — the bundle's verbatim
  `native.json` beside the registry's presentation vocabulary · *Evidence*
  (`/evidence`) — the deduplicated provenance store plus the adapter's
  warnings and failures.

### Deep links

Every page above is addressable by its path. Guided is the default; append
`?mode=expert` to open a shared page in research wording (the mode radio
keeps the URL in sync), and Expert-only paths imply Expert on their own. One
exception: the graph page in Expert is the home page, so link it as
`/?mode=expert` — `/graph?mode=expert` shows a "Page not found" notice before
falling back to it (Streamlit drops a default page's path). The page registry
lives in `src/session_explorer/workbench/nav.py`.

## Tests

```
.venv/bin/python -m pytest tests/core tests/analyzer packages/canonical_snapshot/tests
```

(The former `tests/drivers/` suite now lives in the adapter repositories; see
`docs/PIVOT.md`.)
