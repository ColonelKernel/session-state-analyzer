# Session State Analyzer

**Four observation instruments, one analysis contract.** The four DAW
session-state explorers (Ableton, REAPER, Logic, Cubase) remain independent
adapters in their own repositories; this repository is the analytical layer
that consumes their serialized exports. It contains no DAW parsing or
acquisition code. See `docs/PIVOT.md` for the architecture pivot and
`packages/canonical_snapshot/` for the v0.2 snapshot contract the adapters
emit.

The distribution is named `session-state-analyzer`; the import package stays
`session_explorer` through the transition (decision D1 in the pivot plan).

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
