# Source Explorers Audit

Audit of the four DAW session-state explorers that act as observation
instruments (adapters) beneath the Session State Analyzer. Synthesized from
full-repo exploration reports (2026-07-05) and spot-verified against the
working trees on the same date. Entries marked **UNVERIFIED** are believed
correct but not re-checked against code; **UNKNOWN** means the repositories do
not answer the question yet.

Snapshot of repo state at audit time:

| Repo | Branch | HEAD | Working tree |
|---|---|---|---|
| AbletonSessionStateExplorer | `main` | `55469dd` | clean |
| SessionStateExplorerReaper | `mixer-ui` | `f3cfdd7` | 1 modified file; PR #4 (`guide-grounded-recommendations`) open |
| LogicSessionStateExplorer | `fix/catalog-name-shadowing` | `c4d7dfe` | clean; PR #11 open |
| CubaseSessionStateExplorer | `main` | `ef09481` (empty initial commit) | **entire source tree uncommitted** (`src/`, `tests/`, `fixtures/`, `pyproject.toml` all untracked) |

---

## 1. Ableton Live — AbletonSessionStateExplorer

- **A. Repository location:** `/Volumes/Mac-Storage/GitHub/AbletonSessionStateExplorer`
- **B. Current branch:** `main` @ `55469dd`, clean.
- **C. Current status:** Working prototype v0.1.0. 10 pytest modules. Verified end-to-end against a real Live 12.4.5 set via the extension (110 KB export, 276 graph nodes). Also hosts a Cubase *dialect* (demo + track-archive inspector) that predates the dedicated Cubase repo.
- **D. Launch procedure:** UI: `streamlit run src/ableton_session_state_explorer/app.py`. CLI: `python -m ableton_session_state_explorer {export-demo|diff-demo|inspect-als|inspect-track-archive}` (supports `--dialect cubase`). Extension: `npm install && npm run build` in `extension/session-state-exporter/` (vendored Extensions SDK tarballs), `npm start` against Live 12.3+.
- **E. Acquisition mechanism:** (1) **Session State Exporter** — TypeScript Live extension on the official Ableton Extensions SDK 1.0.0-beta.0; right-click → export session JSON conforming to the ProjectState schema. (2) `.als` **surface inspector**: gzip + ElementTree tag counting — explicitly *not* a parser; output never enters the model pipeline. (3) Built-in demo builders.
- **F. Raw state format:** Extension JSON (schema v0.1.0); `.als` gzip/XML (surface-counted only).
- **G. Normalized state format:** Pydantic `ProjectState` family (`models.py`): TrackState, ClipState (beats domain), SceneState, DeviceState + DeviceParameterState, SendState, ReturnTrackState, MasterTrackState. `validate_project_dict` backfills heuristic `role`/`device_family` without overwriting supplied values.
- **H. Graph representation:** NetworkX DiGraph, 11 node types / 12 edge types (`graph_builder.py`); scene/clip/session-grid structure is first-class.
- **I. Snapshot representation:** JSON export bundle `{schema_version, project, graph, descriptors, recommendations, warnings, export_metadata}`.
- **J. Diff implementation:** `session_diff.py` — name-matched structural diff with narrative + caveats (renames appear as remove+add; parameter diffs only for uniquely-named devices).
- **K. Provenance model:** `raw_source` dicts on entities (rack paths, unmapped fields); `warnings[]`; no field-level provenance, no evidence taxonomy.
- **L. Confidence model:** None formal. Heuristic classifications are labeled as heuristics but carry no scores.
- **M. Capability model:** Informal. README documents extension API 1.0.0 omissions precisely: no automation state, no dB mixer values, no track colors, no device on/off, 64-parameter cap per device — recorded as `null` + warnings.
- **N. Current UI architecture:** Single ~1000-line Streamlit app; modes: demo / upload / inspect (.als, track archive) / diff / export / prediction.
- **O. Existing fixtures:** `data/examples/example_session.json` ("Indie Vocal Production Sketch", 6 tracks/3 scenes/22 devices), `example_session_revision.json` (diff demo), `example_cubase_session.json`. A real extension export existed during validation; whether one is committed is **UNKNOWN** — preferred P1 input if the user can produce a fresh one.
- **P. Stable identifiers:** Sequential `make_id` ids (`track-1`, …) — stable *within* one export only.
- **Q. Unstable identifiers:** All ids across exports; diff intentionally matches by name. Live's internal object ids are not exposed by the extension export.
- **R. DAW-native concepts:** Session view (scenes, clip slots), return tracks, master track, racks (flattened with rack path preserved in `raw_source`), warp, MIDI note counts, group tracks.
- **S. Portable concepts:** Tracks/devices/sends/clips; device-family + track-role keyword heuristics; export bundle shape.
- **T. Known missing state:** Automation (hidden by extension API), mixer dB values, track colors, device enabled flags, plugin-internal parameters beyond the host-visible cap, everything inside `.als`.
- **U. Major technical risks:** Extensions SDK is beta; extension JSON is hand-editable (trust boundary); Live version drift vs SDK.
- **V. Reusable shared code:** Its models/graph/diff/export/viz/recommendations were the base copies absorbed into the analyzer core during the monorepo phase; the round-trip-verified canonical mapper exists (built during that phase) and relocates here.
- **W. Adapter-local code:** Extension TypeScript, `als_inspector.py`, `ableton_export_adapter.py`, `prediction.py` (synthetic-corpus baseline — Ableton-only), demo builders, Ableton keyword tables (original ordering matters for behavior parity).

