"""The Observability Atlas (P5) over the four real fixture bundles.

Asserts the measured atlas arithmetic against the verified fixture shapes, the
declared-capability mapping, and the honest-empty rows (Modulation everywhere;
NOT_APPLICABLE where a domain has neither scope nor a declared capability).
Plus a Streamlit AppTest smoke test that the 4th tab boots and renders.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from session_explorer.atlas import (
    ATLAS_DOMAINS,
    build_atlas,
    declared_domain,
    get_domain,
    measure_domain,
    unknown_state_map,
)
from session_explorer.loaders.bundle import load_bundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "adapters"
DAWS = ("reaper", "ableton", "cubase", "logic")

# The source.daw id each fixture reports (columns are keyed by this).
DAW_ID = {
    "reaper": "reaper",
    "ableton": "ableton_live",
    "cubase": "cubase",
    "logic": "logic_pro",
}


def _bundle(daw: str):
    path = FIXTURES / daw
    if not (path / "canonical.snapshot.json").exists():
        pytest.skip(f"no frozen bundle for {daw}")
    return load_bundle(path)


@pytest.fixture(scope="module")
def bundles():
    return {daw: _bundle(daw) for daw in DAWS}


@pytest.fixture(scope="module")
def atlas(bundles):
    # Ordered reaper, ableton, cubase, logic.
    return build_atlas([bundles[d] for d in DAWS])


# --- taxonomy -------------------------------------------------------------


def test_ten_domains_in_order():
    assert ATLAS_DOMAINS == [
        "Structure",
        "Timeline",
        "Routing",
        "Processing",
        "Parameters",
        "Automation",
        "Modulation",
        "Musical Content",
        "Native Features",
        "Audio Outcome",
    ]


def test_channel_assigned_to_routing_not_structure():
    """The documented modelling choice: CHANNEL is signal-flow, not structure."""
    assert "CHANNEL" in get_domain("Routing").entity_types
    assert "CHANNEL" not in get_domain("Structure").entity_types
    # channel + mixer_state capability domains ride with Routing.
    assert {"channel", "mixer_state"} <= get_domain("Routing").capability_domains


def test_build_atlas_assembles_ten_by_four(atlas):
    assert atlas.domains == ATLAS_DOMAINS
    assert atlas.daws == ["reaper", "ableton_live", "cubase", "logic_pro"]
    assert len(atlas.cells) == 10 * 4


# --- measured math (verified counts) --------------------------------------


def test_reaper_structure_applicable_ten_all_present(bundles):
    """1 PROJECT + 9 TRACK = 10 applicable, all OBSERVED at entity baseline."""
    m = measure_domain(bundles["reaper"].snapshot, get_domain("Structure"))
    assert m.applicable == 10
    assert m.observed == 10
    assert m.hidden == 0
    # The 9 INFERRED semantic_roles are preserved for drill-down, off the
    # applicable denominator (so combined_coverage stays <= 1.0).
    assert len(m.field_refs.get("inferred", [])) == 9


def test_reaper_parameters_not_applicable(atlas):
    """No PARAMETER entities and no `parameters` cap-domain -> NOT_APPLICABLE."""
    cell = atlas.cell("Parameters", "reaper")
    assert cell.measured.applicable == 0
    assert cell.declared is None
    assert cell.status == "NOT_APPLICABLE"


def test_logic_routing_no_channels_but_declared(atlas):
    """Logic observes no CHANNEL entities; routing rides on annotation/manifest."""
    cell = atlas.cell("Routing", "logic_pro")
    # No CHANNEL / ROUTING entities in the logic snapshot.
    assert cell.measured.applicable == 0
    # But the manifest declares routing + mixer_state read capability.
    assert cell.declared is not None
    assert cell.declared.field_count > 0
    assert cell.status == "DECLARED_ONLY"


def test_logic_structure_has_unknown_and_annotation(atlas):
    """Logic Structure carries UNKNOWN channel-availability and ANNOTATED roles."""
    m = atlas.cell("Structure", "logic_pro").measured
    assert m.applicable > 0
    # 8 tracks (full-evidence demo stems) each flag `channel: UNKNOWN`.
    assert m.unknown == 8


def test_logic_audio_outcome_now_measured(atlas):
    """The full-evidence Logic bundle populates Audio Outcome.

    Previously the row was DECLARED_ONLY (audio_content capability, no
    OBSERVATION entities). The refreshed fixture carries stem-sum
    reconciliation + reference comparison as OBSERVATION entities with
    INFERRED (derived_computation) provenance.
    """
    cell = atlas.cell("Audio Outcome", "logic_pro")
    m = cell.measured
    assert m.applicable == 2
    assert m.inferred == 2
    assert cell.declared is not None  # audio_content read capability
    assert cell.status == "FULLY_RECOVERED"


def test_cubase_processing_hidden_present(atlas):
    """Cubase Processing shows HIDDEN (INACCESSIBLE inserts + HIDDEN prov)."""
    cell = atlas.cell("Processing", "cubase")
    m = cell.measured
    assert m.observed == 8  # 8 PROCESSOR entities observed at baseline
    assert m.hidden > 0  # insert_parameter_state inaccessible
    assert cell.hidden_ratio is not None and cell.hidden_ratio > 0


def test_cubase_automation_fully_observed(atlas):
    """The re-exported Cubase bundle carries a real vocal-Volume automation lane.

    The DAWproject export is an official Cubase surface, so the single
    AUTOMATION entity lands as OBSERVED evidence and the Automation cell is
    FULLY_OBSERVED — the only real adapter that measures this domain.
    """
    cell = atlas.cell("Automation", "cubase")
    m = cell.measured
    assert m.applicable == 1
    assert m.observed == 1
    assert m.inferred == 0 and m.hidden == 0 and m.annotated == 0
    assert cell.status == "FULLY_OBSERVED"
    assert cell.direct_observability == 1.0
    # No capability maps to Automation, so the measurement stands alone.
    assert cell.declared is None


def test_modulation_not_applicable_for_all_four(atlas):
    for daw in atlas.daws:
        cell = atlas.cell("Modulation", daw)
        assert cell.measured.applicable == 0
        assert cell.declared is None
        assert cell.status == "NOT_APPLICABLE"


# The Modulation row is NOT_APPLICABLE for every real adapter (none observe
# modulation). The dedicated modulation fixture proves the row is a real
# measurement channel by flipping it to measured (ANNOTATED) somewhere.
MODULATION_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "modulation"
    / "bundles"
    / "synthetic"
)


def test_modulation_fixture_row_is_measured():
    if not (MODULATION_FIXTURE / "canonical.snapshot.json").exists():
        pytest.skip("modulation fixture not generated")
    bundle = load_bundle(MODULATION_FIXTURE)
    atlas = build_atlas([bundle])
    cell = atlas.cell("Modulation", "synthetic")
    # One ANNOTATED MODULATION entity -> measured, and specifically NOT the
    # empty-row status the real adapters get.
    assert cell.measured.applicable == 1
    assert cell.measured.annotated == 1
    assert cell.status != "NOT_APPLICABLE"
    # Reaper and cubase, side by side in the same atlas, still see nothing.
    reaper_cubase = build_atlas(
        [bundle, _bundle("reaper"), _bundle("cubase")]
    )
    for daw in ("reaper", "cubase"):
        assert reaper_cubase.cell("Modulation", daw).status == "NOT_APPLICABLE"

    # The Cubase bundle has been re-exported with its real automation lane, so
    # alongside its empty Modulation row it now measures Automation as
    # FULLY_OBSERVED (see test_cubase_automation_fully_observed for the full
    # arithmetic).
    assert reaper_cubase.cell("Automation", "cubase").status == "FULLY_OBSERVED"


def test_native_features_observed_where_extensions_nonempty(atlas):
    """Every fixture ships a non-empty extensions payload -> observed > 0."""
    for daw in atlas.daws:
        cell = atlas.cell("Native Features", daw)
        assert cell.measured.observed > 0
        assert cell.measured.applicable == cell.measured.observed


def test_declared_domain_none_when_no_capability_mapping(bundles):
    """Modulation maps to no capability domain -> declared is always None."""
    for daw in DAWS:
        assert (
            declared_domain(bundles[daw].capabilities, get_domain("Modulation"))
            is None
        )


def test_ratios_bounded_or_none(atlas):
    for domain_name in atlas.domains:
        for daw in atlas.daws:
            cell = atlas.cell(domain_name, daw)
            for ratio in (
                cell.direct_observability,
                cell.combined_coverage,
                cell.hidden_ratio,
            ):
                assert ratio is None or 0.0 <= ratio <= 1.0


def test_primary_buckets_partition_applicable(atlas):
    """observed+inferred+annotated+hidden+unsupported+not_present+unknown == applicable."""
    for domain_name in atlas.domains:
        for daw in atlas.daws:
            m = atlas.cell(domain_name, daw).measured
            total = (
                m.observed
                + m.inferred
                + m.annotated
                + m.hidden
                + m.unsupported
                + m.not_present
                + m.unknown
            )
            assert total == m.applicable, (domain_name, daw, total, m.applicable)


# --- unknown-state map ----------------------------------------------------


def test_unknown_state_map_cubase_has_inaccessible(bundles):
    usm = unknown_state_map(bundles["cubase"].snapshot)
    assert len(usm["INACCESSIBLE"]) > 0  # 14 inaccessible availability entries
    assert len(usm["HIDDEN"]) > 0  # 20 HIDDEN-evidence fields


def test_unknown_state_map_logic_has_unknown(bundles):
    usm = unknown_state_map(bundles["logic"].snapshot)
    assert len(usm["UNKNOWN"]) == 8  # 8 tracks with channel: UNKNOWN
    # 6 tracks with plugin_chain INACCESSIBLE (8 stems minus the 2 whose
    # chains a channel-strip note lifted) + 2 session-level markers on the
    # PROJECT entity (automation, routing) — the latter only register here once
    # the Logic mapper targets them at the dialect-namespaced project id.
    inaccessible = usm["INACCESSIBLE"]
    assert len(inaccessible) == 8
    assert ("logic:project", "automation") in inaccessible
    assert ("logic:project", "routing") in inaccessible


def test_unknown_state_map_categories_complete(bundles):
    from session_explorer.atlas import UNKNOWN_CATEGORIES

    usm = unknown_state_map(bundles["reaper"].snapshot)
    assert set(usm) == set(UNKNOWN_CATEGORIES)


# --- workbench smoke ------------------------------------------------------


def test_workbench_boots_with_atlas_tab():
    """AppTest smoke: the app boots, the 4th tab exists, atlas renders clean."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    app_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "session_explorer"
        / "workbench"
        / "app.py"
    )
    at = AppTest.from_file(str(app_path), default_timeout=60)
    at.run()
    # P6 two-mode workbench: the app boots into Guided mode; the atlas tab
    # lives in Expert mode, so flip the sidebar mode radio first.
    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, at.exception
    tab_labels = {tab.label for tab in at.tabs}
    assert "Observability atlas" in tab_labels
