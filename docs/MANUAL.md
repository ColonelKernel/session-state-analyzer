# Session State Analyzer — User Manual

> Contract data version: **v0.2** (`canonical-snapshot 0.2.0`). Analyzer distribution `session-state-analyzer 1.0.0`; import package `session_explorer`.

---

## 1. What this is

The Session State Analyzer is the analytical layer of a **"four observation instruments, one analysis contract"** research program. Four independently built DAW explorers — Ableton Live, Cubase, REAPER, and Logic Pro — each live in their **own** repositories as observation instruments (adapters), and each emits its findings through one versioned, validated snapshot contract (the v0.2 `CanonicalDAWSnapshot`). **This** repository consumes those exported bundles and contains **no DAW parsing or acquisition code of its own** — it only analyzes, compares, and visualizes what the adapters observed.

For the full research framing and why it matters, see [`docs/CONTRIBUTION.md`](CONTRIBUTION.md).

---

## 2. Install & first run

Requires Python `>=3.10` (verified on 3.13). Run everything from the analyzer repo root.

**Two-package editable install** — the analyzer plus the vendored contract package (`packages/canonical_snapshot`, a subdirectory, not a separate repo):

```
python -m venv .venv
.venv/bin/pip install -e packages/canonical_snapshot -e ".[dev]"
```

Add the workbench (UI) extras:

```
.venv/bin/pip install -e ".[ui]"
```

Launch the workbench and open the URL Streamlit prints:

```
.venv/bin/python -m streamlit run src/session_explorer/workbench/app.py
```

Or launch headless on a fixed port (matches `.claude/launch.json`, port **8792**):

```
.venv/bin/python -m streamlit run src/session_explorer/workbench/app.py --server.headless true --server.port 8792
```

Verify the two packages imported cleanly:

```
.venv/bin/python -c "import session_explorer, canonical_snapshot; print('imports OK')"
```

**Notes / caveats**
- Install extras **explicitly** (`.[ui]`, `.[audio]`, `.[midi]`, `.[score]`). Do **not** use `.[full]` — that extra is malformed and resolution will fail.
- There is **no working command-line entry point**. The packaged `session-explorer` script is broken; the only supported entry point is the Streamlit workbench (plus the two regeneration modules in §7 and the Python API in §6).
- The workbench auto-discovers bundles under `fixtures/adapters/` — no configuration needed on first run.

Run the tests (optional):

```
.venv/bin/python -m pytest tests/core tests/analyzer packages/canonical_snapshot/tests
```

---

## 3. The workbench

### Two modes

A **Mode** radio in the sidebar switches between **Guided** (default) and **Expert**.

- **Guided** — a plain-language tour. It auto-loads every discovered bundle on first visit and renders eight friendly tabs.
- **Expert** — the research workbench. Adds a **View** radio (`Canonical` [default] · `Native` · `Evidence`), a **Graph layer** radio (`organizational` · `signal_flow` · `processing` · `automation` · `variant` · `all` [default]), and a **Bundles** multiselect.

Both modes share the same loaded-bundle selection, so switching modes keeps your data. **The nine Expert tabs below appear only under the Canonical view** — switching View to Native or Evidence replaces the tabs with a single payload/provenance pane.

### Expert tabs (Canonical view, in order)

