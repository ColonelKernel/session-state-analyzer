"""The two-mode workbench over one st.navigation page tree.

Three tiers of coverage, matching what each can actually see:

- **Registry tests** assert the information architecture against
  ``nav.PAGE_SPECS`` directly — the AppTest element tree has no view of
  ``st.navigation``, so the IA is asserted where it is defined.
- **AppTest page runs** assert rendered content, driving non-default pages
  through :func:`nav_testing.goto` (the pinned private-API workaround).
- **Canary tests** guard the two silent failure modes this architecture has:
  the ``showSidebarNavigation`` config key (hides explicit nav) and a sibling
  ``pages/`` directory (Streamlit's V1 autodetection would shadow deep links
  with bare render modules).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tests.analyzer.nav_testing import goto

STREAMLIT_AVAILABLE = importlib.util.find_spec("streamlit") is not None

pytestmark = pytest.mark.skipif(
    not STREAMLIT_AVAILABLE, reason="streamlit not installed (ui extra)"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_PATH = REPO_ROOT / "src" / "session_explorer" / "workbench" / "app.py"
# Every discovered adapter bundle, incl. the real captured sessions — the
# workbench discovers fixtures/adapters/* dynamically.
DAWS = {"ableton", "cubase", "logic", "logic_real", "reaper", "reaper_real"}

# The X06 grouping-depth fixture carries a deliberate feedback pair (a cycle),
# used to prove the cycle badge fires. It is NOT an adapter bundle, so the
# workbench does not discover it — the badge test renders the page directly.
X06_BUNDLE = (
    REPO_ROOT
    / "fixtures"
    / "cross-daw"
    / "X06_grouping_depth"
    / "bundles"
    / "synthetic"
)


def _apptest():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP_PATH), default_timeout=120)


def _markdown_text(at) -> str:
    return " ".join(str(m.value) for m in at.markdown)


def _caption_text(at) -> str:
    return " ".join(str(c.value) for c in at.caption)


def _header_text(at) -> str:
    return " ".join(str(h.value) for h in at.header)


def _expert(at):
    at.run()
    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]
    return at


# ---------------------------------------------------------------------------
# Tier 1 — the information architecture, asserted against the registry
# ---------------------------------------------------------------------------


def test_guided_tree_matches_the_eight_stories_in_order():
    from session_explorer.workbench import copy as wcopy
    from session_explorer.workbench import nav

    titles = [spec.title(nav.GUIDED) for spec in nav.specs_for(nav.GUIDED)]
    assert titles == [
        wcopy.COPY["tab_overview"],
        wcopy.COPY["tab_x04"],
        wcopy.COPY["tab_atlas"],
        wcopy.COPY["tab_graph"],
        wcopy.COPY["tab_grouping"],
        wcopy.COPY["tab_intervention"],
        wcopy.COPY["tab_evolution"],
        wcopy.COPY["tab_comparison"],
    ]


def test_expert_tree_matches_the_eleven_pages_and_sections():
    from session_explorer.workbench import nav

    specs = nav.specs_for(nav.EXPERT)
    assert [s.title(nav.EXPERT) for s in specs if s.section == "Canonical"] == [
        "Graph",
        "Entity inspector",
        "X04 alignment",
        "Observability atlas",
        "State to audio",
        "Routing depth",
        "Parameter influence",
        "Session evolution",
        "Adapter comparison",
    ]
    assert [s.title(nav.EXPERT) for s in specs if s.section == "Source"] == [
        "Native payload",
        "Evidence",
    ]


def test_registry_invariants():
    """Slug uniqueness, one default per mode, and the fully-expanded bound."""
    from session_explorer.workbench import nav

    slugs = [spec.slug for spec in nav.PAGE_SPECS]
    assert len(slugs) == len(set(slugs))

    for mode in (nav.GUIDED, nav.EXPERT):
        specs = nav.specs_for(mode)
        # st.navigation only fully expands trees of <= 12 pages by default.
        assert 1 < len(specs) <= 12
        # NAV_ORDER membership agrees with each spec's declared modes.
        assert set(nav.NAV_ORDER[mode]) == {
            s.slug for s in nav.PAGE_SPECS if mode in s.modes
        }
        # The mode's default page is a member of its tree, exactly once.
        defaults = [s for s in specs if s.slug == nav.DEFAULT_SLUG[mode]]
        assert len(defaults) == 1
        # Every member page can produce a title for this mode.
        for spec in specs:
            assert spec.title(mode)


def test_shared_slugs_are_shared_and_exclusive_pages_are_exclusive():
    from session_explorer.workbench import nav

    by_slug = {spec.slug: spec for spec in nav.PAGE_SPECS}
    for slug in ("same-idea", "atlas", "graph", "routing-depth",
                 "state-to-audio", "evolution", "comparison"):
        assert by_slug[slug].modes == frozenset({nav.GUIDED, nav.EXPERT})
    assert by_slug["overview"].modes == frozenset({nav.GUIDED})
    for slug in ("inspector", "parameter-influence", "native", "evidence"):
        assert by_slug[slug].modes == frozenset({nav.EXPERT})


# ---------------------------------------------------------------------------
# Canaries — the two silent failure modes, guarded in text
# ---------------------------------------------------------------------------


def test_config_canary_no_sidebar_nav_suppression():
    """client.showSidebarNavigation silently hides explicit sidebar nav."""
    config = (REPO_ROOT / ".streamlit" / "config.toml").read_text()
    active = [
        line for line in config.splitlines() if not line.lstrip().startswith("#")
    ]
    assert "showSidebarNavigation" not in "\n".join(active)


def test_no_pages_directory_shadows_the_app():
    """A sibling pages/ dir triggers Streamlit's V1 multipage autodetection:
    deep links whose slug matches a filename would execute that bare module
    instead of app.py and render a blank page."""
    assert not (APP_PATH.parent / "pages").exists()


def test_goto_private_api_canary():
    """goto() rides AppTest._page_hash + calc_hash(url_path); if a Streamlit
    upgrade changes either half, fail here rather than as N empty pages."""
    from streamlit.util import calc_hash

    at = _apptest()
    assert hasattr(at, "_page_hash")
    at.run()
    goto(at, "atlas")
    assert at._page_hash == calc_hash("atlas")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "What each DAW lets us see" in _header_text(at)


# ---------------------------------------------------------------------------
# Tier 2/3 — boot, mode switch, and per-page rendering
# ---------------------------------------------------------------------------


def test_boots_guided_by_default_with_overview_cards():
    """Fresh boot: Guided mode, the Overview page, every discovered bundle
    auto-loaded, one card per DAW."""
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["app_mode"] == wcopy.COPY["mode_guided"]

    # Auto-load on first visit: every discovered fixture bundle is selected.
    assert set(at.session_state["bundle_select"]) == DAWS

    # One card per DAW: every display name appears in the overview markdown.
    body = _markdown_text(at)
    for display_name in ("Ableton Live", "REAPER", "Cubase", "Logic Pro"):
        assert display_name in body

    # Everything is already loaded, so the no-op "Load all" button is hidden
    # and the confirmation caption shows instead.
    button_labels = {b.label for b in at.button}
    assert wcopy.COPY["load_examples"] not in button_labels
    assert wcopy.COPY["all_loaded"].format(n=len(DAWS)) in (
        body + " " + _caption_text(at)
    )


def test_mode_switch_lands_on_the_expert_graph():
    at = _expert(_apptest())
    # Graph is the Expert default page; it rendered through a real backend.
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")
    # The sidebar holds only the Mode radio (the View radio is gone).
    assert [str(r.label) for r in at.sidebar.radio] == ["Mode"]
    # The layer radio lives on the Graph page.
    layer = [r for r in at.radio if r.key == "graph_layer_expert"]
    assert len(layer) == 1
    assert layer[0].value == "all"


def test_mode_switch_stays_on_the_same_shared_page():
    """The unified tree's headline win: switching mode on /atlas stays on the
    atlas, re-worded."""
    at = _apptest()
    at.run()
    goto(at, "atlas")
    at.run()
    assert "What each DAW lets us see" in _header_text(at)  # guided wording

    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Observability atlas" in _header_text(at)  # expert wording


def test_mode_switch_stays_on_the_graph_in_both_directions():
    """Regression: default pages must carry their slug as url_path — hashing
    the callable name instead gave the shared Graph page two identities, so
    Expert -> Guided on Graph silently landed on Overview."""
    from streamlit.util import calc_hash

    # Expert -> Guided, standing on the Expert default (Graph). Simulate the
    # frontend holding the Graph page's real hash, as the browser would.
    at = _expert(_apptest())
    at._page_hash = calc_hash("graph")
    at.run()
    assert [r for r in at.radio if r.key == "graph_layer_expert"]
    at.sidebar.radio[0].set_value("Guided").run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Explore the graph" in _header_text(at)
    assert [r for r in at.radio if r.key == "guided_graph_layer"]

    # Guided -> Expert on /graph.
    at2 = _apptest()
    at2.run()
    goto(at2, "graph")
    at2.run()
    assert "Explore the graph" in _header_text(at2)
    at2.sidebar.radio[0].set_value("Expert").run()
    assert not at2.exception, [e.value for e in at2.exception]
    assert [r for r in at2.radio if r.key == "graph_layer_expert"]


def test_bundle_narrowing_survives_a_mode_round_trip():
    """Regression: the Expert multiselect's ``bundle_select`` is kept alive on
    Guided runs (where its widget doesn't exist) — a narrowed selection must
    not silently reset to all bundles."""
    at = _expert(_apptest())
    at.sidebar.multiselect[0].set_value(["reaper"]).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["bundle_select"] == ["reaper"]

    at.sidebar.radio[0].set_value("Guided").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["bundle_select"] == ["reaper"]

    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["bundle_select"] == ["reaper"]
    assert list(at.sidebar.multiselect[0].value) == ["reaper"]


def test_mode_query_param_seeds_and_reflects():
    """?mode=expert boots a fresh session into Expert; the mode radio keeps
    the URL shareable by reflecting a non-default mode back into the query
    string. A URL that already names the current mode is never rewritten —
    every query-param write or delete pushes a browser-history entry, so
    rewriting on each rerun (or canonicalizing away an explicit ?mode=guided)
    would trap the Back button."""
    from session_explorer.workbench import nav

    # Seeding: a fresh session with ?mode=expert boots into Expert.
    at = _apptest()
    at.query_params["mode"] = "expert"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["app_mode"] == "Expert"
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")
    # Steady state: the parameter stays put across reruns.
    at.run()
    assert at.query_params.get("mode") in ("expert", ["expert"])

    # Helper contract (query beats path inference; unknown values ignored).
    assert nav.mode_from_query({"mode": "expert"}) == nav.EXPERT
    assert nav.mode_from_query({"mode": "Guided"}) == nav.GUIDED
    assert nav.mode_from_query({"mode": "banana"}) is None
    assert nav.mode_from_query({}) is None

    # Reflection: switching modes rewrites the query string. A stale
    # "expert" is dropped when the radio goes back to Guided (the default
    # carries no parameter).
    at2 = _apptest()
    at2.run()
    assert "mode" not in at2.query_params  # Guided default carries no param
    at2.sidebar.radio[0].set_value("Expert").run()
    assert at2.query_params.get("mode") in ("expert", ["expert"])
    at2.sidebar.radio[0].set_value("Guided").run()
    assert "mode" not in at2.query_params

    # An explicit ?mode=guided seeds Guided and STAYS in the URL — deleting
    # it would push a canonicalized history entry on every Back press.
    at3 = _apptest()
    at3.query_params["mode"] = "guided"
    at3.run()
    assert not at3.exception, [e.value for e in at3.exception]
    assert at3.session_state["app_mode"] == "Guided"
    assert at3.query_params.get("mode") in ("guided", ["guided"])


def test_fixture_backed_pages_declare_their_scope():
    """The empty-state rule: fixture-backed exhibits always render, and say
    so — a one-line caption declares independence from the sidebar selection
    on all three surfaces, in both modes' wording."""
    from session_explorer.workbench import copy as wcopy
    from session_explorer.workbench import ui as wui

    for slug in ("same-idea", "state-to-audio", "evolution"):
        at = _apptest()
        at.run()
        goto(at, slug)
        at.run()
        assert not at.exception, [e.value for e in at.exception]
        assert wcopy.COPY["fixture_scope"] in _caption_text(at), slug

        at.sidebar.radio[0].set_value("Expert").run()
        assert not at.exception, [e.value for e in at.exception]
        assert wui.FIXTURE_SCOPE_NOTE in _caption_text(at), slug


def test_expert_only_deep_links_seed_expert_mode():
    """A fresh session deep-linking an Expert-only slug must boot into Expert
    (the Guided tree lacks the slug; the link would 404 into Overview).
    The URL itself is not drivable under AppTest, so assert the seeding
    helper's contract directly."""
    from session_explorer.workbench import nav

    assert nav.EXPERT_ONLY_SLUGS == {
        "inspector", "parameter-influence", "native", "evidence",
    }
    for slug in nav.EXPERT_ONLY_SLUGS:
        assert nav.mode_for_requested_path(f"http://x/{slug}") == nav.EXPERT
        assert nav.mode_for_requested_path(f"/{slug}?embed=true") == nav.EXPERT
    for path in ("", None, "/", "/atlas", "/graph", "http://x/comparison"):
        assert nav.mode_for_requested_path(path) is None


def test_graph_layer_choice_survives_visiting_another_page():
    """KEEP_KEYS regression: the layer radio only exists on the Graph page,
    so its state must survive a round trip through another page."""
    at = _expert(_apptest())
    layer = [r for r in at.radio if r.key == "graph_layer_expert"][0]
    layer.set_value("processing")
    at.run()
    assert not at.exception, [e.value for e in at.exception]

    goto(at, "evidence")
    at.run()
    assert not at.exception, [e.value for e in at.exception]

    goto(at, "")  # back to the Expert default: Graph
    at.run()
    layer = [r for r in at.radio if r.key == "graph_layer_expert"][0]
    assert layer.value == "processing"


def test_bundle_focus_is_shared_across_pages():
    """One focused bundle follows the user from page to page."""
    at = _expert(_apptest())

    def picker(key):
        return [s for s in at.selectbox if s.key == key][0]

    goto(at, "inspector")
    at.run()
    picker("inspector_bundle").set_value("cubase")
    at.run()
    assert at.session_state["focus_bundle"] == "cubase"

    goto(at, "routing-depth")
    at.run()
    assert picker("depth_bundle_expert").value == "cubase"

    picker("depth_bundle_expert").set_value("reaper_real")
    at.run()
    goto(at, "inspector")
    at.run()
    assert picker("inspector_bundle").value == "reaper_real"

    goto(at, "parameter-influence")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert picker("param_influence_bundle").value == "reaper_real"

    goto(at, "native")
    at.run()
    assert picker("bundle_for_native").value == "reaper_real"


def test_unloading_the_focused_bundle_moves_the_focus_with_the_display():
    """Focus always equals what is displayed: unloading the focused bundle
    moves the focus to the fallback, so re-loading the old bundle later does
    not snap every picker back mid-analysis."""
    at = _expert(_apptest())
    goto(at, "inspector")
    at.run()

    def picker(key):
        return [s for s in at.selectbox if s.key == key][0]

    picker("inspector_bundle").set_value("cubase")
    at.run()
    assert at.session_state["focus_bundle"] == "cubase"

    remaining = [n for n in at.session_state["bundle_select"] if n != "cubase"]
    at.sidebar.multiselect[0].set_value(remaining).run()
    assert not at.exception, [e.value for e in at.exception]
    displayed = picker("inspector_bundle").value
    assert displayed != "cubase"
    assert at.session_state["focus_bundle"] == displayed

    # Re-adding cubase must not steal the focus back.
    at.sidebar.multiselect[0].set_value(remaining + ["cubase"]).run()
    assert not at.exception, [e.value for e in at.exception]
    assert picker("inspector_bundle").value == displayed


# ---------------------------------------------------------------------------
# Guided story pages
# ---------------------------------------------------------------------------


def test_guided_x04_story_renders_the_four_columns():
    """The four native-mechanism cards: each DAW's own noun on screen."""
    at = _apptest()
    at.run()
    goto(at, "same-idea")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    body = _markdown_text(at)
    for noun in ("Return Track", "FX Channel", "Aux Channel Strip"):
        assert noun in body
    assert "What Ableton Live calls it:" in body


def test_expert_x04_alignment_page_renders():
    """The Expert face of /same-idea: the research alignment page."""
    at = _expert(_apptest())
    goto(at, "same-idea")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "X04 — effect return, aligned across four DAWs" in _header_text(at)
    # The pairwise alignment table rendered.
    assert len(at.dataframe) >= 1


def test_guided_groups_and_feedback_page_renders():
    """The Guided face of /routing-depth: plain-language group decomposition."""
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    goto(at, "routing-depth")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert wcopy.DEPTH["guided_header"] in _header_text(at)


def test_guided_atlas_renders_friendly_rows():
    at = _apptest()
    at.run()
    goto(at, "atlas")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    body = _markdown_text(at)
    for label in ("Tracks & layout", "Signal routing", "Effects & processing"):
        assert label in body


def test_guided_graph_renders_with_relabeled_layers():
    at = _apptest()
    at.run()
    goto(at, "graph")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    layer_radio = [r for r in at.radio if r.key == "guided_graph_layer"]
    assert len(layer_radio) == 1
    assert layer_radio[0].value == "Everything"
    assert list(layer_radio[0].options) == [
        "How things are organized",
        "How audio flows",
        "Effect chains",
        "Automation & control",
        "Session versions",
        "Everything",
    ]
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")

    layer_radio[0].set_value("How audio flows")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")

    layer_radio[0].set_value("Effect chains")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["graph_backend"] in ("pyvis", "plotly")


def test_glossary_present_in_guided_mode():
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    expander_labels = {e.label for e in at.expander}
    assert wcopy.COPY["glossary_title"] in expander_labels
    body = _markdown_text(at)
    for term in wcopy.GLOSSARY:
        assert term in body


# ---------------------------------------------------------------------------
# Shared pages render in both modes
# ---------------------------------------------------------------------------


def test_intervention_parameter_experiment_renders_in_both_modes():
    """The intervention page dispatches the Delay-feedback A/B in each mode —
    and the mode switch itself stays on the state-to-audio page."""
    at = _apptest()
    at.run()
    goto(at, "state-to-audio")
    at.run()
    guided_sel = [r for r in at.radio if r.key == "intervention_experiment_guided"]
    assert len(guided_sel) == 1
    guided_sel[0].set_value("Delay feedback").run()
    assert not at.exception, [e.value for e in at.exception]

    at.sidebar.radio[0].set_value("Expert").run()
    expert_sel = [r for r in at.radio if r.key == "intervention_experiment_expert"]
    assert len(expert_sel) == 1
    expert_sel[0].set_value("Delay feedback").run()
    assert not at.exception, [e.value for e in at.exception]


def test_session_evolution_page_renders_in_both_modes():
    """Whether the variants module/fixtures are present (a live selector) or
    absent (the honest info note) — never an exception."""
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    goto(at, "evolution")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]
    info_text = " ".join(str(i.value) for i in at.info)
    family_selectors = [s for s in at.selectbox if s.key == "evolution_family"]
    assert (wcopy.EVOLUTION["unavailable"] in info_text) or family_selectors


