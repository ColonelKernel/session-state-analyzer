# REAPER adapter fixture bundle

Frozen v0.2 canonical snapshot bundle produced by the REAPER observation
instrument. Used by the analyzer's loader/conformance tests; regenerate only
deliberately (it is a frozen contract fixture, not a build artifact).

## Provenance

- **Adapter repo:** `SessionStateExplorerReaper` (branch `feat/canonical-export`,
  built on `e290b20`; relocated driver code originates from
  `SessionStateExplorer@041f529`).
- **Adapter:** `session-state-explorer-reaper` 0.3.0, adapter id `reaper-rpp`,
  capture mode `file_parse`.
- **Source project:** `data/examples/example_project.rpp` in the adapter repo
  (the synthetic 9-track demo project; REAPER 7 header `7.0/win64`).
- **Command:**

  ```sh
  sse-reaper export-canonical data/examples/example_project.rpp \
      --out exports/example_project
  ```

  then copied verbatim into this directory.

## Contents

The 5-file bundle contract: `adapter_descriptor.json`, `capabilities.json`,
`native.json` (complete native `ProjectState` dump; referenced by path+sha256
from the snapshot's `extensions.reaper.native_file`), `canonical.snapshot.json`
(schema 0.2.0; snapshot id `reaper:rpp:0be2dc3f8b93b5c8`), `validation.json`
(`valid: true`).

56 entities (1 PROJECT, 9 TRACK, 9 CHANNEL, 22 PROCESSOR, 7 TEMPORAL_OBJECT,
7 MEDIA_ASSET, 1 ROUTING_ENDPOINT), 49 relationships, 11 provenance records.
The export is deterministic (`created_at` = source-file mtime, snapshot id =
native.json content hash) and sanitized (home-directory prefixes redacted to
`~`; the synthetic demo contains no personal data anyway).