1. **Graph** — *(flagship: the four-DAW graph)* all loaded snapshots as one layered, namespaced graph; nodes colored by observability (falling back to entity type), with per-observability-class checkboxes and a legend. When routing feedback exists, a **cycle badge** warns "Feedback loop detected: N cycle(s)…" — framed as *a finding, not an error* — with an expander listing each ring as `A → B → … → A`.
2. **Entity inspector** — pick a bundle, then an entity (grouped by type); see it three ways side by side: Canonical (properties + availability), Native (DAW-native identity), Evidence (per-field provenance table).
3. **X04 alignment** — *(flagship)* one production strategy (a vocal → shared-reverb effect return) shown as four native mechanisms across four DAWs, plus the pairwise alignment table over the six DAW pairs, each claim with its reasons.
4. **Observability atlas** — *(flagship)* a 10-domain × loaded-DAW grid of stacked epistemic-mix bars, a click-to-drill domain × DAW panel (measured vs. declared capability), and a per-DAW unknown-state map.
5. **State to audio** — *(flagship)* one controlled A/B in three panels (state change → signal-flow explanation → acoustic delta before/after). An **Experiment** radio selects `Effect send` or `Delay feedback`.
6. **Routing depth** — group decomposition (one native "group" fanned into **Contains / Sums in / Controls (VCA) / Routes in**, with a multi-concept finding badge) plus the ordered per-channel processing chain.
7. **Parameter influence** — for one parameter or automated field: base value, automation lane, modulation source, and an honest effective value reported as a **range** (never a value at instant *t*).
8. **Session evolution** — a variant family's lineage graph and the diff of each adjacent version pair. A **Version family** selectbox chooses the family. Degrades to an info note when the variants module/fixtures are absent.
9. **Adapter comparison** — *(flagship: the ladder)* every loaded DAW as a column, eight measurable facets as rows (schema, coverage, evidence mix, provenance, conformance, compatibility ladder, declared capability, alignment confidence). Explicitly **"profiles, not a ranking,"** with metrics/ladder downloads.

### Guided tabs (in order)

1. **Overview** — a "Load all example sessions" button and one friendly card per DAW (session name, plain entity counts, a "How much can we see?" mini evidence bar).
2. **The same idea in four DAWs** — the X04 effect-return story in plain words, with an expander for the full comparison table.
3. **What each DAW lets us see** — the observability atlas with friendly labels and per-cell captions ("X read directly · Y pieced together · Z locked away").
4. **Explore the graph** — the canonical graph with a plain-language layer picker (default "Everything"). Reuses the Graph view, so the same feedback-loop cycle badge can appear here.
5. **Groups & feedback** — group decomposition in plain columns (**Holds these tracks / Mixes these together / Controls the level of / Receives audio from**) plus a section explaining feedback loops.
6. **What one change does to the sound** — the intervention A/B in three plain beats. A "Which experiment?" radio selects `Reverb send` or `Delay feedback`.
7. **How a song evolved** — the variant lineage plus step-by-step diffs, plain framing.
8. **How the DAWs compare** — the Adapter comparison dashboard with plain-language row questions and "not a scoreboard" framing.

---

## 4. Core concepts

Enough to read the UI; full depth is in [`docs/CONTRACT.md`](CONTRACT.md).

**The contract.** Every adapter must emit a `CanonicalDAWSnapshot` (v0.2). A small canonical core — **19 entity concepts** plus a **relationship-type registry** — carries shared semantics; all DAW-native detail rides in each entity's `native` payload and namespaced `extensions`. Schema changes are **additive-only** within 0.2; anything else bumps the version and the analyzer refuses loudly rather than silently.

**Three separated epistemic dimensions.** These are what the observability views color and count:
- **Evidence** — how a value entered the system: `OBSERVED`, `INFERRED`, `ANNOTATED`, `HIDDEN`.
- **Availability** — whether the state could be had at all (an exception ledger; entities record only non-available fields, never a silent null): `AVAILABLE`, `NOT_PRESENT`, `INACCESSIBLE`, `UNSUPPORTED`, `NOT_APPLICABLE`, `PARSE_ERROR`, `REDACTED`, `UNKNOWN`.
- **Source stability** — how fragile the capture pathway was, best → worst: `OFFICIAL_DOCUMENTED`, `OFFICIAL_EXPORT`, `SUPPORTED_INTEGRATION`, `COMMUNITY_DOCUMENTED`, `REVERSE_ENGINEERED`, `UI_AUTOMATION`, `HEURISTIC`, `MANUAL`. (A value can be `OBSERVED` through a fragile method — both truths are recorded.)

**TRACK ≠ CHANNEL.** A `TRACK` owns content/arrangement; a `CHANNEL` owns signal flow/mixer state; they are linked by `TRACK_USES_CHANNEL`. A dialect that cannot observe channels (e.g. Logic evidence) conforms by emitting TRACK-only entities with `availability: {channel: UNKNOWN}` — the conformance suite rejects *silent omission*, not honest ignorance.

