"""Cross-dialect structural fingerprint tests (canonicalized from the REAPER suite)."""

from session_explorer.core.fingerprint import (
    compare_fingerprints,
    compute_session_fingerprint,
)
from session_explorer.core.models import AudioDescriptorSet, CanonicalSession

from .conftest import build_demo_session


def test_fingerprint_counts(demo_session):
    fp = compute_session_fingerprint(demo_session)
    assert fp["n_tracks"] == 4  # all kinds counted, master included
    assert fp["n_vocal_tracks"] == 1
    assert fp["n_drum_tracks"] == 1
    assert fp["n_bus_tracks"] == 1
    assert fp["n_fx"] == 5
    assert fp["n_ambience_fx"] == 2
    assert fp["n_dynamics_fx"] == 2
    assert fp["n_eq_fx"] == 1
    assert fp["n_routes"] == 1
    assert fp["avg_fx_per_track"] == round(5 / 4, 3)
    assert fp["dialect"] == "test"
    assert "descriptor_summary" not in fp


def test_fingerprint_descriptor_summary(demo_session):
    demo_session.descriptors = [
        AudioDescriptorSet(available=True, rms_mean=0.2, peak_amplitude=0.9),
        AudioDescriptorSet(available=False, rms_mean=0.9),  # excluded
    ]
    fp = compute_session_fingerprint(demo_session)
    assert fp["descriptor_summary"]["n_audio_files"] == 1
    assert fp["descriptor_summary"]["mean_rms"] == 0.2


def test_identical_sessions_similarity_is_one(demo_session):
    fp1 = compute_session_fingerprint(demo_session)
    fp2 = compute_session_fingerprint(build_demo_session())
    assert compare_fingerprints(fp1, fp2) == 1.0


def test_cross_dialect_comparison_ignores_dialect(demo_session):
    other = build_demo_session(dialect="other")
    similarity = compare_fingerprints(
        compute_session_fingerprint(demo_session),
        compute_session_fingerprint(other),
    )
    assert similarity == 1.0  # same structure, different dialect


def test_empty_session_similarity_is_zero(demo_session):
    empty = CanonicalSession(dialect="test", name="Empty")
    assert (
        compare_fingerprints(
            compute_session_fingerprint(demo_session),
            compute_session_fingerprint(empty),
        )
        == 0.0
    )


def test_similarity_bounded_and_symmetric(demo_session):
    other = build_demo_session()
    other.tracks = other.tracks[:2]
    fp1 = compute_session_fingerprint(demo_session)
    fp2 = compute_session_fingerprint(other)
    s12 = compare_fingerprints(fp1, fp2)
    s21 = compare_fingerprints(fp2, fp1)
    assert 0.0 <= s12 <= 1.0
    assert s12 == s21
