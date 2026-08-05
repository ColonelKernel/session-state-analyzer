"""The workbench's navigation: one unified page tree, two modes of wording.

``PAGE_SPECS`` is a plain-data registry — no Streamlit objects — so tests can
import and assert the information architecture directly (the AppTest element
tree cannot see ``st.navigation`` at all). :func:`build_navigation` turns the
registry into ``st.navigation`` for the current mode.

The unifying idea: Guided and Expert are **two wordings of one tree**, not two
trees. A shared page keeps one stable ``url_path`` across modes, so switching
mode stays on the same page — re-worded — and every exhibit is deep-linkable
(``/atlas``, ``/same-idea``, ``/state-to-audio``). Four pages are
mode-exclusive: Overview exists only in Guided; Entity inspector, Parameter
influence, Native payload, and Evidence only in Expert. Each mode's *default*
page (Guided: Overview; Expert: Graph) also serves at the app root; every page
— defaults included — carries its slug as ``url_path`` so its identity (the
script hash) is stable across modes.

Page bodies load their own bundles through the cached loader (cheap on every
call after the first) and dispatch on the mode radio's session value, so
``st.Page`` gets the zero-argument callables it requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, FrozenSet, List, Optional

import streamlit as st

from session_explorer.loaders import SnapshotBundle
from session_explorer.workbench import copy as wcopy
from session_explorer.workbench import state
from session_explorer.workbench.views import (
    alignment,
    atlas,
    canonical_graph,
    comparison,
    depth,
    entity_inspector,
    evidence,
    guided,
    intervention,
    native,
    parameter_influence,
    session_evolution,
)

GUIDED = wcopy.COPY["mode_guided"]
EXPERT = wcopy.COPY["mode_expert"]

LAYER_OPTIONS = (
    "organizational",
    "signal_flow",
    "processing",
    "automation",
    "variant",
    "all",
)

# Widget keys whose widgets live inside page bodies. A widget's state is
# garbage-collected on any run where its page is not the active one, so the
# entry script re-asserts these through ui.keep() before pg.run(). The
# pick_bundle widget keys are absent by design — pick_bundle repairs them from
# the always-alive ``focus_bundle`` before instantiation every run.
KEEP_KEYS: tuple[str, ...] = (
    "graph_layer_expert",
    "guided_graph_layer",
    # Graph observability-filter checkboxes (one per class present).
    "obs_observed",
    "obs_inferred",
    "obs_annotation",
    "obs_hidden",
    "obs_derived",
    "obs_unknown",
    "atlas_dd_domain",
    "atlas_dd_daw",
    "depth_group_expert",
    "depth_group_guided",
    "depth_channel_expert",
    "inspector_entity",
    "param_influence_target",
    "evolution_family",
    "intervention_experiment_expert",
    "intervention_experiment_guided",
    "alignment_concepts",
)


# ---------------------------------------------------------------------------
# Shared context for page bodies
# ---------------------------------------------------------------------------


def current_mode() -> str:
    return st.session_state.get("app_mode", GUIDED)


def discovered_bundle_names() -> List[str]:
    return [path.name for path in state.discover_bundle_dirs(state.FIXTURES_ROOT)]


def load_current_bundles(report_errors: bool = False) -> List[SnapshotBundle]:
    """The bundles selected in the sidebar, through the cached loader.

    Called once by the entry script (with ``report_errors=True``, so a broken
    bundle surfaces exactly one sidebar error per run) and again by the active
    page body (silently — the loads are cache hits, and reporting here too
    would render every error twice).
    """
    loaded: List[SnapshotBundle] = []
    for name in st.session_state.get("bundle_select", []):
        try:
            loaded.append(state.load_bundle_cached(state.FIXTURES_ROOT / name))
        except Exception as exc:  # noqa: BLE001 - a bad bundle must not kill the app
            if report_errors:
                st.sidebar.error(f"Failed to load bundle '{name}': {exc}")
    return loaded


# ---------------------------------------------------------------------------
# Page bodies — zero-argument callables for st.Page, dispatching on mode
# ---------------------------------------------------------------------------


def _page_overview() -> None:
    guided.render_overview(load_current_bundles(), discovered_bundle_names())


def _page_same_idea() -> None:
    if current_mode() == EXPERT:
        alignment.render()
    else:
        guided.render_x04()


def _page_atlas() -> None:
    if current_mode() == EXPERT:
        atlas.render(load_current_bundles())
    else:
        guided.render_atlas(load_current_bundles())


def _page_graph() -> None:
    if current_mode() == EXPERT:
        # The layer choice affects only this page; ui.keep() preserves its
        # state while other pages (or Guided mode) are showing.
        layer = st.radio(
            "Graph layer",
            LAYER_OPTIONS,
            index=LAYER_OPTIONS.index("all"),
            horizontal=True,
            key="graph_layer_expert",
        )
        canonical_graph.render(load_current_bundles(), layer)
    else:
        guided.render_graph(load_current_bundles())


def _page_routing_depth() -> None:
    if current_mode() == EXPERT:
        depth.render(load_current_bundles())
    else:
        depth.render_guided(load_current_bundles())


def _page_state_to_audio() -> None:
    if current_mode() == EXPERT:
        intervention.render_expert()
    else:
        intervention.render_guided()


def _page_evolution() -> None:
    if current_mode() == EXPERT:
        session_evolution.render(load_current_bundles())
    else:
        session_evolution.render_guided(load_current_bundles())


def _page_comparison() -> None:
    if current_mode() == EXPERT:
        comparison.render(load_current_bundles())
    else:
        comparison.render_guided(load_current_bundles())


def _page_inspector() -> None:
    entity_inspector.render(load_current_bundles())


def _page_parameter_influence() -> None:
    parameter_influence.render(load_current_bundles())


def _page_native() -> None:
    native.render(load_current_bundles())


def _page_evidence() -> None:
    evidence.render(load_current_bundles())


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageSpec:
    """One destination in the unified tree — plain data, importable by tests."""

    slug: str                 # stable url_path (the default page renders at /)
    section: str              # Expert sidebar section; Guided renders flat
    modes: FrozenSet[str]     # which modes show this page
    icon: str                 # :material/...: icon for the nav entry
    title_guided: Optional[str]
    title_expert: Optional[str]
    body: Callable[[], None]

    def title(self, mode: str) -> str:
        title = self.title_guided if mode == GUIDED else self.title_expert
        assert title is not None, f"page '{self.slug}' has no title for {mode}"
        return title


_BOTH = frozenset({GUIDED, EXPERT})
_GUIDED_ONLY = frozenset({GUIDED})
_EXPERT_ONLY = frozenset({EXPERT})

# The page each mode opens on; it renders at the app root.
DEFAULT_SLUG = {GUIDED: "overview", EXPERT: "graph"}

PAGE_SPECS: tuple[PageSpec, ...] = (
    PageSpec(
        slug="overview",
        section="Canonical",
        modes=_GUIDED_ONLY,
        icon=":material/home:",
        title_guided=wcopy.COPY["tab_overview"],
        title_expert=None,
        body=_page_overview,
    ),
    PageSpec(
        slug="same-idea",
        section="Canonical",
        modes=_BOTH,
        icon=":material/join_inner:",
        title_guided=wcopy.COPY["tab_x04"],
        title_expert="X04 alignment",
        body=_page_same_idea,
    ),
    PageSpec(
        slug="atlas",
        section="Canonical",
        modes=_BOTH,
        icon=":material/map:",
        title_guided=wcopy.COPY["tab_atlas"],
        title_expert="Observability atlas",
        body=_page_atlas,
    ),
    PageSpec(
        slug="graph",
        section="Canonical",
        modes=_BOTH,
        icon=":material/hub:",
        title_guided=wcopy.COPY["tab_graph"],
        title_expert="Graph",
        body=_page_graph,
    ),
    PageSpec(
        slug="inspector",
        section="Canonical",
        modes=_EXPERT_ONLY,
        icon=":material/search:",
        title_guided=None,
        title_expert="Entity inspector",
        body=_page_inspector,
    ),
    PageSpec(
        slug="routing-depth",
        section="Canonical",
        modes=_BOTH,
        icon=":material/account_tree:",
        title_guided=wcopy.COPY["tab_grouping"],
        title_expert="Routing depth",
        body=_page_routing_depth,
    ),
    PageSpec(
        slug="state-to-audio",
        section="Canonical",
        modes=_BOTH,
        icon=":material/graphic_eq:",
        title_guided=wcopy.COPY["tab_intervention"],
        title_expert="State to audio",
        body=_page_state_to_audio,
    ),
    PageSpec(
        slug="parameter-influence",
        section="Canonical",
        modes=_EXPERT_ONLY,
        icon=":material/tune:",
        title_guided=None,
        title_expert="Parameter influence",
        body=_page_parameter_influence,
    ),
    PageSpec(
        slug="evolution",
        section="Canonical",
        modes=_BOTH,
        icon=":material/history:",
        title_guided=wcopy.COPY["tab_evolution"],
        title_expert="Session evolution",
        body=_page_evolution,
    ),
    PageSpec(
        slug="comparison",
        section="Canonical",
        modes=_BOTH,
        icon=":material/compare:",
        title_guided=wcopy.COPY["tab_comparison"],
        title_expert="Adapter comparison",
        body=_page_comparison,
    ),
    PageSpec(
        slug="native",
        section="Source",
        modes=_EXPERT_ONLY,
        icon=":material/data_object:",
        title_guided=None,
        title_expert="Native payload",
        body=_page_native,
    ),
    PageSpec(
        slug="evidence",
        section="Source",
        modes=_EXPERT_ONLY,
        icon=":material/receipt_long:",
        title_guided=None,
        title_expert="Evidence",
        body=_page_evidence,
    ),
)


# Slugs that exist only in the Expert tree. A fresh session deep-linking one
# of these must boot into Expert mode, or the URL would 404 into the Guided
# default (the entry script seeds ``app_mode`` from the requested path).
EXPERT_ONLY_SLUGS: frozenset[str] = frozenset(
    spec.slug for spec in PAGE_SPECS if spec.modes == _EXPERT_ONLY
)


def mode_for_requested_path(path: str | None) -> str | None:
    """The mode a fresh session should boot into for ``path``, or None.

    Only Expert-exclusive slugs force a mode; every other path (shared slugs,
    the root, unknown paths) leaves the default alone.
    """
    if not path:
        return None
    slug = path.strip("/").split("/")[-1].split("?")[0]
    return EXPERT if slug in EXPERT_ONLY_SLUGS else None


# Sidebar order per mode — the two faces tell the same story in a different
# sequence (Guided is a tour that opens with the X04 hook; Expert leads with
# the flagship graph). Membership must agree with each spec's ``modes``; the
# registry invariants test enforces the consistency.
NAV_ORDER: dict[str, tuple[str, ...]] = {
    GUIDED: (
        "overview",
        "same-idea",
        "atlas",
        "graph",
        "routing-depth",
        "state-to-audio",
        "evolution",
        "comparison",
    ),
    EXPERT: (
        "graph",
        "inspector",
        "same-idea",
        "atlas",
        "state-to-audio",
        "routing-depth",
        "parameter-influence",
        "evolution",
        "comparison",
        "native",
        "evidence",
    ),
}


def specs_for(mode: str) -> tuple[PageSpec, ...]:
    by_slug = {spec.slug: spec for spec in PAGE_SPECS}
    return tuple(by_slug[slug] for slug in NAV_ORDER[mode])


def build_navigation(mode: str):
    """``st.navigation`` for ``mode`` — Guided flat, Expert sectioned."""
    flat: list = []
    sections: dict[str, list] = {}
    for spec in specs_for(mode):
        is_default = spec.slug == DEFAULT_SLUG[mode]
        page = st.Page(
            spec.body,
            title=spec.title(mode),
            icon=spec.icon,
            # Always pass the slug — including on the default page. A default
            # page still serves at the app root (its public url_path is ""),
            # but its script hash is calc_hash(_url_path); leaving url_path
            # unset would hash the callable's __name__ instead, giving the
            # shared page two identities across modes and breaking
            # "mode switch stays on the same page" for the default slugs.
            url_path=spec.slug,
            default=is_default,
        )
        if mode == GUIDED:
            flat.append(page)
        else:
            sections.setdefault(spec.section, []).append(page)
    return st.navigation(flat if mode == GUIDED else sections, position="sidebar")
