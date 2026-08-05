"""Session State Analyzer workbench — single entry point, one page tree.

Run from the repo root:

    streamlit run src/session_explorer/workbench/app.py

Navigation is a sidebar table of contents (``st.navigation``) built from the
plain-data registry in :mod:`session_explorer.workbench.nav`. The sidebar's
**Mode** radio switches the *wording* of the tree, not the tree itself:

- **Guided** (default) — the plain-language tour, eight story pages.
- **Expert** — the research workbench, eleven pages in two sections
  (Canonical, Source).

Shared pages keep one stable URL across modes (``/atlas``, ``/same-idea``,
``/state-to-audio``, …), so switching mode stays on the same page — re-worded
— and every exhibit is deep-linkable. Exactly one page executes per rerun.

The workbench is read-only by principle: it presents adapter exports, it
never parses a DAW artifact.
"""

from __future__ import annotations

import streamlit as st

from session_explorer.workbench import copy as wcopy
from session_explorer.workbench import nav
from session_explorer.workbench import state
from session_explorer.workbench import ui

st.set_page_config(
    page_title="Session State Analyzer",
    page_icon="🎛️",
    layout="wide",
)

bundle_names = nav.discovered_bundle_names()

# Widget keys living inside page bodies would have their state
# garbage-collected on every run where their page is not the active one;
# keep() re-asserts them before any page runs. ``bundle_select`` is included
# because its widget (the Expert multiselect) is absent on Guided runs — a
# narrowed selection must survive a mode round trip, not reset to all.
ui.keep("bundle_select", *nav.KEEP_KEYS)

# Shared bundle selection: every discovered bundle auto-loads on first visit;
# Expert's multiselect binds to the same key, so the two modes always agree
# about what is loaded.
if "bundle_select" not in st.session_state:
    st.session_state["bundle_select"] = list(bundle_names)

# A fresh session's mode can be named by the URL: an explicit ?mode= wins
# (it is how a shared-page link like /atlas?mode=expert carries its wording),
# and a deep link to an Expert-only page (/inspector, /native, …) implies
# Expert — the Guided tree doesn't contain those slugs, so the link would
# otherwise 404 into the Guided Overview.
if "app_mode" not in st.session_state:
    _seeded_mode = nav.mode_from_query(st.query_params)
    if _seeded_mode is None:
        try:
            _requested = str(getattr(st.context, "url", "") or "")
        except Exception:  # noqa: BLE001 - context absent under bare execution
            _requested = ""
        _seeded_mode = nav.mode_for_requested_path(_requested)
    if _seeded_mode is not None:
        st.session_state["app_mode"] = _seeded_mode

st.sidebar.title("Session State Analyzer")
mode = st.sidebar.radio(
    wcopy.COPY["mode_label"],
    (wcopy.COPY["mode_guided"], wcopy.COPY["mode_expert"]),
    key="app_mode",
    horizontal=True,
    help=wcopy.COPY["mode_help"],
)

# Keep the URL shareable: reflect a non-default mode in the query string so a
# copied link reopens in the same wording (Guided is the default and carries
# no parameter). Every st.query_params write or delete makes the frontend push
# a browser-history entry — even when the URL doesn't change — so both branches
# are guarded on the parsed value: a URL already naming the current mode (each
# Expert rerun; a hand-made ?mode=guided link) is left untouched, or every
# interaction and every Back press would push a duplicate entry and trap the
# Back button. Only a stale or unrecognized value is dropped.
_url_mode = nav.mode_from_query(st.query_params)
if mode == wcopy.COPY["mode_expert"]:
    if _url_mode != nav.EXPERT:
        st.query_params["mode"] = "expert"
elif _url_mode != nav.GUIDED and "mode" in st.query_params:
    del st.query_params["mode"]

if mode == wcopy.COPY["mode_guided"]:
    st.sidebar.caption(wcopy.COPY["guided_tagline"])
    with st.sidebar.expander(wcopy.COPY["glossary_title"]):
        for term, definition in wcopy.GLOSSARY.items():
            st.markdown(f"**{term}** — {definition}")
    # Surface any broken bundle exactly once per run (page bodies load
    # silently through the cache).
    nav.load_current_bundles(report_errors=True)
else:
    st.sidebar.caption("Four observation instruments, one analysis contract.")
    st.sidebar.caption(wcopy.COPY["expert_switch_hint"])

    if not bundle_names:
        st.sidebar.error(
            f"No snapshot bundles found under {state.FIXTURES_ROOT}."
        )

    st.sidebar.multiselect("Bundles", bundle_names, key="bundle_select")
    _n_bundles = len(bundle_names)
    st.sidebar.button(
        f"Load all {_n_bundles} bundles" if _n_bundles else "Load all bundles",
        on_click=lambda: st.session_state.update(
            bundle_select=list(bundle_names)
        ),
        disabled=not bundle_names,
    )

    load_warnings = [
        f"[{bundle.dir.name}] {warning}"
        for bundle in nav.load_current_bundles(report_errors=True)
        for warning in bundle.load_warnings
    ]
    if load_warnings:
        with st.sidebar.expander(f"Load warnings ({len(load_warnings)})"):
            for warning in load_warnings:
                st.caption(warning)

nav.build_navigation(mode).run()
