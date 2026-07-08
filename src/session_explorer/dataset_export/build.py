"""Build the §57 dataset tree from the frozen fixtures (Phase 3 — infra only).

:func:`build_dataset` packages the analyzer's frozen corpus into the standard
``dataset/{snapshots,native,renders,observations,interventions,alignments,
fixtures,metrics}`` tree — *descriptors only, never audio* — sanitizing every
artifact on the way out (defense-in-depth over the already-sanitized adapter
exports). It is infrastructure: no model training, no audio decode, no
wall-clock in serialized content. Building the same fixtures twice yields the
same bytes.

The alignment artifact is produced through the streamlit-free alignment engine
directly (``session_explorer.alignment.align``), never the workbench page — the
dataset builder must not drag Streamlit into a batch export.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from itertools import combinations
from pathlib import Path
from typing import Any, Optional

from session_explorer.alignment import align
from session_explorer.compat.ladder import assess_bundle
from session_explorer.loaders.bundle import load_bundle
from session_explorer.metrics import metrics_report

from .layout import (
    ALIGNMENTS_DIR,
    ALIGNMENTS_FILENAME,
    DATASET_SCHEMA_VERSION,
    FIXTURES_DIR,
    INTERVENTIONS_DIR,
    MANIFEST_FILENAME,
    METRICS_DIR,
    NATIVE_DIR,
    OBSERVATIONS_DIR,
    RENDERS_DIR,
    SNAPSHOTS_DIR,
    SUBDIRS,
    BundleManifestEntry,
    DatasetManifest,
)
from .sanitize import sanitize_json, sanitize_native, sanitize_snapshot

SNAPSHOT_FILE = "canonical.snapshot.json"
NATIVE_FILE = "native.json"
INTERVENTION_FILE = "intervention.json"

# The four DAWs of the cross-DAW X04 exhibit, in presentation order (mirrors the
# workbench alignment page, but this module never imports it).
_X04_DAW_ORDER: tuple[str, ...] = ("ableton", "reaper", "cubase", "logic")

# The distinct-daw adapter bundles the metrics report is computed over. Kept to
# one bundle per source.daw so the atlas never collapses two bundles onto one
# key (``logic_real`` shares ``logic``'s daw and is exported, but not counted
# twice in metrics).
_METRICS_ADAPTERS: tuple[str, ...] = ("ableton", "reaper", "cubase", "logic")

_GENERATED_FROM = "session-state dataset export"


# --------------------------------------------------------------------------
# Small IO helpers (deterministic JSON).
# --------------------------------------------------------------------------


def _write_json(path: Path, obj: Any) -> None:
    """Write ``obj`` as sorted, newline-terminated JSON (stable across builds)."""
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(text: str) -> str:
    """A filesystem-safe basename fragment from an id / name."""
    out = "".join(c if (c.isalnum() or c in "._-") else "_" for c in text)
    return out.strip("_") or "unnamed"


def _count_json(directory: Path) -> int:
    return len([p for p in directory.iterdir() if p.is_file() and p.suffix == ".json"])


# --------------------------------------------------------------------------
# Bundle discovery.
# --------------------------------------------------------------------------


def _bundle_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        child
        for child in root.iterdir()
        if child.is_dir() and (child / SNAPSHOT_FILE).is_file()
    )


def _x04_bundles_dir(x04_root: Path) -> Path:
    """The directory that actually holds the X04 bundle dirs."""
    nested = x04_root / "bundles"
    return nested if nested.is_dir() else x04_root


def _collect_specs(
    fixtures_root: Path, x04_root: Path, experiments_root: Path
) -> list[tuple[str, str, Path]]:
    """(name, kind, dir) for every bundle the dataset exports, in stable order."""
    specs: list[tuple[str, str, Path]] = []

    for child in _bundle_dirs(fixtures_root):
        specs.append((f"adapter_{child.name}", "adapter", child))

    for child in _bundle_dirs(_x04_bundles_dir(x04_root)):
        specs.append((f"x04_{child.name}", "x04", child))

    if experiments_root.is_dir():
        for exp in sorted(p for p in experiments_root.iterdir() if p.is_dir()):
            for side in ("before", "after"):
                side_dir = exp / side
                if (side_dir / SNAPSHOT_FILE).is_file():
                    specs.append(
                        (f"experiment_{exp.name}_{side}", "experiment", side_dir)
                    )

    return specs


# --------------------------------------------------------------------------
# Per-section writers.
# --------------------------------------------------------------------------


def _provenance_note(raw_snapshot: dict) -> str:
    source = raw_snapshot.get("source", {}) or {}
    adapter = source.get("adapter") or source.get("daw") or "unknown"
    modes = source.get("capture_modes") or []
    n_prov = len(raw_snapshot.get("provenance", []) or [])
    return (
        f"{adapter} / capture: {', '.join(modes) if modes else 'n/a'} / "
        f"{n_prov} provenance record(s)"
    )


def _write_snapshots_and_native(
    out: Path, specs: list[tuple[str, str, Path]]
) -> tuple[list[BundleManifestEntry], list[str]]:
    """Write sanitized snapshots + native payloads; return manifest rows + notes."""
    entries: list[BundleManifestEntry] = []
    absent_native: list[str] = []

    for name, kind, bundle_dir in specs:
        raw = _read_json(bundle_dir / SNAPSHOT_FILE)
        _write_json(out / SNAPSHOTS_DIR / f"{name}.snapshot.json", sanitize_snapshot(raw))

        native_path = bundle_dir / NATIVE_FILE
        native_present = native_path.is_file()
        if native_present:
            _write_json(
                out / NATIVE_DIR / f"{name}.native.json",
                sanitize_native(_read_json(native_path)),
            )
        else:
            absent_native.append(name)

        bundle = load_bundle(bundle_dir)
        reached = sorted(assess_bundle(bundle).reached_set)
        entries.append(
            BundleManifestEntry(
                name=name,
                daw=raw.get("source", {}).get("daw", "unknown"),
                kind=kind,
                provenance_note=_provenance_note(raw),
                ladder_reached=reached,
                schema_version=str(raw.get("schema_version", DATASET_SCHEMA_VERSION)),
                native_present=native_present,
            )
        )
    return entries, absent_native


def _write_renders(out: Path, experiments_root: Path) -> None:
    """Copy (sanitized) the render *descriptor* JSONs — never any audio."""
    dest = out / RENDERS_DIR
    if not experiments_root.is_dir():
        return
    for exp in sorted(p for p in experiments_root.iterdir() if p.is_dir()):
        renders_dir = exp / "renders"
        if not renders_dir.is_dir():
            continue
        for descriptor in sorted(renders_dir.glob("*.json")):
            # Descriptors only: a stray audio file must never be packaged.
            assert descriptor.suffix == ".json", descriptor
            _write_json(
                dest / f"{exp.name}__{descriptor.name}",
                sanitize_json(_read_json(descriptor)),
            )


def _write_observations(
    out: Path, fixtures_root: Path, experiments_root: Path
) -> None:
    """OBSERVATION entities (logic_real) + experiment before/after observations."""
    dest = out / OBSERVATIONS_DIR

    # 1) Standalone OBSERVATION entities carried inside adapter snapshots.
    for child in _bundle_dirs(fixtures_root):
        raw = _read_json(child / SNAPSHOT_FILE)
        for entity in raw.get("entities", []):
            if entity.get("entity_type") != "OBSERVATION":
                continue
            eid = _slug(entity.get("id", "observation"))
            _write_json(
                dest / f"{child.name}__{eid}.observation.json",
                sanitize_json(entity),
            )

    # 2) The controlled experiments' before/after observation records.
    if experiments_root.is_dir():
        for exp in sorted(p for p in experiments_root.iterdir() if p.is_dir()):
            intervention_path = exp / INTERVENTION_FILE
            if not intervention_path.is_file():
                continue
            intervention = _read_json(intervention_path)
            for side in ("before", "after"):
                record = intervention.get(side)
                if record is None:
                    continue
                _write_json(
                    dest / f"{exp.name}__{side}.observation.json",
                    sanitize_json(record),
                )


def _write_interventions(out: Path, experiments_root: Path) -> None:
    """Copy (sanitized) each experiment's ``intervention.json`` record."""
    dest = out / INTERVENTIONS_DIR
    if not experiments_root.is_dir():
        return
    for exp in sorted(p for p in experiments_root.iterdir() if p.is_dir()):
        intervention_path = exp / INTERVENTION_FILE
        if intervention_path.is_file():
            _write_json(
                dest / f"{exp.name}.intervention.json",
                sanitize_json(_read_json(intervention_path)),
            )


