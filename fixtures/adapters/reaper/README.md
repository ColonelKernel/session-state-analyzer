# REAPER adapter fixture bundle

Frozen v0.2 canonical snapshot bundle produced by the REAPER observation
instrument. Used by the analyzer's loader/conformance tests; regenerate only
deliberately (it is a frozen contract fixture, not a build artifact).

## Provenance

- **Adapter repo:** `SessionStateExplorerReaper` (`main` at `249d20a`, the
  merge of PR #8 AUXRECV channel decode + ISBUS folder hierarchy; relocated
  driver code originates from `SessionStateExplorer@041f529`).
- **Adapter:** `session-state-explorer-reaper` 0.5.0, adapter id `reaper-rpp`,
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
(schema 0.2.0; snapshot id `reaper:rpp:899bcfc0d9ba9d8d`), `validation.json`
(`valid: true`).

56 entities (1 PROJECT, 9 TRACK, 9 CHANNEL, 22 PROCESSOR, 7 TEMPORAL_OBJECT,
7 MEDIA_ASSET, 1 ROUTING_ENDPOINT), 62 relationships, 12 provenance records.
Since adapter 0.5.0 the `CHANNEL_SENDS_TO` edges carry the decoded AUXRECV
channel wiring (`source_channels`/`target_channels`/`channel_count`/
`channel_layout` plus raw packed values in extras); the 13 `PRECEDES`
processing-order edges come from the Phase-1 shared flattener, first frozen in
this refresh. The demo project has no folder tracks, so the ISBUS hierarchy
decode correctly emits no group entities here.
The export is deterministic (`created_at` = source-file mtime, snapshot id =
native.json content hash) and sanitized (home-directory prefixes redacted to
`~`; the synthetic demo contains no personal data anyway).
