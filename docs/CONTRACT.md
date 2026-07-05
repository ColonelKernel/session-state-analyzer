# The Adapter Contract (v0.2)

What every observation instrument (adapter) must produce for the Session State
Analyzer to consume it. The machine-readable source of truth is
[`packages/canonical_snapshot/`](../packages/canonical_snapshot/) — this
document is the narrative spec. Schema changes are additive-only within 0.2;
anything else bumps the version and the analyzer refuses loudly
(`IncompatibleSchemaError`), never silently.

## The bundle

One export = one directory of five files:

| File | Contents | Required |
|---|---|---|
| `canonical.snapshot.json` | The `CanonicalDAWSnapshot` (below) | yes |
| `native.json` | The adapter's full native model dump — never embedded in the canonical file, referenced by path + sha256 from `extensions[daw].native_file` | yes (or explicit `native_payload_omitted`) |
| `capabilities.json` | `CapabilityManifest`: read / write / live_observation / render as separate sections; per-domain per-field applicability, support, capture method, source stability, tested version, validation status | yes |
| `adapter_descriptor.json` | `AdapterDescriptor`: adapter id, DAW, capture modes, capability summaries, known limitations | yes |
| `validation.json` | The adapter's own `validate_snapshot()` report at export time (the analyzer revalidates on load regardless) | yes |

Adapters install the contract with
`pip install -e <analyzer>/packages/canonical_snapshot` (or a git-subdirectory
pin) and produce bundles via their `export-canonical` CLI. Exports must be
**deterministic**: reset id counters, derive `created_at` from the input
artifact (not wall-clock), content-hash the `snapshot_id` — re-exporting the
same input yields byte-identical bundles.

## The snapshot

Flat `entities[]` + `relationships[]` — structure is never hidden inside
nested JSON. Every entity carries:

- `entity_type` — one of the 19 core concepts (PROJECT, TIMELINE, TRACK,
  CHANNEL, TEMPORAL_OBJECT, MEDIA_ASSET, MUSICAL_CONTENT, PROCESSOR,
  PARAMETER, AUTOMATION, MODULATION, ROUTING_ENDPOINT, ROUTING_EDGE,
  STRUCTURAL_CONTAINER, VARIANT, ANNOTATION, RENDER, OBSERVATION,
  INTERVENTION). The core is deliberately smaller than the union of DAW
  features; DAW detail rides in `native` and `extensions`.
- `semantic_roles[]` — plural, because a REAPER track really is
  simultaneously a source, a submix, and a folder parent.
- `native {daw, native_type, properties}` — what the DAW calls it and its
  inspectable native detail. An Ableton `return_track`, a Cubase
  `fx_channel`, a Logic `aux_channel_strip`, and a REAPER `media_track` may
  all be canonical `effect_return`s — the native identity is never erased.
- `prov {field → prov_ref, "*" = entity default}` — field-level provenance by
  reference into the deduplicated `provenance[]` store.
- `availability {field → …}` — only for fields that are NOT plainly
  available: NOT_PRESENT, INACCESSIBLE, UNSUPPORTED, NOT_APPLICABLE,
  PARSE_ERROR, REDACTED, UNKNOWN. Never encode these eight meanings as null.

### Track ≠ Channel (mandatory)

A TRACK owns content and arrangement; a CHANNEL owns signal flow and mixer
state. They are linked by `TRACK_USES_CHANNEL`. A dialect that cannot observe
channels (Logic evidence) conforms by emitting TRACK-only entities with
`availability: {channel: UNKNOWN}` — the conformance suite rejects silent
omission, not honest ignorance.

### Three separated epistemic dimensions

- **Evidence** (`ProvenanceRecord.evidence`): OBSERVED / INFERRED / ANNOTATED
  / HIDDEN — how the value entered the system.
- **Availability** (per field, above) — whether the state could be had at all.
- **Source stability** (`ProvenanceRecord.source_stability`):
  OFFICIAL_DOCUMENTED / OFFICIAL_EXPORT / SUPPORTED_INTEGRATION /
  COMMUNITY_DOCUMENTED / REVERSE_ENGINEERED / UI_AUTOMATION / HEURISTIC /
  MANUAL — how fragile the capture pathway is. A value can be genuinely
  OBSERVED through a fragile method; the contract records both truths.

Confidence appears only where it means something (inference, alignment);
OBSERVED records carry none.

### Ids

One namespace per snapshot: every entity id is prefixed with the dialect
(`reaper:track-1`, `reaper:track-1:channel`, `reaper:project`). Exceptions:
`asset:` (media assets, deliberately dialect-free for cross-DAW content
matching) and `prov:` (provenance store). Ids are stable within a snapshot
only — no adapter currently has cross-export-stable identity, which is why
cross-snapshot alignment is semantic (names, roles, topology, media hashes),
never positional.

## Conformance

`tests/analyzer/test_conformance.py` runs the same checks against every
frozen bundle in `fixtures/adapters/`: clean validation, exactly one PROJECT,
single id namespace, the Track≠Channel rule, resolving provenance with
contractual vocabulary, non-empty coverage, shipped capabilities/descriptor,
native-sidecar sha256 integrity, no home-directory leaks, and the loud
version gate. Adapter repos are expected to run their own bundle exports
through the same assertions in their test suites.

## What the contract is not

Not a session-conversion format, not a claim that hidden state is known, and
not a promise of feature parity. Degraded bundles are first-class: an `.als`
or `.cpr` input yields a PROJECT-only snapshot with explicit failures and
UNKNOWN/UNSUPPORTED availability — the honesty *is* the deliverable.