def _write_alignments(out: Path, x04_root: Path) -> None:
    """Serialize pairwise X04 alignment results — streamlit-free by construction.

    Uses the alignment *engine* (``align``) directly over the loaded X04
    bundles; the workbench page (which imports Streamlit) is never touched.
    """
    bundles_dir = _x04_bundles_dir(x04_root)
    bundles = {}
    for name in _X04_DAW_ORDER:
        candidate = bundles_dir / name
        if (candidate / SNAPSHOT_FILE).is_file():
            bundles[name] = load_bundle(candidate)

    present = [n for n in _X04_DAW_ORDER if n in bundles]
    pairs: list[dict[str, Any]] = []
    for a, b in combinations(present, 2):
        results = align(bundles[a].snapshot, bundles[b].snapshot)
        pairs.append(
            {
                "pair": f"{a} -> {b}",
                "source": a,
                "target": b,
                "results": [asdict(result) for result in results],
            }
        )

    payload = {
        "daw_order": present,
        "pair_count": len(pairs),
        "note": (
            "Pairwise cross-DAW alignment over the X04 effect-return exhibit; "
            "every claim carries the engine's reasons. Produced by the alignment "
            "engine directly (no workbench / Streamlit)."
        ),
        "pairs": pairs,
    }
    _write_json(out / ALIGNMENTS_DIR / ALIGNMENTS_FILENAME, sanitize_json(payload))


