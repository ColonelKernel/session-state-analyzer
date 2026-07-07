"""P9 gate: the controlled state→audio intervention experiment.

Exercises the whole chain over the frozen ``fixtures/experiments/effect_send``
A/B: the state delta finds exactly the one added send (nothing removed), the
signal-flow explanation reads back the real path in plain English, the acoustic
delta measures the level change between the two renders, and the packaged
experiment is deterministic. A headless workbench smoke boots the new
"State to audio" tab in both modes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from session_explorer.interventions import (
    build_effect_send_experiment,
    build_parameter_experiment,
    load_intervention,
    load_render_descriptors,
)
from session_explorer.interventions.compare import (
    acoustic_delta,
    explain_signal_flow,
    snapshot_delta,
)
from session_explorer.loaders.bundle import load_bundle

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "fixtures" / "experiments" / "effect_send"
PARAM_FIXTURE = REPO_ROOT / "fixtures" / "experiments" / "parameter_change"


@pytest.fixture(scope="module")
def bundles():
    return load_bundle(FIXTURE / "before"), load_bundle(FIXTURE / "after")


@pytest.fixture(scope="module")
def param_bundles():
    return load_bundle(PARAM_FIXTURE / "before"), load_bundle(PARAM_FIXTURE / "after")


# ---------------------------------------------------------------------------
# State delta
# ---------------------------------------------------------------------------


def test_snapshot_delta_is_one_added_send_nothing_removed(bundles):
    before, after = bundles
    delta = snapshot_delta(before.snapshot, after.snapshot)

    # Exactly one added CHANNEL_SENDS_TO: the vox channel → the FX-1 channel.
    sends = [r for r in delta.added_relationships if r.type == "CHANNEL_SENDS_TO"]
    assert len(sends) == 1
    assert delta.added_sends == sends
    send = sends[0]
    assert "Lead Vox" in send.label
    assert "FX 1" in send.label

    # The underlying edge is vox:channel → fx1, as verified in the export.
    edge = next(
        r
        for r in after.snapshot.relationships
        if r.rel_type == "CHANNEL_SENDS_TO"
    )
    assert edge.source == "cubase:track-tr-ch-vox:channel"
    assert edge.target == "cubase:track-tr-ch-fx1"

    # Nothing was removed — this is a pure addition.
    assert delta.removed_entities == []
    assert delta.removed_relationships == []

    # The send points at a newly-added FX-1 return + its REVerence processor.
    added_labels = {r.label for r in delta.added_entities}
    assert "FX 1 - Plate" in added_labels
    assert "REVerence" in added_labels
    # before/after entity id sets: fx1 + reverence are the only structural adds.
    before_ids = {e.id for e in before.snapshot.entities}
    after_ids = {e.id for e in after.snapshot.entities}
    assert after_ids - before_ids == {
        "cubase:track-tr-ch-fx1",
        "cubase:device-dev-ch-fx1-0",
    }
    assert before_ids - after_ids == set()


# ---------------------------------------------------------------------------
# Signal-flow explanation
# ---------------------------------------------------------------------------


def test_explain_signal_flow_is_readable_and_traces_the_path(bundles):
    _before, after = bundles
    delta = snapshot_delta(_before.snapshot, after.snapshot)
    flow = explain_signal_flow(after.snapshot, delta)

    summary = flow.summary
    assert "vocal" in summary  # derived from the track's vocal_source role
    assert "FX 1" in summary or "Plate" in summary
    assert "REVerence" in summary
    assert "main output" in summary  # derived from the master's main_output role

    # The path is the left-to-right chain source → target → processor → output.
    assert len(flow.path) >= 3
    assert flow.path[0] == "Lead Vox"
    assert "REVerence" in flow.path
    assert flow.path[-1] == "Stereo Out"


# ---------------------------------------------------------------------------
# Acoustic delta
# ---------------------------------------------------------------------------


def test_acoustic_delta_is_louder_by_about_6db():
    renders = load_render_descriptors()
    before = renders["render:routing_a"].descriptor
    after = renders["render:routing_b"].descriptor
    ad = acoustic_delta(before, after)

    metrics = {m.name: m for m in ad.metrics}

    rms = metrics["rms_db"]
    assert rms.delta is not None and 4 < rms.delta < 8  # ~+5.6 dB
    assert rms.direction == "louder"

    peak = metrics["peak_db"]
    assert peak.delta is not None and peak.delta > 0
    assert peak.direction == "louder"

    # LUFS present in the frozen descriptors (pyloudnorm was available).
    assert "lufs" in metrics
    assert metrics["lufs"].delta is not None and metrics["lufs"].delta > 0
    assert "louder" in ad.summary


def test_acoustic_delta_guards_missing_descriptors():
    ad = acoustic_delta(None, None)
    assert not ad.available
    assert ad.metrics == []


# ---------------------------------------------------------------------------
# Packaged experiment
# ---------------------------------------------------------------------------


def test_build_effect_send_experiment_is_complete_and_deterministic():
    comparison = build_effect_send_experiment()

    # Complete: all three beats populated.
    assert comparison.state_delta.added_sends
    assert comparison.signal_flow.summary
    assert comparison.signal_flow.path
    assert comparison.acoustic_delta.metrics

    # The intervention record round-tripped from intervention.json.
    iv = comparison.intervention
    assert iv.description == load_intervention().description
    assert "cubase" in iv.native_implementations
    assert iv.before.render_id == "render:routing_a"
    assert iv.after.render_id == "render:routing_b"

    # Deterministic: two calls produce equal comparisons.
    again = build_effect_send_experiment()
    assert comparison.model_dump() == again.model_dump()


# ---------------------------------------------------------------------------
# Parameter-change generalization — the delay-feedback A/B
# ---------------------------------------------------------------------------


def test_parameter_snapshot_delta_is_one_feedback_change_nothing_else(param_bundles):
    before, after = param_bundles
    delta = snapshot_delta(before.snapshot, after.snapshot)

    # Exactly one ParameterChange: the delay Feedback, 0.2 → 0.7, role FEEDBACK.
    assert len(delta.parameter_changes) == 1
    pc = delta.parameter_changes[0]
    assert pc.id == "reaper:fx-delay:feedback"
    assert pc.name == "Feedback"
    assert pc.role == "FEEDBACK"
    assert pc.before_value == pytest.approx(0.2)
    assert pc.after_value == pytest.approx(0.7)
    # The owning processor and its channel were resolved from the edges.
    assert pc.processor_id == "reaper:fx-delay"
    assert pc.channel_id == "reaper:track-vox:channel"

    # A pure in-place value change: nothing structural added or removed, and it
    # is not a routing change.
    assert delta.added_entities == []
    assert delta.removed_entities == []
    assert delta.added_relationships == []
    assert delta.removed_relationships == []
    assert delta.added_sends == []
    # The generic ``changed`` view flags the same one PARAMETER entity.
    assert [(r.type, r.label) for r in delta.changed] == [("PARAMETER", "Feedback")]


def test_parameter_explain_signal_flow_names_the_delay_and_values(param_bundles):
    before, after = param_bundles
    delta = snapshot_delta(before.snapshot, after.snapshot)
    flow = explain_signal_flow(after.snapshot, delta)

    # The generalized bail no longer returns empty: it explains the parameter.
    summary = flow.summary
    assert summary
    assert "Delay" in summary          # names the owning processor
    assert "FEEDBACK" in summary        # the derived role
    assert "vocal" in summary           # the channel's source noun
    assert "0.20" in summary and "0.70" in summary  # both readings

    # The path is [channel, processor] — the two nodes the change touches.
    assert flow.path == ["Lead Vox", "Delay"]


def test_parameter_acoustic_delta_measures_a_real_change():
    renders = load_render_descriptors(PARAM_FIXTURE)
    before = renders["render:routing_a"].descriptor
    after = renders["render:routing_b"].descriptor
    ad = acoustic_delta(before, after)
    assert ad.available

    metrics = {m.name: m for m in ad.metrics}

    # Higher feedback sustains more energy: the render is genuinely louder.
    rms = metrics["rms_db"]
    assert rms.delta is not None and rms.delta > 0.5
    assert rms.direction == "louder"

    # LUFS present (pyloudnorm available) and moved measurably in the same
    # direction — the two renders are not acoustically identical.
    assert "lufs" in metrics
    assert metrics["lufs"].delta is not None and metrics["lufs"].delta > 0
    assert "louder" in ad.summary


def test_build_parameter_experiment_is_complete_and_deterministic():
    comparison = build_parameter_experiment()

    # Complete: all three beats populated, driven by the parameter change.
    assert comparison.state_delta.parameter_changes
    assert not comparison.state_delta.added_sends
    assert comparison.signal_flow.summary
    assert comparison.signal_flow.path
    assert comparison.acoustic_delta.metrics

    # The intervention record round-tripped from intervention.json.
    iv = comparison.intervention
    assert iv.semantic_role == "FEEDBACK"
    assert "reaper" in iv.native_implementations
    assert iv.before.render_id == "render:routing_a"
    assert iv.after.render_id == "render:routing_b"

    # Deterministic: two calls produce equal comparisons.
    again = build_parameter_experiment()
    assert comparison.model_dump() == again.model_dump()


# ---------------------------------------------------------------------------
# Workbench smoke — the new tab in both modes
# ---------------------------------------------------------------------------

STREAMLIT_AVAILABLE = importlib.util.find_spec("streamlit") is not None
APP_PATH = REPO_ROOT / "src" / "session_explorer" / "workbench" / "app.py"

workbench = pytest.mark.skipif(
    not STREAMLIT_AVAILABLE, reason="streamlit not installed (ui extra)"
)


def _apptest():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP_PATH), default_timeout=120)


@workbench
def test_guided_intervention_tab_renders():
    from session_explorer.workbench import copy as wcopy

    at = _apptest()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    # The guided intervention tab is present and its plain-language story ran.
    assert wcopy.COPY["tab_intervention"] in [tab.label for tab in at.tabs]
    body = " ".join(str(m.value) for m in at.markdown)
    assert "REVerence" in body
    assert "Lead Vox" in body


@workbench
def test_expert_state_to_audio_tab_renders():
    at = _apptest()
    at.run()
    at.sidebar.radio[0].set_value("Expert").run()
    assert not at.exception, [e.value for e in at.exception]
    assert "State to audio" in {tab.label for tab in at.tabs}
    body = " ".join(str(m.value) for m in at.markdown)
    # The signal-flow explanation reached the expert panel.
    assert "REVerence" in body
    assert "main output" in body
