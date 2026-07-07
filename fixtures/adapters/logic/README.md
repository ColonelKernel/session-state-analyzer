# Logic adapter fixture bundle

Frozen five-file canonical v0.2 bundle exported by the Logic explorer's
canonical-export adapter (`LogicSessionStateExplorer`, branch
`feat/full-pipeline-demo` @ `34ecb1123f0c4b787fb65460498ff8e61deb74eb`,
built on `feat/canonical-export`; adapter id `logic-evidence`, contract
`canonical-snapshot` 0.2.0 from this repo).

## Provenance

- **Source session:** the repo's built-in **"Logic Full Evidence Demo"** — a
  richer full-pipeline demo that replaces the earlier small "Logic Indie Mix
  Evidence Demo" bundle. *Synthetic* audio (generated tones/noise,
  deterministic PRNG) run through the **real** evidence pipeline: stem scan →
  filename role inference → MIDI + MusicXML inspection with token-matched
  track linking → channel-strip-note annotation lift → descriptor extraction →
  stem-sum reconciliation + reference comparison → hidden-state markers →
  recommendations. It is clearly labelled synthetic in `native.json`
  (`source_type: "synthetic_demo"`, `metadata.synthetic: true`) and in the
  snapshot warnings.
- **Command:**
  `python -m logic_session_evidence_explorer export-canonical-bundle demo-full
  --out exports/full_demo_evidence`
  (descriptors ON — the point of this bundle is the full evidence surface;
  descriptor values are pinned to the librosa version used at export,
  librosa 0.11.0).
- **Determinism:** native + canonical id counters reset per build;
  `created_at` derives from the demo evidence files' mtimes, `snapshot_id` is
  a content hash of the snapshot body with volatile fields blanked
  (`logic_pro:sha256:23646c5afcd2431a`); byte-identical across re-exports of
  the same inputs.
- **Sanitisation:** home directory → `~`, temp directory → `$TMPDIR` in all
  paths.

## What this bundle showcases

The Logic adapter is the INFERRED / ANNOTATED / HIDDEN + availability
showcase of the contract — no Logic project file is ever read — and this
bundle additionally lights up the whole evidence pipeline:

- 8 TRACK-only entities (`kind="inferred"`, roles Vocal/Drums/Bass/Keys/
  Strings/FX), each with `availability.channel = UNKNOWN` — no fabricated
  CHANNELs. Three tracks carry `linked_midi_track_names` and/or
  `linked_musicxml_parts` from token matching against the MIDI file and
  MusicXML score in the evidence set.
- 10 MEDIA_ASSET entities: the 8 stems plus a mixdown (`is_mixdown`) and a
  reference track (`is_reference`).
- 2 OBSERVATION entities (evidence INFERRED, capture `derived_computation`):
  - `stem_sum_reconciliation` — the mixdown is the exact 0.5-scaled sum of
    the stems by construction, so the reconciliation reports
    `fitted_gain = 0.5` with a residual of **−81.53 dB** (the 16-bit
    quantisation floor) — a correct, satisfying result, not a fabricated one.
  - `reference_comparison` — per-octave-band spectral deltas against the
    spectrally different reference track.
- 6 PROCESSOR entities asserted purely by user channel-strip notes (evidence
  ANNOTATED, confidence 0.5); five resolve a `family` from the documented
  Logic stock-plug-in catalogue, and one ("Warmify Pro") deliberately does
  not — the unknown-family path stays unknown.
- 3 ANNOTATION entities (a vocal chain with send "Reverb" → "Bus 1", a drum
  bus note matching no single stem, and a piano chain).
- MIDI + MusicXML evidence in `extensions.logic_pro.evidence`
  (`midi_evidence`, `musicxml_evidence`), plus 10 per-file descriptor sets
  (`available: true`) in `extensions.logic_pro.descriptors`.
- Hidden-state markers as availability records: PROJECT has
  `automation`/`routing` = INACCESSIBLE with HIDDEN provenance; the six
  tracks without plug-in notes carry `plugin_chain` = INACCESSIBLE.
- `capabilities.json`: read-only, evidence-scan capture; structure HEURISTIC
  (role inference benchmarked 99.3% in-sample), audio content
  OFFICIAL_EXPORT, plugin/sends/bus MANUAL, automation & mixer state support
  NONE; write / live_observation / render NONE.

Totals: 30 entities (1 PROJECT, 8 TRACK, 10 MEDIA_ASSET, 6 PROCESSOR,
3 ANNOTATION, 2 OBSERVATION), 30 provenance records (22 INFERRED,
3 ANNOTATED, 3 HIDDEN, 2 OBSERVED), 6 CHANNEL_PROCESSED_BY relationships.
