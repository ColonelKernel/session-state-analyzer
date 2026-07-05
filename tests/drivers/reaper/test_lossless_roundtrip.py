"""The Phase 2 lossless gate plus golden structural facts for the demo project.

``to_native(to_canonical(p)).model_dump() == p.model_dump()`` is the driver's
losslessness contract; the golden-snapshot assertions pin the canonical
projection of ``data/examples/reaper/example_project.rpp`` so schema drift is
caught structurally. Fingerprint assertions cover the prototype's
``test_fingerprint`` intent through the mapper.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from session_explorer.core.fingerprint import (
    compare_fingerprints,
    compute_session_fingerprint,
)
from session_explorer.core.models import NativePayload
from session_explorer.drivers.reaper.driver import ReaperDriver
from session_explorer.drivers.reaper.mapper import to_canonical, to_native
from session_explorer.drivers.reaper.rpp_parser import parse_rpp

EXAMPLE_RPP = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "examples"
    / "reaper"
    / "example_project.rpp"
)


@pytest.fixture(scope="module")
def example_project():
    text = EXAMPLE_RPP.read_text(encoding="utf-8")
    return parse_rpp(text, source_file=str(EXAMPLE_RPP))


def test_example_project_exists():
    assert EXAMPLE_RPP.exists()


def test_lossless_roundtrip(example_project):
    session = to_canonical(example_project)
    assert to_native(session).model_dump() == example_project.model_dump()


def test_to_native_requires_native_payload(example_project):
    session = to_canonical(example_project)
    session.native = None
    with pytest.raises(ValueError):
        to_native(session)


def test_to_native_rejects_foreign_payload(example_project):
    session = to_canonical(example_project)
    session.native = NativePayload(dialect="ableton", model_name="LiveSet", model={})
    with pytest.raises(ValueError):
        to_native(session)


def test_golden_structural_facts(example_project):
    session = to_canonical(example_project)

    assert session.dialect == "reaper"
    assert session.name == "example_project"
    assert session.tempo == 120.0
    assert session.time_signature == "4/4"
    assert session.sample_rate == 44100
    assert session.extras["header_platform"] == "7.0/win64"
    assert session.extras["sample_rate_use"] is False
    assert session.metadata["source_artifact"] == "rpp_file"

    assert len(session.tracks) == 9
    assert session.tracks[0].name == "Lead Vox"
    assert session.tracks[0].id == "reaper:track-0"
    assert all(t.id.startswith("reaper:") for t in session.tracks)

    processors = session.all_processors()
    assert len(processors) == 22
    assert all(p.id.startswith("reaper:") for p in processors)

    assert len(session.routes) == 4
    assert sum(1 for r in session.routes if r.route_type == "send") == 3
    assert sum(1 for r in session.routes if r.route_type == "unresolved") == 1
    assert all(r.id.startswith("reaper:") for r in session.routes)

    clips = session.all_clips()
    assert len(clips) == 7  # Synth Pad and Drum Bus carry no media items
    assert all(c.clip_type == "audio" for c in clips)
    assert clips[0].audio_file == "audio/lead_vox.wav"
    assert clips[0].position_seconds == 0.0
    assert clips[0].length_seconds == 2.0

    # Native payload is intact and native ids inside it stay un-namespaced.
    assert session.native is not None
    assert session.native.dialect == "reaper"
    assert session.native.model_name == "ProjectState"
    assert session.native.model["tracks"][0]["id"] == "track-0"

    # The heuristic role carries inferred provenance; the track itself is observed.
    lead = session.tracks[0]
    assert lead.role == "Vocal"
    assert lead.provenance.observability == "observed"
    assert lead.provenance.source_artifact == "rpp_file"
    assert lead.field_provenance["role"].observability == "inferred"

    # REAPER-only mixer state is surfaced in extras without schema changes.
    assert lead.extras["volume"] == 1.0


def test_fingerprint_of_example_project(example_project):
    session = to_canonical(example_project)
    fp = compute_session_fingerprint(session)
    assert fp["dialect"] == "reaper"
    assert fp["n_tracks"] == 9
    assert fp["n_fx"] == 22
    assert fp["n_routes"] == 4
    assert fp["n_vocal_tracks"] == 2  # Lead Vox + BGV
    assert fp["n_drum_tracks"] == 3  # Kick, Snare, Perc ("Drum Bus" reads as Bus)
    assert fp["n_eq_fx"] == 8

    # Identical parses fingerprint identically (similarity 1.0).
    text = EXAMPLE_RPP.read_text(encoding="utf-8")
    fp2 = compute_session_fingerprint(
        to_canonical(parse_rpp(text, source_file=str(EXAMPLE_RPP)))
    )
    assert compare_fingerprints(fp, fp2) == 1.0


def test_driver_demo_and_sniff_roundtrip():
    driver = ReaperDriver()
    assert driver.sniff("song.rpp", b"") == 0.95
    assert driver.sniff("song.txt", b"<REAPER_PROJECT 0.1") == 0.95
    assert driver.sniff("song.als", b"PK\x03\x04") == 0.0

    session = driver.demo()
    assert session.dialect == "reaper"
    assert len(session.tracks) == 9
    native = driver.to_native(session)
    assert native.model_dump() == to_native(session).model_dump()