---

## 2. REAPER — SessionStateExplorerReaper

- **A. Repository location:** `/Volumes/Mac-Storage/GitHub/SessionStateExplorerReaper`
- **B. Current branch:** `mixer-ui` @ `f3cfdd7` (1 modified file in tree); PR #4 open from `guide-grounded-recommendations`.
- **C. Current status:** Working prototype v0.3.0; the strongest offline parser of the four; 6 pytest modules; validated on a real REAPER 7 session (recommendation-spam fixes, screenshots committed).
- **D. Launch procedure:** `streamlit run src/session_state_explorer/app.py`. No CLI.
- **E. Acquisition mechanism:** Offline parse of `.rpp` project text — stack-based, line-oriented, quote-aware, tolerant (never raises; warnings instead). **No runtime/live observation yet** — the "RPP + runtime dual observability" description is aspirational; the vendored SDK headers (`sdk/`, `reaper-plugins/`) are reference documentation only, imported by nothing.
- **F. Raw state format:** `.rpp` text; raw source lines preserved per entity (`raw_line`/`raw_lines`).
- **G. Normalized state format:** Pydantic `ProjectState` (TrackState with pan_mode/pan_law/width/solo_mode/solo_defeat/main_send, FxState with offline flag + rec-input chain, MediaItemState (seconds domain), RouteState with AUXRECV send modes).
- **H. Graph representation:** NetworkX DiGraph, 6 node types incl. unresolved-route targets.
- **I. Snapshot representation:** JSON `{schema_version 0.3.0, project, graph, descriptors, recommendations, fingerprint, warnings}`.
- **J. Diff implementation:** None; structural **fingerprint** + cosine similarity instead (`fingerprint.py`).
- **K. Provenance model:** Raw-line traceability on every parsed object; warnings for unresolved routes/missing files; `header_platform` disambiguates OS-dependent color byte order. No evidence taxonomy.
- **L. Confidence model:** None formal; stock-FX identification is authoritative via the guide-derived knowledge table (`reaper_fx_knowledge.py`, ~650 LOC with REAPER User Guide citations), keyword heuristics otherwise.
- **M. Capability model:** Informal but explicit: docstrings enumerate what is deliberately not decoded — plug-in parameter blobs, envelopes/automation, take FX, item fades, tempo maps.
- **N. Current UI architecture:** Streamlit multi-tab (summary/graph/tables/descriptors/recommendations/export); `mixer-ui` branch is evolving the mixer view.
- **O. Existing fixtures:** `data/examples/example_project.rpp` (synthetic 23-track REAPER 7 session) + `make_example_data.py` generating seven WAV stems.
- **P. Stable identifiers:** Sequential per-parse ids only.
- **Q. Unstable identifiers:** REAPER's own track GUIDs exist in `.rpp` but are **not extracted** by the parser (verified: no GUID handling) — a cheap future win for stable identity.
- **R. DAW-native concepts:** Record-input/monitoring FX chains (`FXCHAIN_REC`), AUXRECV routing with send modes, pan modes/laws, solo modes + solo-defeat, `main_send` parent routing, platform-dependent packed colors, offline (unloaded) FX.
- **S. Portable concepts:** tracks/items/FX/routes; fingerprinting; the descriptors failure model (`available`/`unavailable_reason`).
- **T. Known missing state:** Plug-in internal state, automation envelopes, take FX, item fades, tempo map, markers/regions (verified: no MARKER parsing), folder hierarchy (parent/child depth not modeled), video/notation.
- **U. Major technical risks:** `.rpp` format is community-documented (not an official spec); cross-platform color ambiguity; live-observation pathway entirely unbuilt.
- **V. Reusable shared code:** Fingerprint (now core), descriptor failure model (now core), knowledge-catalogue pattern.
- **W. Adapter-local code:** `rpp_parser.py`, `reaper_fx_knowledge.py`, color decoding, the 11 guide-cited recommendation rules.

