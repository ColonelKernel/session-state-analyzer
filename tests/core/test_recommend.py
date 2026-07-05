"""Rule engine + core cross-DAW rule pack tests."""

from session_explorer.core.driver import Rule
from session_explorer.core.ids import reset_id_counters
from session_explorer.core.models import Recommendation, Route, Track
from session_explorer.core.recommend import (
    CORE_RULES,
    DENSE_CHAIN_THRESHOLD,
    rule_dense_chain,
    rule_level_imbalance,
    rule_master_limiter_context,
    rule_shared_ambience,
    rule_unused_returns,
    rule_vocal_corrective_chain,
    run_rules,
)

from .conftest import build_demo_session, make_processor


def setup_function(_fn):
    reset_id_counters()


def test_run_rules_skips_hidden_requirements_with_info_note(demo_session):
    demo_session.dialect = "logic"
    demo_session.metadata["source_artifact"] = "exported_audio"
    fired = []

    def never_runs(session):
        fired.append(True)
        return []

    recs = run_rules(
        demo_session,
        [Rule(rule_id="needs.chain", fn=never_runs, requires=["plugin_chain"])],
    )
    assert not fired
    assert len(recs) == 1
    assert recs[0].severity == "info"
    assert "plugin_chain" in recs[0].explanation
    assert "needs.chain" in recs[0].title


def test_run_rules_executes_when_field_observed(demo_session):
    demo_session.dialect = "reaper"
    demo_session.metadata["source_artifact"] = "rpp_file"
    recs = run_rules(
        demo_session,
        [
            Rule(
                rule_id="x",
                fn=lambda s: [Recommendation(id="r-1", title="T", severity="warning")],
                requires=["plugin_chain"],
            )
        ],
    )
    assert [r.id for r in recs] == ["r-1"]


def test_run_rules_without_artifact_runs_everything(demo_session):
    recs = run_rules(
        demo_session,
        [
            Rule(
                rule_id="x",
                fn=lambda s: [Recommendation(id="r-1", title="T")],
                requires=["automation"],  # would be hidden if artifact known
            )
        ],
    )
    assert [r.id for r in recs] == ["r-1"]


def test_run_rules_sorts_by_severity_then_confidence(demo_session):
    def fn(_):
        return [
            Recommendation(id="a", title="a", severity="info", confidence=0.9),
            Recommendation(id="b", title="b", severity="warning", confidence=0.2),
            Recommendation(id="c", title="c", severity="suggestion", confidence=0.9),
            Recommendation(id="d", title="d", severity="suggestion", confidence=0.3),
        ]

    recs = run_rules(demo_session, [Rule(rule_id="x", fn=fn)])
    assert [r.id for r in recs] == ["b", "c", "d", "a"]


def test_shared_ambience_fires_on_unrouted_carriers(demo_session):
    # Demo: Drums carries ambience but routes exist only from Lead Vox.
    # Add a second unrouted ambience carrier.
    demo_session.tracks.insert(
        2,
        Track(
            id="test:track-3",
            index=2,
            name="Pad",
            kind="audio",
            role="Keys",
            processors=[
                make_processor("test:fx-8", "test:track-3", "Plate Reverb", "Ambience")
            ],
        ),
    )
    recs = rule_shared_ambience(demo_session)
    assert len(recs) == 1
    assert set(recs[0].related_node_ids) == {"test:track-2", "test:track-3"}


def test_shared_ambience_quiet_when_routed(demo_session):
    demo_session.routes.append(
        Route(
            id="test:route-2",
            source_track_id="test:track-2",
            target_track_id="test:return-1",
        )
    )
    assert rule_shared_ambience(demo_session) == []


def test_unused_returns(demo_session):
    assert rule_unused_returns(demo_session) == []  # return receives a route
    demo_session.routes = []
    recs = rule_unused_returns(demo_session)
    assert len(recs) == 1
    assert recs[0].related_node_ids == ["test:return-1"]


def test_vocal_corrective_chain(demo_session):
    recs = rule_vocal_corrective_chain(demo_session)
    assert len(recs) == 1
    assert recs[0].related_node_ids == ["test:track-1"]
    # Adding a de-esser silences the rule.
    demo_session.tracks[0].processors.append(
        make_processor("test:fx-9", "test:track-1", "DeEsser 2", "Dynamics")
    )
    assert rule_vocal_corrective_chain(demo_session) == []


def test_vocal_rule_ignores_empty_chains(demo_session):
    demo_session.tracks[0].processors = []
    assert rule_vocal_corrective_chain(demo_session) == []


def test_dense_chain(demo_session):
    assert rule_dense_chain(demo_session) == []
    track = demo_session.tracks[1]
    for i in range(DENSE_CHAIN_THRESHOLD + 1):
        track.processors.append(
            make_processor(f"test:fx-d{i}", track.id, f"FX {i}", "Utility", index=i + 1)
        )
    recs = rule_dense_chain(demo_session)
    assert len(recs) == 1
    assert recs[0].related_node_ids == [track.id]
    # Record-input chains don't count toward the main-chain density.
    track.processors = track.processors[:DENSE_CHAIN_THRESHOLD]
    for i in range(3):
        track.processors.append(
            make_processor(f"test:fx-r{i}", track.id, f"Mon {i}", "Utility")
        )
        track.processors[-1].chain = "rec"
    assert rule_dense_chain(demo_session) == []


def test_level_imbalance(demo_session):
    assert rule_level_imbalance(demo_session) == []  # -6 vs -4 dB
    demo_session.tracks[1].volume_db = -20.0
    recs = rule_level_imbalance(demo_session)
    assert len(recs) == 1
    assert set(recs[0].related_node_ids) == {"test:track-1", "test:track-2"}


def test_master_limiter_context(demo_session):
    recs = rule_master_limiter_context(demo_session)
    assert len(recs) == 1  # Limiter on master, no loudness descriptors
    from session_explorer.core.models import AudioDescriptorSet

    demo_session.descriptors = [
        AudioDescriptorSet(available=True, integrated_loudness_lufs=-14.0)
    ]
    assert rule_master_limiter_context(demo_session) == []


def test_core_rules_run_end_to_end(demo_session):
    demo_session.dialect = "reaper"
    demo_session.metadata["source_artifact"] = "rpp_file"
    recs = run_rules(demo_session, CORE_RULES)
    titles = [r.title for r in recs]
    # mixer_state is revealed by rpp_file: level rule ran (quietly), no skip note.
    assert not any("not evaluable" in t for t in titles)
    assert any("corrective chain" in t for t in titles)
    assert all(r.caveat for r in recs)


def test_core_rules_respect_logic_observability(demo_session):
    demo_session.dialect = "logic"
    demo_session.metadata["source_artifact"] = "exported_audio"
    recs = run_rules(demo_session, CORE_RULES)
    # Every core rule must be skipped: stems reveal audio content only.
    skip_notes = [r for r in recs if "not evaluable" in r.title]
    assert len(skip_notes) == len(CORE_RULES)
    assert all(r.severity == "info" for r in skip_notes)
