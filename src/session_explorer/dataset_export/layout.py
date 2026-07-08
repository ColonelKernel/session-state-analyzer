"""The §57 dataset layout: subdir names + the ``DatasetManifest`` schema.

The dataset tree is::

    dataset/
      snapshots/      sanitized canonical snapshots (descriptors, never WAV)
      native/         sanitized verbatim native payloads
      renders/        render descriptor JSONs (never the audio itself)
      observations/   state+render observation records
      interventions/  the controlled-A/B intervention records
      alignments/     cross-DAW alignment results (X04)
      fixtures/       this manifest — the fixture inventory + provenance + ladder
      metrics/        the measurable coverage/evidence report

``DatasetManifest`` is the machine-readable index of what the tree contains. It
forbids unknown fields — the same contract discipline the snapshot follows — and
carries no wall-clock time (``generated_at`` is a deliberately empty placeholder)
so a rebuilt dataset diffs cleanly.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

DATASET_SCHEMA_VERSION = "0.2"

# The eight §57 subdirectory names, in tree order.
SNAPSHOTS_DIR = "snapshots"
NATIVE_DIR = "native"
RENDERS_DIR = "renders"
OBSERVATIONS_DIR = "observations"
INTERVENTIONS_DIR = "interventions"
ALIGNMENTS_DIR = "alignments"
FIXTURES_DIR = "fixtures"
METRICS_DIR = "metrics"

SUBDIRS: tuple[str, ...] = (
    SNAPSHOTS_DIR,
    NATIVE_DIR,
    RENDERS_DIR,
    OBSERVATIONS_DIR,
    INTERVENTIONS_DIR,
    ALIGNMENTS_DIR,
    FIXTURES_DIR,
    METRICS_DIR,
)

MANIFEST_FILENAME = "manifest.json"
ALIGNMENTS_FILENAME = "x04.json"


class _DatasetModel(BaseModel):
    """Base for the manifest models: unknown fields are a schema violation."""

    model_config = ConfigDict(extra="forbid")


class BundleManifestEntry(_DatasetModel):
    """One bundle's row in the dataset manifest.

    ``name`` is the dataset-local basename (``adapter_cubase``,
    ``x04_reaper``, ``experiment_effect_send_before``); ``kind`` says which
    corpus it came from. ``provenance_note`` is a short human string derived from
    the snapshot's source block; ``ladder_reached`` is the compatibility-ladder
    reached-set (rung indices) from ``compat.assess_bundle``; ``schema_version``
    is the contract version the snapshot declares; ``native_present`` records
    whether a ``native.json`` rode along.
    """

    name: str
    daw: str
    kind: str
    provenance_note: str
    ladder_reached: list[int]
    schema_version: str
    native_present: bool


class DatasetManifest(_DatasetModel):
    """The dataset-level index: schema version, counts, and the bundle inventory.

    ``counts`` maps each §57 subdir name to the number of files written under it.
    ``generated_at`` is an intentionally empty placeholder — the build never
    stamps wall-clock time into serialized content, so the tree is reproducible.
    """

    schema_version: str = DATASET_SCHEMA_VERSION
    generated_at: Optional[str] = None
    counts: dict[str, int] = Field(default_factory=dict)
    bundles: list[BundleManifestEntry] = Field(default_factory=list)
