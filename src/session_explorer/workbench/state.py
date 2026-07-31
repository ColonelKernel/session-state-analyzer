"""Cached bundle loading for the workbench.

Bundles are cached on (path, snapshot mtime): editing a fixture bundle on
disk invalidates its cache entry without restarting the app.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from session_explorer.loaders import SnapshotBundle, load_bundle

SNAPSHOT_FILE = "canonical.snapshot.json"


@st.cache_data(show_spinner="Loading snapshot bundle…")
def _load_bundle(path_str: str, mtime_ns: int) -> SnapshotBundle:
    # mtime_ns participates in the cache key only.
    return load_bundle(Path(path_str))


def _snapshot_mtime_ns(bundle_dir: Path) -> int:
    snapshot_path = bundle_dir / SNAPSHOT_FILE
    return snapshot_path.stat().st_mtime_ns if snapshot_path.is_file() else 0


def load_bundle_cached(path: Path | str) -> SnapshotBundle:
    """Load a bundle through the Streamlit cache, keyed on path + mtime."""
    bundle_dir = Path(path)
    return _load_bundle(str(bundle_dir), _snapshot_mtime_ns(bundle_dir))


def bundle_key(bundle: SnapshotBundle) -> tuple[str, int]:
    """A stable, hashable identity for a loaded bundle: (dir, snapshot mtime).

    This is the same key :func:`load_bundle_cached` memoizes on, so downstream
    caches (see :mod:`session_explorer.workbench.compute`) can key on it and
    reload the bundle from the cache on a hit — invalidating exactly when the
    snapshot on disk changes.
    """
    bundle_dir = Path(bundle.dir)
    return (str(bundle_dir), _snapshot_mtime_ns(bundle_dir))


def discover_bundle_dirs(root: Path) -> list[Path]:
    """Bundle directories under ``root`` (anything with a canonical snapshot)."""
    if not root.is_dir():
        return []
    return sorted(
        child
        for child in root.iterdir()
        if child.is_dir() and (child / SNAPSHOT_FILE).is_file()
    )
