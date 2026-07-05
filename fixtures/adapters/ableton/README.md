# Ableton adapter fixture bundle

A frozen, real 5-file canonical bundle produced by the Ableton explorer's
canonical-export adapter. The analyzer's loaders and conformance suite treat
this directory as the Ableton reference input; regenerate it only from the
adapter repo, never by hand.

## Provenance

- **Producing repo:** `AbletonSessionStateExplorer`
  (https://github.com/ColonelKernel/AbletonSessionStateExplorer)
- **Commit:** `c6fe5e7` (branch `feat/canonical-export`,
  "Add the canonical-export adapter (v0.2 snapshot bundles)"), which
  relocated the mapper from `SessionStateExplorer@041f529`.
- **Command:**

  ```bash
  python -m ableton_session_state_explorer export-canonical \
      data/examples/example_session.json --out exports/example_session
  ```

- **Input:** `data/examples/example_session.json` — the repo's documented
  example session (*Indie Vocal Production Sketch*: 6 tracks, 3 scenes,
  12 clips, 22 devices, 2 return tracks, master chain). No real extension
  export JSON exists in that repo's `data/` or `docs/` (the verified
  110 KB Live 12.4.5 export described in the extension README was not
  committed), so this hand-authored/demo-derived session is the fixture;
  its provenance records honestly carry `source_stability: MANUAL` and
  `capture_modes: ["session_json"]`. Swap in a real
  `--source extension_json` capture when one lands in the adapter repo.
- **Contract:** `canonical-snapshot` 0.2.0 (schema_version `0.2.0`).
- **Determinism:** `created_at` derives from the input file's mtime and
  `snapshot_id` is content-hashed, so re-running the command at the same
  commit reproduces this bundle byte-for-byte.

## Contents

| File | What it is |
| --- | --- |
| `adapter_descriptor.json` | Identity card: `ableton-extension`, capture modes, known limitations |
| `capabilities.json` | Measured capability manifest (read/write/live/render separate) |
| `native.json` | Verbatim native `ProjectState` payload (lossless sidecar) |
| `canonical.snapshot.json` | Flat v0.2 snapshot: 80 entities, 82 relationships (6 TRACK, 9 CHANNEL — the TRACK ≠ CHANNEL split visible in the data) |
| `validation.json` | Contract validation report (`valid: true`, no warnings) |
