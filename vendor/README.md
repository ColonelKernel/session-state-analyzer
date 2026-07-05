# Vendored third-party material

- `ableton-extensions-sdk-1.0.0-beta.0/` — Ableton Extensions SDK + CLI tarballs, consumed by
  `extension/session-state-exporter/package.json` via `file:` references. Needed to build the
  Session State Exporter Live extension (`npm install && npm run build` inside the extension dir).
- `reaper-sdk/` — REAPER plugin SDK headers (`sdk/`) and plugin reference sources
  (`reaper-plugins/`). **Documentation-only**: nothing in the Python package imports these; they
  ground the `.rpp` parser's field semantics (volume/pan encoding, solo modes, custom colors)
  and recommendation citations.
