# reaper_real — a REAL REAPER session (file-parse capture)

"Planet Telex Scheffler" — a real band project (REAPER header `5.93/x64`).
Unlike `logic_real` (a staged multi-source evidence capture), this is the
adapter's primary pathway doing its ordinary job on genuine material: one
`.rpp` file, parsed, no DAW running.

What the real session exercises that the synthetic demo cannot:

- **Folder hierarchy on real data** — 7 folder tracks decoded from ISBUS
  depth deltas into group TRACKs: 18 `CONTAINS` memberships with matching
  `SUMS_TO` / `CHANNEL_ROUTES_TO (via=group_sum)` edges and
  `folder_parent`/`submix` semantic roles.
- **Send wiring on real data** — 12 `CHANNEL_SENDS_TO` edges, every one
  carrying the decoded AUXRECV channel spec (`source_channels` /
  `target_channels` / `channel_count` / `channel_layout`; raw packed
  `I_SRCCHAN`/`I_DSTCHAN` values in extras).
- **The known per-child gating limitation, observed in the wild** —
  `reaper:track-15` has `MAINSEND 0` (it genuinely does not feed its folder
  parent's summing channel), and the contract can only gate summing
  per-parent, so the bundle carries the honest snapshot warning instead of
  suppressing the edge. This is the limitation documented in the adapter's
  capability manifest, now demonstrated on a real session rather than a
  constructed fixture.

Produced by SessionStateExplorerReaper `main` @ `249d20a`
(`session-state-explorer-reaper` 0.5.0, adapter id `reaper-rpp`, capture
mode `file_parse`):

    sse-reaper export-canonical "<local path>/Planet Telex Scheffler.rpp" \
        --out exports/planet_telex

then copied verbatim into this directory. The source project lives locally
under `~/Library/CloudStorage/OneDrive-Personal/Documents/Planet Telex
Scheffler/`; audio is NOT committed — this bundle is metadata + descriptors
only, and home-directory prefixes are redacted to `~` by the exporter.

Snapshot shape: 82 entities (1 PROJECT, 25 TRACK, 25 CHANNEL, 19 PROCESSOR,
7 TEMPORAL_OBJECT, 5 MEDIA_ASSET), 130 relationships, 28 provenance records;
schema 0.2.0, snapshot id `reaper:rpp:5c7fe14b3e3b3a57`, `validation.json`
`valid: true` (0 errors, 0 warnings). Compatibility ladder reached set:
{L0, L1, L2, L3} — same shape as the synthetic `reaper` bundle (structure,
routing, timeline; the pathway has no automation, scene, or observation
evidence), which is itself the point: the ladder measures the *pathway*,
not how interesting the music is.
