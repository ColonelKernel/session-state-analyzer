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

The sidebar selects bundles (discovered under `fixtures/adapters/`), the
graph layer (`organizational` / `signal_flow` / `all`), and the view:

- **Canonical** — two tabs: *Graph* (all selected snapshots side by side in
  one canonical graph, coloured by entity type with observability overriding
  where a value is inferred/annotated/hidden) and *Entity inspector* (one
  entity, three panels: canonical / native / evidence — every value traceable
  to its provenance record, every unobservable field stated).
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
