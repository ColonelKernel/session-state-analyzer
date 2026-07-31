"""Rerun-stable memoization for the workbench's heavy computations.

Streamlit re-executes the whole script — and *every* ``st.tabs`` body, since
tabs are hidden with CSS, not rendered lazily — on each widget interaction. So
anything below the bundle loader recomputes on every click: the atlas is rebuilt
in three tabs, the six-pair X04 alignment runs three times, the canonical graph
is recomposed and its cycles re-detected. None of it is keyed on anything.

The builders in :mod:`session_explorer` take Pydantic snapshots / ``SnapshotBundle``
objects, which Streamlit cannot hash, and ``st.cache_data`` hands back a *copy*
of its result each call — so downstream code cannot cache on object identity
either. Each wrapper here turns its inputs into a **stable scalar key** (bundle
directory + snapshot mtime — the very key :func:`state.load_bundle_cached`
memoizes on), reloads the bundles from that key *inside* the cached function, and
lets Streamlit key on content. Editing a fixture on disk still invalidates,
mirroring the loader's contract; within a single rerun the repeated calls become
one compute plus cheap cache hits.
"""

from __future__ import annotations

from typing import List, Tuple

import streamlit as st

from session_explorer.atlas import Atlas, build_atlas
from session_explorer.graph_layers import annotate_cycles, build_graph, build_multi, detect_cycles
from session_explorer.loaders import SnapshotBundle

from .state import bundle_key, load_bundle_cached

# (bundle dir, snapshot mtime_ns) — the hashable identity a cache keys on.
BundleKey = Tuple[str, int]


def _keys(bundles: List[SnapshotBundle]) -> Tuple[BundleKey, ...]:
    return tuple(bundle_key(b) for b in bundles)


def _reload(keys: Tuple[BundleKey, ...]) -> List[SnapshotBundle]:
    """Re-materialize bundles from their keys — a cache hit in the loader."""
    return [load_bundle_cached(dir_str) for dir_str, _mtime in keys]


# --- observability atlas ---------------------------------------------------


@st.cache_data(show_spinner=False)
def _atlas(keys: Tuple[BundleKey, ...]) -> Atlas:
    return build_atlas(_reload(keys))


def atlas_for(bundles: List[SnapshotBundle]) -> Atlas:
    """The observability atlas over ``bundles``, memoized across reruns and tabs.

    Column order matches ``bundles`` order (see :func:`atlas.build_atlas`), so
    callers may still zip ``bundles`` with ``atlas.columns`` / ``column_keys``.
    """
    return _atlas(_keys(bundles))


# --- canonical graph -------------------------------------------------------


@st.cache_data(show_spinner=False)
def _graph(keys: Tuple[BundleKey, ...], layer: str):
    bundles = _reload(keys)
    graph = build_multi([b.snapshot for b in bundles], layer=layer)
    report = detect_cycles(graph)
    annotate_cycles(graph, report)  # rides ``in_cycle`` into the cached graph
    return graph, report


def graph_for(bundles: List[SnapshotBundle], layer: str):
    """The composed, cycle-annotated canonical graph and its cycle report.

    Returns ``(graph, cycle_report)``; the caller still applies the interactive
    observability filter and renders — only the expensive compose + cycle
    detection is memoized.
    """
    return _graph(_keys(bundles), layer)


# --- per-channel processing subgraph (routing-depth tab) -------------------


@st.cache_data(show_spinner=False)
def _processing_graph(key: BundleKey):
    bundle = load_bundle_cached(key[0])
    return build_graph(bundle.snapshot, layer="processing")


def processing_graph_for(bundle: SnapshotBundle):
    """The processing-layer graph for one bundle, memoized."""
    return _processing_graph(bundle_key(bundle))