**The bundle 5-file layout.** One export = one directory:
- `canonical.snapshot.json` — the `CanonicalDAWSnapshot` (required)
- `native.json` — the adapter's full native model dump (referenced by path + sha256 from `extensions[daw].native_file`; required *or* an explicit `native_payload_omitted`)
- `capabilities.json` — the `CapabilityManifest` (read/write/live-observation/render capability, per-domain)
- `adapter_descriptor.json` — adapter id, DAW, capture modes, known limitations
- `validation.json` — the adapter's own validation report at export time (the analyzer revalidates on load regardless)

> Synthetic contract-exhibit bundles legitimately omit `native.json` under the `native_payload_omitted` allowance (see §5). The strict five-file layout holds for the real adapter bundles, the X04 bundles, and the effect_send experiment.

---

## 5. Working with data

### Fixtures inventory

Under `fixtures/`:

**`fixtures/adapters/*`** — the five frozen reference bundles the conformance suite and workbench treat as inputs:
- **`ableton`** — synthetic/demo-derived input through the real Ableton adapter. Shows **TRACK ≠ CHANNEL** (6 TRACK vs. 9 CHANNEL).
- **`cubase`** — synthetic `.dawproject` through the real DAWproject pipeline (`OFFICIAL_EXPORT`); hidden plug-in params surface as `INACCESSIBLE`. Carries one real automation lane (vocal Volume).
- **`logic`** — synthetic audio through the real Logic **evidence** pipeline; showcases `INFERRED`/`ANNOTATED`/`HIDDEN` and availability, with TRACK-only entities (`channel: UNKNOWN`). No Logic project file is ever read.
- **`logic_real`** — the **only real captured session** ("Lincoln's Come in Fives"). Demonstrates every evidence class on real material, including an honest negative `OBSERVATION` (stems barely explain the bounce). Metadata/descriptors only; audio not committed. The real-capture flagship.
- **`reaper`** — synthetic 9-track demo `.rpp` through the real `.rpp` parser.