def _write_metrics(out: Path, fixtures_root: Path, x04_root: Path) -> None:
    """Write ``metrics/metrics.json`` = ``metrics_report(...).model_dump()``."""
    adapter_bundles = []
    for name in _METRICS_ADAPTERS:
        candidate = fixtures_root / name
        if (candidate / SNAPSHOT_FILE).is_file():
            adapter_bundles.append(load_bundle(candidate))

    bundles_dir = _x04_bundles_dir(x04_root)
    x04_bundles = {}
    for name in _X04_DAW_ORDER:
        candidate = bundles_dir / name
        if (candidate / SNAPSHOT_FILE).is_file():
            x04_bundles[name] = load_bundle(candidate)

    report = metrics_report(
        adapter_bundles,
        x04_bundles=x04_bundles or None,
        experiment_ctx={"generated_from": _GENERATED_FROM},
    )
    _write_json(out / METRICS_DIR / "metrics.json", sanitize_json(report.model_dump()))


# --------------------------------------------------------------------------
# Public entrypoint.
# --------------------------------------------------------------------------


def build_dataset(
    out_dir: Path | str,
    *,
    fixtures_root: Path | str,
    x04_root: Path | str,
    experiments_root: Path | str,
) -> DatasetManifest:
    """Assemble the §57 dataset tree under ``out_dir`` and return its manifest.

    Descriptors only, never WAV. Every serialized artifact is sanitized
    (home dirs / usernames / ``/Volumes`` redacted, asset paths hashed) as
    defense-in-depth over the already-sanitized adapter exports. Deterministic:
    no wall-clock is written into the tree.
    """
    out = Path(out_dir)
    fixtures_root = Path(fixtures_root)
    x04_root = Path(x04_root)
    experiments_root = Path(experiments_root)

    out.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (out / subdir).mkdir(parents=True, exist_ok=True)

    specs = _collect_specs(fixtures_root, x04_root, experiments_root)
    entries, _absent_native = _write_snapshots_and_native(out, specs)

    _write_renders(out, experiments_root)
    _write_observations(out, fixtures_root, experiments_root)
    _write_interventions(out, experiments_root)
    _write_alignments(out, x04_root)
    _write_metrics(out, fixtures_root, x04_root)

    # Count everything written so far; the manifest itself is the one file the
    # fixtures/ dir will hold once we write it below.
    counts: dict[str, int] = {}
    for subdir in SUBDIRS:
        counts[subdir] = _count_json(out / subdir)
    counts[FIXTURES_DIR] = 1

    manifest = DatasetManifest(
        schema_version=DATASET_SCHEMA_VERSION,
        generated_at=None,
        counts=counts,
        bundles=entries,
    )
    _write_json(
        out / FIXTURES_DIR / MANIFEST_FILENAME,
        sanitize_json(manifest.model_dump()),
    )
    return manifest