---

## 3. Logic Pro — LogicSessionStateExplorer

- **A. Repository location:** `/Volumes/Mac-Storage/GitHub/LogicSessionStateExplorer`
- **B. Current branch:** `fix/catalog-name-shadowing` @ `c4d7dfe` (PR #11 open; contains the instrument-name shadowing fix — newer than any copy made during the monorepo phase).
- **C. Current status:** Working prototype v0.1.0; ~4,400 LOC / 22 modules; 13 pytest modules; role inference benchmarked at **99.3%** weighted accuracy on a MedleyDB-derived corpus (6,467 instances; in-sample caveat documented).
- **D. Launch procedure:** `streamlit run src/logic_session_evidence_explorer/app.py`; CLI console script `logic-session-evidence-explorer {demo|scan-stems|export-bundle}`.
- **E. Acquisition mechanism:** **Evidence-based; never parses `.logicx`.** Ingests exported stems/mixdown (filename + header scan), MIDI (mido), MusicXML (music21), channel-strip notes CSV/JSON (user assertions), session manifest, reference tracks, AAF/ADM conservative surface inspection.
- **F. Raw state format:** Audio files, `.mid`, MusicXML, CSV/JSON annotations.
- **G. Normalized state format:** `SessionEvidence` family: AudioEvidence, MidiEvidence, MusicXmlEvidence, ChannelStripNote, InferredTrackState (with explicit `observed_fields`/`inferred_fields`/`hidden_fields`), HiddenStateMarker, StemSumReconciliation, ReferenceComparison.
- **H. Graph representation:** NetworkX, 18 node types, every node tagged `observed|inferred|annotation|hidden|derived` — the origin of the system-wide observability framework.
- **I. Snapshot representation:** `session_evidence.json`, `graph.json`, `full_bundle.json`, plus a **PROV-O-grounded** export.
- **J. Diff implementation:** None; signal-level analyses instead — stem-sum reconciliation (fitted gain, residual dB, band residuals) and level-independent reference comparison.
- **K. Provenance model:** The declarative observation matrix (`observation_model.py`: reveals/constrains/asserts/hides per artifact type), per-node observability tags, hidden-state markers with consequences and possible sources, PROV-O vocabulary mapping. Richest *epistemics* of the four.
- **L. Confidence model:** Calibrated: role-inference confidence bins (0.2/0.55/0.70/0.75/0.85) with measured per-bin accuracy in the benchmark; matching threshold 0.75.
- **M. Capability model:** The observation matrix doubles as a declarative capability statement for evidence artifacts.
- **N. Current UI architecture:** Streamlit, 4 modes (demo / upload exports / upload metadata / about+limitations); observability color legend.
- **O. Existing fixtures:** `data/examples/` (manifest JSON, channel-strip notes CSV), `data/eval/` MedleyDB corpus + cached benchmark results, synthetic demo builder (stdlib WAV synthesis).
- **P. Stable identifiers:** Sequential per-run (`audio_1` style).
- **Q. Unstable identifiers:** Everything across runs; linking is token-based name matching by design.
- **R. DAW-native concepts:** Channel strips (annotated), sends/buses (annotated), track stacks (hidden-state marker), stock plugin/instrument catalog with Logic User Guide page citations, Logic filename decoration conventions.
- **S. Portable concepts:** Observability taxonomy, hidden-state markers, role inference + evaluation harness, token matching, stem-sum reconciliation — all already generalized into the analyzer core.
- **T. Known missing state:** By design nearly all native session state: plugin chains, automation, routing, mixer state (hidden unless annotated). The honesty about this *is* the contribution.
- **U. Major technical risks:** Evidence-only ceiling on what can ever be claimed; mido/music21 are heavy optional deps; in-sample benchmark generalization.
- **V. Reusable shared code:** observation model, role inference, matching, signal comparisons, PROV export, visualization observability scheme (all absorbed into analyzer core).
- **W. Adapter-local code:** stem scanner, manifest loader, MIDI/MusicXML/AAF inspectors, session builder, plugin catalog, demo synthesis, the 9 evidence rules (note: prototype has **9**, not the 7 previously reported).

---

## 4. Cubase — CubaseSessionStateExplorer

- **A. Repository location:** `/Volumes/Mac-Storage/GitHub/CubaseSessionStateExplorer`
- **B. Current branch:** `main` @ `ef09481` — an **empty initial commit; the entire source tree is untracked/uncommitted** (src/, tests/, fixtures/, pyproject.toml, lib/, tools/, runtime/, data/). First adapter action must be committing the working tree.
- **C. Current status:** Youngest of the four but real code (~2,130 LOC): three working extractors and the most modern schema design. Test directory currently **UNKNOWN** contents (was empty at first exploration; files appeared in today's uncommitted work — verify at P1).
- **D. Launch procedure:** `cpr-lab` CLI implemented (`cpr_lab:_cli`); `cubase-explorer` console script declared but **not implemented**; no UI.
- **E. Acquisition mechanism:** (1) **DAWproject** (`.dawproject` zip/XML — official Cubase 14+/15 export): full structural parse. (2) Dependency-free SMF MIDI reader. (3) `.cpr` **conservative binary evidence scan** (string/token proximity, plugin-name candidates with offsets; explicitly never parsed into structural state).
- **F. Raw state format:** `.dawproject` zip, `.mid`, `.cpr` RIFF binary.
- **G. Normalized state format:** `SessionState` family with a `Provenanced` base on *every* entity: TrackState (12 track types), FolderState (organizational vs group-channel-enabled distinction), RouteState (explicit output routing), AutomationLane, MusicalStructure (tempo map, time signatures, markers, chords), MediaFile, **UnknownState** (first-class observability boundary), CaptureInfo.
- **H. Graph representation:** None yet.
- **I. Snapshot representation:** `SessionState.model_dump()` JSON v0.1.0 with adapter + capture metadata and coverage percent; `CprReport` JSON. This 0.1.0 shape is the closest ancestor of the analyzer's v0.2 contract and is retired by it.
- **J. Diff implementation:** None. (In-flight uncommitted work may include comparison fixtures — `dualfilter_a/b`, `routing_a/b` `.dawproject` pairs suggest A/B intent; **UNVERIFIED**.)
- **K. Provenance model:** Richest *mechanics* of the four: per-field Provenance {status: exported/parsed/observed/inferred/unavailable/conflicting, confidence, source{type, artifact, locator, evidence}, alternatives[]}.
- **L. Confidence model:** Per-provenance-record confidence 0..1.
- **M. Capability model:** Declarative `observation_model.py` (what each artifact type reveals/hides) + capture coverage metrics.
- **N. Current UI architecture:** None (deliberately modular; UI was expected to be reused).
- **O. Existing fixtures:** `fixtures/cubase/` (uncommitted, created today): `demo_session.dawproject`, `dualfilter_a/b.dawproject` + WAVs, `routing_a/b.dawproject` + WAVs, `manifest.json`, `notes.mid`. Plus the Ableton repo's hand-authored Cubase demo session (ProjectState dialect).
- **P. Stable identifiers:** Dialect-namespaced ids (`cubase:track-1`) — the convention the analyzer adopted.
- **Q. Unstable identifiers:** DAWproject XML ids stability across re-exports **UNKNOWN**.
- **R. DAW-native concepts:** FX channels vs group channels, folders with `group_channel_enabled`, chord track, score state (placeholder), freeze state, 12-type track taxonomy.
- **S. Portable concepts:** Provenance-first entity design, UnknownState, observation matrix, capture coverage — all directly anticipated the analyzer contract.
- **T. Known missing state:** `.cpr` structural content (evidence-scan only), Track Archive XML parsing (only the Ableton repo's toy inspector exists), plugin internals, anything not in DAWproject export.
- **U. Major technical risks:** No committed history (work exists only in a working tree — data-loss risk until committed); zero tests at exploration time; DAWproject coverage vs real Cubase projects untested against large sessions.
- **V. Reusable shared code:** Its provenance/observability design (conceptually absorbed into the v0.2 contract); dawproject extractor patterns.
- **W. Adapter-local code:** All three extractors, cpr-lab CLI, native SessionState family, `runtime/` + `tools/` placeholders (MIDI Remote capture — future).

---

## 5. Cross-cutting findings

**Duplicated infrastructure (pre-pivot):** all four repos carried near-identical
copies of librosa descriptor extraction, PyVis/Plotly visualization, JSON export,
keyword classifiers, and id/utility helpers, with drift. These were consolidated
into the analyzer's `session_explorer.core` during the monorepo phase (see
`docs/PIVOT.md`) — that consolidation survives the pivot as the analysis layer.

**Incompatible assumptions to respect in the contract:**
1. **Time domains:** Ableton/Cubase-dialect clips are in beats; REAPER items in
   seconds; Logic evidence has file durations only. Unit-tagged, never coerced.
2. **Identity:** no adapter has cross-export-stable ids today (REAPER GUIDs are
   the nearest opportunity). Alignment must remain name/topology/media-based.
3. **Track≠Channel:** REAPER tracks are genuinely both; Ableton returns/master
   are channel-like; Logic tracks vs channel strips differ by design; Cubase
   separates mixer channels. The nested v0.1 schema hid this; the v0.2 flatten
   step makes it explicit.
4. **Evidence semantics:** Logic's tags, Cubase's provenance statuses, REAPER's
   raw-line traceability, and Ableton's raw_source dicts are four dialects of
   the same idea — mapped to one Evidence/Availability/SourceStability model in
   the v0.2 contract (see `docs/CONTRACT.md`).
5. **Rule packs:** REAPER's 11 rules and Logic's 9 are dialect knowledge with
   literature citations; they stay adapter-side. The analyzer's `explain/`
   layer reasons only over canonical snapshots and measured coverage.