**`fixtures/cross-daw/*`** — intent-defined, capture-replaceable:
- **`X04_effect_return`** — the **flagship** alignment fixture: one intent (vocal → shared reverb return → main out) realized four ways (Ableton Return Track, Cubase FX Channel, REAPER receive track, Logic aux — annotated, never observed). Full 5-file bundles for all four DAWs; the alignment engine matches the reverb return across all six DAW pairs.
- **`X06_grouping_depth`** — synthetic contract exhibit (no `native.json`) packing every routing-depth distinction (organizational folder, group-channel bus, VCA/edit group, channel'd sends, a feedback cycle, a branching processing chain) into one dense session.

**`fixtures/experiments/*`** — controlled state→audio A/B interventions:
- **`effect_send`** — the primary state→audio demo (Cubase A/B, real material): adding one post-fader reverb send. Full before/ + after/ bundles, render descriptors, `intervention.json`. WAVs not committed.
- **`parameter_change`** — a synthetic REAPER A/B changing one delay Feedback parameter (0.2 → 0.7). Ships only `canonical.snapshot.json` + `validation.json` per side.

**`fixtures/variants/*`** — a synthetic `demo_song` variant family (`v1`, `v2`, `v2_alpha`, `v3`) for the session-evolution analyzer (no `native.json`).

**`fixtures/modulation/`** — a single synthetic exhibit (a kick sidechaining a bass channel) that gives the Observability Atlas Modulation row one measurable cell.

### How a new real session becomes a bundle

1. **In the adapter's own repo**, install the contract package and run that adapter's `export-canonical` CLI over an input artifact. Exports must be **deterministic** (reset id counters, derive `created_at` from the input, content-hash the `snapshot_id`) so re-exporting the same input yields byte-identical bundles.
2. **Freeze the five files** verbatim into `fixtures/adapters/<name>/` in this repo (regenerate from the adapter repo; never hand-edit).
3. The workbench **auto-discovers** it — any child directory of `fixtures/adapters/` containing a `canonical.snapshot.json` is loaded. No registration list to edit. (Cache is keyed on path + snapshot mtime, so editing a fixture invalidates just that entry without a restart.)

> Caveat: while the workbench discovers bundles dynamically, several tests (`tests/analyzer/test_conformance.py`, `test_workbench_modes.py`, `test_dataset_export.py`, `test_ladder.py`, `test_metrics.py`, `test_atlas.py`, `test_graph_layers.py`) hard-code the current fixture set and counts. Adding or removing a bundle requires updating those tests for CI to pass.

### Adapter `export-canonical` commands

Each adapter requires the `canonical-snapshot` contract package, installed editable from this repo's `packages/canonical_snapshot`. **Ableton** and **REAPER** expose it as a `canonical` extra (`pip install -e ".[canonical]"` in those repos); **Logic** and **Cubase** have no such extra, so install the contract package directly there (`pip install -e <path-to>/packages/canonical_snapshot`). All four emit the shared 5-file bundle. The four adapters are sibling repositories.

**Ableton** (`AbletonSessionStateExplorer`) — no console script; invoke as a module:

```
python -m ableton_session_state_explorer export-canonical <session.json|set.als> --out exports/ableton --source session_json
```

`--source` is `{extension_json, session_json}` (default `session_json`); `--out` defaults to `exports/canonical`.

**REAPER** (`SessionStateExplorerReaper`) — console script `sse-reaper`:

```
sse-reaper export-canonical <project.rpp> --out exports/reaper [--audio-base DIR] [--no-sanitize]
```

`--out` is **required**.

**Logic** (`LogicSessionStateExplorer`) — console script `logic-session-evidence-explorer`. **The verb differs**: `export-canonical-bundle`:

```
logic-session-evidence-explorer export-canonical-bundle <folder|manifest.json|demo|demo-full> --out exports/logic [--notes notes.csv] [--no-sanitize]
```

`--out` defaults to `exports/canonical`; the positional accepts an evidence folder, a session manifest `.json`, or the literals `demo` / `demo-full`.

**Cubase** (`CubaseSessionStateExplorer`) — console script `cubase-explorer`:

```
cubase-explorer export-canonical <input> --out exports/cubase [--no-sanitize]
```

`--out` is **required**.

---

## 6. The analytical tools as a Python API

For scripted / headless use. Run from the repo root with the venv interpreter (`.venv/bin/python`). DAW ids are snake_case: `ableton_live`, `cubase`, `logic_pro`, `reaper`. Verified outputs are shown as `#` comments.

### Load a bundle

```python
from session_explorer.loaders.bundle import load_bundle
b = load_bundle("fixtures/adapters/logic")
print(b.snapshot.source.daw, len(b.snapshot.entities), not b.validation.errors, b.native is not None)
# -> logic_pro 30 True True
```

`load_bundle(path)` requires `canonical.snapshot.json` (else `FileNotFoundError`); sidecars are tolerated. Also available from `session_explorer.loaders`: `load_snapshot`, `SnapshotBundle`, and the presentation registry (`get_presentation`, `known_daws`).

### Observability atlas

```python
from session_explorer.atlas import build_atlas, measure_domain, unknown_state_map, get_domain
from session_explorer.atlas.coverage import aggregate_mix   # NOT re-exported by atlas/__init__
bundles = [load_bundle(f"fixtures/adapters/{d}") for d in ("ableton","cubase","logic","reaper")]
atlas = build_atlas(bundles)
md = measure_domain(bundles[2].snapshot, get_domain("Structure"))
print(md.applicable, md.observed, md.inferred)          # -> 25 1 8
print(aggregate_mix(atlas, "logic_pro"))
# -> {'observed':17,'inferred':10,'annotated':6,'hidden':8,'absent':8,'applicable':49}
```

Gotchas: `aggregate_mix` must be imported from `session_explorer.atlas.coverage`. `ATLAS_DOMAINS` is a `list[str]` of names — `measure_domain` needs an `AtlasDomain` object, obtained via `get_domain(name)` or `atlas_domains()`.

### Compatibility ladder

```python
from session_explorer.compat import assess_bundle, assess_fixtures, render_ladder_markdown
p = assess_bundle(load_bundle("fixtures/adapters/logic"))
print(p.daw, [l.level for l in p.levels if l.reached])   # -> logic_pro [0, 1, 5]
md = render_ladder_markdown(assess_fixtures())
print(md.splitlines()[0])                                # -> # Compatibility Ladder
```

Levels run `L0_LOADABLE` (0) … `L6_CONTROLLED_INTERVENTION` (6). `assess_fixtures()` yields six profiles: `ableton`, `cubase`, `logic`, `logic_real`, `reaper`, and `effect_send/after` (reaches L6 via injected context). Logic reaching `[0, 1, 5]` — acoustic-outcome-linked without signal-flow or temporal — is the load-bearing "profiles, not ranks" result.

### Metrics report

```python
from session_explorer.metrics import metrics_report, write_metrics
from session_explorer.workbench.pages.alignment import load_x04_bundles
rep = metrics_report(
    [load_bundle(f"fixtures/adapters/{d}") for d in ("ableton","cubase","logic","reaper")],
    load_x04_bundles(),
)
print(len(rep.bundles), len(rep.alignment))              # -> 4 6
# write_metrics(rep, "out_dir")  # writes out_dir/metrics.json, returns that Path
```

`write_metrics(report, out_dir)`'s second argument is an output **directory** — it creates the dir and writes a fixed-name `metrics.json` inside it (do not pass a filename).

### Dataset export

```python
from session_explorer.dataset_export import build_dataset, sanitize_snapshot
man = build_dataset(
    "/tmp/ds_out",
    fixtures_root="fixtures/adapters",
    x04_root="fixtures/cross-daw/X04_effect_return/bundles",
    experiments_root="fixtures/experiments",
)
print(man.schema_version, man.counts)
# -> 0.2 {'snapshots':13,'native':11,'renders':4,'observations':7,'interventions':2,'alignments':1,'fixtures':1,'metrics':1}
clean = sanitize_snapshot(load_bundle("fixtures/adapters/logic").snapshot.model_dump())
```

`build_dataset` writes descriptors only (never WAV) and is deterministic. `sanitize_snapshot` returns a deep-copied, redacted dict (paths redacted, asset paths hashed); the input is untouched. See also `sanitize_native`, `redact_paths`, `hash_asset_path`.

### Alignment

```python
from session_explorer.alignment import align
res = align(load_bundle("fixtures/adapters/ableton").snapshot,
            load_bundle("fixtures/adapters/logic").snapshot)
print(len(res), res[0].status, res[0].confidence)        # -> 9 CONFLICTING 0.7

from session_explorer.workbench.pages.alignment import load_x04_bundles, pair_rows
rows = pair_rows(load_x04_bundles(), ("effect_return","audio_source"))
print(len(rows), rows[0]["pair"], rows[0]["status"])     # -> 12 'ableton → reaper' PROBABLE
```

`align` is directional (one result per strip of `a`); `confirm(result)` is the sole path to `CONFIRMED`. Concept ids are **bare tokens** (`effect_return`, `audio_source`, `main_output`) — not `concept:`-prefixed. Importing `session_explorer.workbench.pages.alignment` pulls in Streamlit and prints harmless "missing ScriptRunContext" warnings when run outside `streamlit run`.

### Graph, cycles, grouping

```python
from session_explorer.graph_layers import build_graph, detect_cycles, annotate_cycles
from session_explorer.graph_layers.grouping import find_group_entities, decompose_group
g = build_graph(load_bundle("fixtures/adapters/logic").snapshot, layer="signal_flow")
print(g.number_of_nodes(), g.number_of_edges())          # -> 8 6
rep = detect_cycles(g); annotate_cycles(g, rep)
print(rep.has_cycles, rep.truncated)                     # -> False False
cub = load_bundle("fixtures/adapters/cubase").snapshot
print(find_group_entities(cub))
# -> ['cubase:track-tr-ch-grp', 'cubase:track-tr-ch-grp:channel']
```

Layer keys: `organizational`, `signal_flow`, `processing`, `automation`, `variant`, `all`. `build_multi(snapshots, layer)` namespaces ids (`s0:`, `s1:`) with no cross-edges. `decompose_group(snapshot, group_entity_id)` returns `.contains / .sums / .controls / .routes_in`. `find_group_entities` returns `[]` for fixtures without group entities (e.g. ableton, logic).

### Variants

```python
from session_explorer.variants import build_variant_set, build_variant_graph, variant_diff
vb = [load_bundle(f"fixtures/variants/{v}") for v in ("v1","v2","v2_alpha","v3")]
sets = build_variant_set(vb)
print(sets[0].family, [(m.label, m.ordinal) for m in sets[0].members])
# -> demo_song [('v1',0),('v2',1),('v2_alpha',1),('v3',2)]
g = build_variant_graph(sets[0]); print(g.number_of_nodes(), g.number_of_edges())   # -> 47 38
print(variant_diff(vb[0], vb[1]).added_entities)         # -> [<2 entities>]
```

`variant_diff` returns a `StateDelta` with fields `added_entities`, `removed_entities`, `added_relationships`, `removed_relationships`, `changed`, `added_sends`, `parameter_changes` — there is **no** `.added`/`.removed`.

### Interventions (state → audio)

```python
from session_explorer.interventions import build_effect_send_experiment, build_parameter_experiment
c = build_effect_send_experiment()
print(type(c).__name__, c.acoustic_delta.available)      # -> InterventionComparison True
p = build_parameter_experiment()
print(len(p.state_delta.parameter_changes))              # -> 1  (delay FEEDBACK 0.2 -> 0.7)
```

Both builders are deterministic and default to `fixtures/experiments/effect_send` and `fixtures/experiments/parameter_change`. An `InterventionComparison` exposes `.intervention`, `.state_delta`, `.signal_flow`, and `.acoustic_delta`.

---

## 7. Regenerating docs & exporting a dataset

**Compatibility ladder markdown** — regenerates `docs/COMPATIBILITY_LADDER.md` (deterministic; reruns byte-identical):

```
.venv/bin/python -m session_explorer.compat.ladder
```

**Concept registry** — regenerates `src/session_explorer/registry/concepts.yaml` (deterministic):

```
.venv/bin/python -m session_explorer.registry.concepts
```

> Both emit a benign `RuntimeWarning` from `runpy`; output is unaffected. These are the only two module `__main__` entry points.

**Metrics JSON** — there is no module entry point for metrics. Produce it either from the API (`metrics_report(...)` then `write_metrics(report, out_dir)` — the second arg is an output **directory**; §6) or from the workbench **Adapter comparison** tab's download button. The narrative doc is [`docs/METRICS.md`](METRICS.md).

**Dataset export tree** — build the descriptors-only dataset from the API (`build_dataset(...)`, §6). It never copies WAVs and is deterministic.

**Privacy / redaction.** Bundle exports sanitize by default (adapters redact paths unless `--no-sanitize` is passed). On the analyzer side, `sanitize_snapshot` / `sanitize_native` / `redact_paths` / `hash_asset_path` (from `session_explorer.dataset_export`) redact filesystem paths and hash asset paths on a deep copy before anything leaves the repo. Run these over any snapshot you intend to share.

---

## 8. Pointers

- [`docs/CONTRACT.md`](CONTRACT.md) — the Adapter Contract (v0.2): the narrative spec of what every adapter must produce (machine source of truth is `packages/canonical_snapshot/`; additive-only within 0.2).
- [`docs/CONTRIBUTION.md`](CONTRIBUTION.md) — "Four observation instruments, one analysis contract": what the system is and why it matters, tying the flagship demonstrations together.
- [`docs/COMPATIBILITY_LADDER.md`](COMPATIBILITY_LADDER.md) — the generated reached-set table (L0 loadable → L6 controlled intervention) across the frozen fixtures. Regenerate with the ladder command in §7.
- [`docs/METRICS.md`](METRICS.md) — the metrics export: loaded bundles reduced to one evidence-and-coverage **profile** (not a score).
- [`docs/evaluation.md`](evaluation.md) — role-inference evaluation: filename role inference benchmarked against labeled vocabularies, with abstention reported separately.
- [`docs/PIVOT.md`](PIVOT.md) — the 2026-07-05 architecture pivot from monorepo product to analytical layer (where the adapter driver code was relocated, and why).
- [`docs/SOURCE_EXPLORERS_AUDIT.md`](SOURCE_EXPLORERS_AUDIT.md) — audit of the four DAW explorers acting as observation instruments (launch procedures and capabilities; unverified items flagged).