def _download_labels(at) -> set[str]:
    return {d.label for d in at.get("download_button")}


def _assert_comparison_dashboard(at) -> None:
    from session_explorer.workbench import copy as wcopy

    body = _markdown_text(at)
    for rung in ("L0", "L2", "L6"):
        assert rung in body
    info_text = " ".join(str(i.value) for i in at.info)
    assert wcopy.COMPARISON["caption_not_ranking"] in info_text
    labels = _download_labels(at)
    assert wcopy.COMPARISON["download_metrics"] in labels
    assert wcopy.COMPARISON["download_ladder"] in labels


def test_comparison_dashboard_renders_ladder_chips_and_downloads_expert():
    at = _expert(_apptest())
    goto(at, "comparison")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    _assert_comparison_dashboard(at)


def test_comparison_dashboard_renders_ladder_chips_and_downloads_guided():
    at = _apptest()
    at.run()
    goto(at, "comparison")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    _assert_comparison_dashboard(at)


# ---------------------------------------------------------------------------
# Cycle badge: fires as a finding on a cycle-bearing bundle
# ---------------------------------------------------------------------------


def test_cycle_badge_appears_on_a_feedback_bearing_bundle():
    """Rendering the X06 grouping-depth bundle surfaces the feedback finding."""
    from streamlit.testing.v1 import AppTest

    def _script(bundle_path: str):
        from session_explorer.loaders import load_bundle
        from session_explorer.workbench.views import canonical_graph

        bundle = load_bundle(bundle_path)
        canonical_graph.render([bundle], "all")

    at = AppTest.from_function(
        _script, args=(str(X06_BUNDLE),), default_timeout=120
    )
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["graph_has_cycles"] is True
    warnings = " ".join(str(w.value) for w in at.warning)
    assert "Feedback loop detected" in warnings


def test_no_cycle_badge_on_adapter_bundles():
    """The discovered adapter bundles carry no routing feedback: the Expert
    default (Graph) renders with no false finding."""
    at = _expert(_apptest())
    assert at.session_state["graph_has_cycles"] is False
