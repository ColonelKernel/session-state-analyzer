# canonical-snapshot

The v0.2 snapshot contract between the four DAW session-state explorer
adapters (Ableton, REAPER, Logic, Cubase) and the Session State Analyzer.

**Four observation instruments, one analysis contract.** Adapters observe a
DAW session as well as their evidence allows and serialize what they saw — and
what they could not see — into a flat `CanonicalDAWSnapshot`: entities,
relationships, a deduplicated provenance store, availability records for the
gaps, and a capability manifest describing what the adapter can even attempt.
The analyzer consumes these snapshots and never touches DAW-native files.

Design commitments:

- **Evidence is explicit.** Every value traces to a `ProvenanceRecord` with
  one of four evidence classes: OBSERVED / INFERRED / ANNOTATED / HIDDEN.
- **Absence is a fact, not a null.** Fields an adapter could not observe carry
  an `Availability` status instead of silently missing.
- **TRACK ≠ CHANNEL.** Organizational lanes and mixer signal paths are
  distinct entities joined by `TRACK_USES_CHANNEL`; DAWs that fuse them emit
  both, DAWs that separate them emit what they separate.
- **Flat, additive, versioned.** No nested JSON hiding structure; `rel_type`
  is registry-validated but open (unknown types warn, never fail); schema
  compatibility is gated loudly via `IncompatibleSchemaError`.

This package is pydantic-only by design. It contains the flat v0.2 models
(`models`, `enums`, `capabilities`, `validation`), the v0.1 nested
intermediate the adapters use internally (`nested`, `ids`), and the single
audited converter between them (`from_nested.flatten_session`).

Install (from the analyzer repo root):

```
pip install -e packages/canonical_snapshot
```

Adapters pin by git subdirectory tag (`@schema-v0.2.0`) or editable path.
