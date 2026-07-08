"""Dataset export (master-prompt §57): package the frozen corpus for release.

Writes the standard ``dataset/{snapshots,native,renders,observations,
interventions,alignments,fixtures,metrics}`` tree — *descriptors only, never
WAV* — with every artifact sanitized on the way out. This is infrastructure:
building an ML model over the exported descriptors is explicitly out of scope.

Public surface:

- :func:`build_dataset` — build the whole tree, returning its
  :class:`DatasetManifest`.
- :class:`DatasetManifest` — the machine-readable index of the tree.
- :func:`sanitize_snapshot`, :func:`redact_paths`, :func:`hash_asset_path` — the
  sanitization primitives, exposed for reuse and testing.
"""

from __future__ import annotations

from .build import build_dataset
from .layout import (
    DATASET_SCHEMA_VERSION,
    SUBDIRS,
    BundleManifestEntry,
    DatasetManifest,
)
from .sanitize import (
    hash_asset_path,
    redact_paths,
    sanitize_json,
    sanitize_native,
    sanitize_snapshot,
)

__all__ = [
    "build_dataset",
    "DatasetManifest",
    "BundleManifestEntry",
    "DATASET_SCHEMA_VERSION",
    "SUBDIRS",
    "sanitize_snapshot",
    "sanitize_native",
    "sanitize_json",
    "redact_paths",
    "hash_asset_path",
]
