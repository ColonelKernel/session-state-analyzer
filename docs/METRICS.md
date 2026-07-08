# Metrics export (master-prompt §67)

The metrics export reduces a set of loaded bundles to one measurable
evidence-and-coverage profile: **not a score, a profile.** Every number is read
back from an existing analyzer surface — the Observability Atlas, the
deduplicated provenance store, the compatibility ladder, and the alignment
engine — so the metrics can never disagree with the workbench that shows the
same figures.

Code lives in [`src/session_explorer/metrics/`](../src/session_explorer/metrics/):

| Module | Role |
| --- | --- |
| `models.py` | The pydantic schema (`extra="forbid"`). |
| `compute.py` | `metrics_report(...)` and the `compute_*` pieces. |
| `export.py` | `write_metrics(report, out_dir)` → `metrics.json`. |
| `__init__.py` | Re-exports the above plus the shared `aggregate_mix`. |

## What is measured

Per master-prompt §67:

- **Per-domain coverage** — one `DomainMetric` per atlas domain per DAW:
  `direct_observability`, `combined_coverage`, `hidden_ratio`, and the cell
  `status`. These are the `AtlasCell` ratios verbatim (`None` where a domain has
  no measurable scope).
- **Evidence ratios** — the whole-session epistemic mix as bounded fractions
  (`observed` / `inferred` / `annotated` / `hidden` / `absent`), derived from
  the shared `atlas.coverage.aggregate_mix` — the exact counts the Guided overview bars
  draw, so the two cannot drift.
- **Provenance completeness** — the share of `Entity.prov` field refs and
  `Relationship.prov_ref` refs that resolve into the snapshot's deduplicated
  `provenance[]` store. A dangling ref is a broken evidence chain; this measures
  how honest the chain is.
- **Native-feature preservation** — the atlas Native-Features observed count,
  the `extensions[*]` top-level key count, and whether the verbatim
  `native.json` sidecar rode along in the bundle.
- **Fixture / schema conformance** — `schema_valid` (the analyzer's own
  re-validation on load) plus the load/validation `warnings`.
- **Semantic-alignment confidence** — one `AlignmentMetric` per X04 DAW pair,
  reusing the alignment page's `pair_rows` (six directed pairs for
  `effect_return`), each with its `status` and `confidence`.
- **Ladder reached-set** — `ladder_reached`, the set of compatibility-ladder
  rungs a bundle's data demonstrates (from `compat.ladder.assess_bundle`). It is
  a *reached set, never a rank*. When `compat.ladder` is not importable the
  field degrades honestly to `[]` and auto-populates once the module lands
  (`metrics.LADDER_AVAILABLE` reports which).

The `AggregateMetrics` roll-up sums the per-bundle evidence buckets across the
report (a tally, not an average) and summarizes the alignment rows.

## Schema

```
MetricsReport
├─ generated_from : str
├─ bundles        : list[BundleMetrics]
│   ├─ daw, bundle, schema_valid, warnings
│   ├─ native_preservation : NativePreservation
│   │     (native_features_observed, extension_keys, native_json_present)
│   ├─ ladder_reached      : list[int]
│   ├─ domains             : list[DomainMetric]
│   │     (domain, applicable, direct_observability,
│   │      combined_coverage, hidden_ratio, status)
│   ├─ evidence_ratios     : EvidenceRatios
│   │     (observed, inferred, annotated, hidden, absent : ratios; applicable : count)
│   └─ provenance          : ProvenanceCompleteness
│         (entity_field_refs, resolvable, rel_prov_refs, rel_resolvable, completeness)
├─ alignment      : list[AlignmentMetric]  (pair, concept, status, confidence)
└─ aggregate      : AggregateMetrics
      (bundle_count, observed, inferred, annotated, hidden, absent, applicable,
       alignment_pairs, mean_alignment_confidence)
```

All ratio fields are bounded to `[0, 1]`; `EvidenceRatios.applicable` and every
`AggregateMetrics` bucket are integer counts.

## How to regenerate

```python
from pathlib import Path
from session_explorer.loaders.bundle import load_bundle
from session_explorer.metrics import metrics_report, write_metrics
from session_explorer.workbench.pages import alignment as alignment_page

daws = ("reaper", "ableton", "cubase", "logic")
bundles = [load_bundle(Path("fixtures/adapters") / d) for d in daws]
x04 = alignment_page.load_x04_bundles()           # six-pair alignment section

report = metrics_report(
    bundles,
    x04_bundles=x04,
    experiment_ctx={"generated_from": "fixtures/adapters + X04_effect_return"},
)
write_metrics(report, "out")                        # writes out/metrics.json
```

`write_metrics` is dependency-free and does no computation; it is the surface
the dataset export (§57 `metrics/` tree) and a workbench download reuse.

## Sample (generated from the frozen fixtures, trimmed)

```json
{
  "generated_from": "fixtures/adapters + X04_effect_return",
  "bundles": [
    {
      "daw": "reaper",
      "bundle": "reaper",
      "schema_valid": true,
      "warnings": [],
      "native_preservation": {
        "native_features_observed": 6,
        "extension_keys": 6,
        "native_json_present": true
      },
      "ladder_reached": [0, 1, 2, 3],
      "domains": [
        {"domain": "Structure", "applicable": 10, "direct_observability": 1.0,
         "combined_coverage": 1.0, "hidden_ratio": 0.0, "status": "FULLY_OBSERVED"},
        {"domain": "Timeline", "applicable": 7, "direct_observability": 1.0,
         "combined_coverage": 1.0, "hidden_ratio": 0.0, "status": "FULLY_OBSERVED"},
        {"domain": "Routing", "applicable": 11, "direct_observability": 0.909,
         "combined_coverage": 0.909, "hidden_ratio": 0.0, "status": "MOSTLY_OBSERVED"}
        // … 10 domains total
      ],
      "evidence_ratios": {
        "observed": 0.9841, "inferred": 0.0, "annotated": 0.0,
        "hidden": 0.0, "absent": 0.0159, "applicable": 63
      },
      "provenance": {
        "entity_field_refs": 65, "resolvable": 65,
        "rel_prov_refs": 49, "rel_resolvable": 49, "completeness": 1.0
      }
    }
    // … 4 bundles total: reaper, ableton_live, cubase, logic_pro
  ],
  "alignment": [
    {"pair": "ableton → reaper", "concept": "effect_return", "status": "PROBABLE", "confidence": 0.9},
    {"pair": "ableton → cubase", "concept": "effect_return", "status": "PROBABLE", "confidence": 0.95}
    // … 6 X04 pairs total
  ],
  "aggregate": {
    "bundle_count": 4,
    "observed": 195, "inferred": 10, "annotated": 6,
    "hidden": 22, "absent": 9, "applicable": 242,
    "alignment_pairs": 6, "mean_alignment_confidence": 0.9333
  }
}
```

> The sample is illustrative and fixture-coupled: the aggregate buckets, the
> ladder reached-sets, and the alignment confidences all move when a fixture is
> re-exported or a real capture lands, and the corresponding test expectations
> in [`tests/analyzer/test_metrics.py`](../tests/analyzer/test_metrics.py) must
> be updated in the same change.
