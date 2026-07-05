# Architecture pivot: from monorepo product to analytical layer

**Date:** 2026-07-05

## What changed

This repository began as a **monorepo unification** of the four DAW session-state
explorer prototypes: commits `d0bd9b2` (scaffold), `2f8bae6` (shared core
services), `c438957`/`2a409c1`/`4f98625`/`041f529` (embedded per-DAW "drivers":
native models, parsers, lossless mappers, rule packs, tests) pursued that plan.

The direction was superseded before the drivers shipped. The research program's
architecture is now:

> **Four observation instruments, one analysis contract.**
> The four explorers remain independent adapters in their own repositories.
> This repository is the **Session State Analyzer** — a deliberately separate
> analytical layer that consumes their serialized exports (native snapshot +
> canonical snapshot + capability manifest) and contains **no DAW parsing or
> acquisition code**.

## Why

The scientific claim is not "four DAWs can output the same JSON" but that
production state can be represented across creative systems with different
ontologies and unequal observability — without erasing DAW-native semantics or
pretending hidden state is known. That requires the observation layer and the
analysis layer to be genuinely separate, with a versioned, validated snapshot
contract between them (see `docs/CONTRACT.md` and `packages/canonical_snapshot/`).

## What happened to the driver code

Nothing was lost, and history was not rewritten. The embedded driver work was
**relocated** to the repositories where acquisition belongs, as their
`canonical_export/` subpackages (the `export-canonical` CLI):

| Driver subtree (this repo, at `041f529`) | Destination |
|---|---|
| `src/session_explorer/drivers/reaper/` + `tests/drivers/reaper/` | `SessionStateExplorerReaper` |
| `src/session_explorer/drivers/ableton/` (+ `extension/`, already canonical there) | `AbletonSessionStateExplorer` |
| `src/session_explorer/drivers/cubase/` (mapper + observation notes; native copies discarded — the Cubase repo originals win) | `CubaseSessionStateExplorer` |
| `src/session_explorer/drivers/logic/` (pipeline copies discarded — the Logic repo originals win, incl. its newer role-inference fixes) | `LogicSessionStateExplorer` |

Extraction commits in the adapter repos cite `SessionStateExplorer@041f529` as
the origin. The nested canonical schema those mappers emit was moved to
`packages/canonical_snapshot/src/canonical_snapshot/nested.py` and remains the
adapters' internal intermediate; the wire format is the flat v0.2
`CanonicalDAWSnapshot` produced by `from_nested.flatten_session()`.

## What survived in place

The DAW-agnostic analysis services built during the monorepo phase are exactly
the analyzer-layer assets and stayed: graph construction, visualization themes
and renderers, PROV-O export, structural diff, fingerprinting, the rule engine
(re-scoped to `explain/`), role inference (MedleyDB-benchmarked), token
matching, and audio descriptors/signal comparisons.
