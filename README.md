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
Guided mode and a research Expert mode); the four example sessions load on
first visit. The canonical schema lives in `packages/canonical_snapshot/`
(v0.2). Adapters: [REAPER](https://github.com/ColonelKernel/session-state-explorer-reaper),
[Cubase](https://github.com/ColonelKernel/session-state-explorer-cubase),
[Ableton](https://github.com/ColonelKernel/session-state-explorer-ableton),
[Logic](https://github.com/ColonelKernel/session-state-explorer-logic).

---

**New here? Start with the [User Manual](docs/MANUAL.md)** — install, run the
workbench, a tour of every tab (both modes), the Python API, and how a new
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

Adapters depend on `canonical-snapshot` via a git-subdirectory pin
(`@schema-v0.2.0` tag) or an editable path to `packages/canonical_snapshot`.

## Workbench

The Streamlit workbench renders adapter-exported bundles — it never parses a
DAW artifact. Install the UI extras and run the single entry point:

```
.venv/bin/pip install -e ".[ui]"
.venv/bin/python -m streamlit run src/session_explorer/workbench/app.py
```

The workbench has two modes, switched at the top of the sidebar (Guided is
the default):

### Guided mode (default)

A plain-language, story-first tour of the same data — no research vocabulary.
Five tabs:

- **Overview** — what the tool is, a "Load the four example sessions" button
  (the fixture bundles auto-load on first visit), and one card per DAW:
  session name, counts in plain words ("9 tracks · 22 effects · 4 routing
  connections"), and a mini "how much can we see?" bar with a one-line
  readout derived from the measured atlas mix (e.g. REAPER: "Read directly
  from the project file"; Logic: "Mostly reconstructed from exported audio
  and your notes — the DAW itself stays closed").
- **The same idea in four DAWs** — the X04 effect-return story: what each
  DAW calls the same mechanism ("What Ableton Live calls it: Return Track"),
  one friendly sentence per DAW pair with the match confidence and the top
  two reasons in plain words, and the full comparison table in an expander.
- **What each DAW lets us see** — the observability atlas with friendly row
  labels ("Tracks & layout", "Signal routing", …) and a plain-words legend
  (observed = "read directly", hidden = "exists but the DAW won't show it"),
  plus the expert drill-down behind a "Look closer" section.
- **Explore the graph** — the canonical graph with relabeled layers ("How
  things are organized" / "How audio flows" / "Everything").
- **What one change does to the sound** — the P9 state→audio experiment in
  plain language: we added a reverb send to a vocal, and the tab walks the
  three beats — what changed in the session, the path the vocal now travels
  ("Lead Vox → FX 1 - Plate → REVerence → Stereo Out"), and how much the sound
  changed (louder, with a wet tail) — with an honest note that the sessions
  and audio are synthetic fixtures.

A "What do these words mean?" glossary (evidence, availability, canonical vs
native, provenance) lives in the Guided sidebar. All Guided wording is in
`src/session_explorer/workbench/copy.py`.

### Expert mode

The research workbench, unchanged. The sidebar selects bundles (discovered
under `fixtures/adapters/`), the graph layer (`organizational` /
`signal_flow` / `all`), and the view:

- **Canonical** — five tabs: *Graph* (all selected snapshots side by side in
  one canonical graph, coloured by entity type with observability overriding
  where a value is inferred/annotated/hidden); *Entity inspector* (one
  entity, three panels: canonical / native / evidence — every value traceable
  to its provenance record, every unobservable field stated); *X04 alignment*
  (one production strategy, four native mechanisms, aligned); and
  *Observability atlas* (the P5 flagship — measured per-domain observability
  across the loaded DAWs as ten canonical domains × N columns, each cell a
  stacked observed/inferred/annotated/hidden/unsupported bar with direct,
  recovered, and hidden ratios. Click a domain × DAW to drill into the exact
  entities and fields behind the numbers beside the adapter's *declared* read
  capability; an unknown-state map per DAW categorizes everything a snapshot
  admits it cannot see. Modulation, and Native Features where a DAW ships no
  extension payload, render NOT_APPLICABLE — the gaps are shown, not hidden);
  and *State to audio* (the P9 controlled intervention: one semantic change —
  a post-fader vocal→plate-reverb send — traced from the state delta, through
  the signal-flow explanation and its path chain, to the acoustic delta
  between the two renders. Loaded from `fixtures/experiments/effect_send`; the
  inputs and renders are synthetic fixtures, reproducible via the Cubase
  adapter).
- **Native** — the bundle's verbatim `native.json` beside the registry's
  per-DAW presentation vocabulary.
- **Evidence** — the deduplicated provenance store as a table, plus the
  adapter's warnings and failures.

## Tests

```
.venv/bin/python -m pytest tests/core tests/analyzer packages/canonical_snapshot/tests
```

(`tests/drivers/` is being relocated into the adapter repositories; see
`docs/PIVOT.md`.)
