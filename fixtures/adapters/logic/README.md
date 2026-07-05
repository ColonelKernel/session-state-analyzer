# Logic adapter fixture bundle

Frozen five-file canonical v0.2 bundle exported by the Logic explorer's
canonical-export adapter (`LogicSessionStateExplorer`, branch
`feat/canonical-export`, adapter id `logic-evidence`, contract
`canonical-snapshot` 0.2.0 from this repo @041f529 lineage).

## Provenance

- **Source session:** the repo's built-in "Logic Indie Mix Evidence Demo" —
  *synthetic* audio (generated tones/noise, deterministic PRNG) run through
  the **real** evidence pipeline: stem scan → filename role inference →
  channel-strip-note annotation lift → hidden-state markers →
  recommendations. It is clearly labelled synthetic in
  `native.json` (`source_type: "synthetic_demo"`, `metadata.synthetic: true`)
  and in the snapshot warnings.
- **Command:**
  `python -m logic_session_evidence_explorer export-canonical-bundle demo
  --out exports/demo_evidence --no-descriptors`
  (`--no-descriptors` keeps the bundle deterministic and free of
  librosa-version drift).
- **Determinism:** native + canonical id counters reset per build;
  `created_at` derives from the demo WAVs' mtime, `snapshot_id` is a content
  hash of the snapshot body (`logic_pro:sha256:…`); byte-identical across
  re-exports of the same inputs.
- **Sanitisation:** home directory → `~`, temp directory → `$TMPDIR` in all
  paths.

## What this bundle showcases

The Logic adapter is the INFERRED / ANNOTATED / HIDDEN + availability
showcase of the contract — no Logic project file is ever read:

- 6 TRACK-only entities (`kind="inferred"`), each with
  `availability.channel = UNKNOWN` — no fabricated CHANNELs.
- 7 PROCESSOR entities asserted purely by user channel-strip notes
  (evidence ANNOTATED, confidence 0.5, family from the documented Logic
  stock-plug-in catalogue).
- 2 ANNOTATION entities (the notes themselves).
- Hidden-state markers as availability records: PROJECT has
  `automation`/`routing` = INACCESSIBLE with HIDDEN provenance; the four
  tracks without notes carry `plugin_chain` = INACCESSIBLE.
- `capabilities.json`: read-only, evidence-scan capture; structure HEURISTIC
  (role inference benchmarked 99.3% in-sample), audio content
  OFFICIAL_EXPORT, plugin/sends/bus MANUAL, automation & mixer state support
  NONE; write / live_observation / render NONE.
