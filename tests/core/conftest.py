"""Shared canonical-session factories for core tests."""

import pytest

from session_explorer.core.models import (
    CanonicalSession,
    Clip,
    Processor,
    ProcessorParameter,
    Route,
    Scene,
    Track,
)


def make_processor(pid, track_id, name, family=None, index=0, parameters=None):
    return Processor(
        id=pid,
        track_id=track_id,
        index=index,
        name=name,
        family=family,
        enabled=True,
        parameters=parameters or [],
    )


def build_demo_session(dialect="test", tempo=120.0) -> CanonicalSession:
    """A small mixed session: vocal + drums + return + master, one route."""
    vocal = Track(
        id=f"{dialect}:track-1",
        index=0,
        name="Lead Vox",
        kind="audio",
        role="Vocal",
        volume_db=-6.0,
        processors=[
            make_processor(f"{dialect}:fx-1", f"{dialect}:track-1", "Channel EQ", "EQ"),
            make_processor(
                f"{dialect}:fx-2",
                f"{dialect}:track-1",
                "Compressor",
                "Dynamics",
                index=1,
                parameters=[
                    ProcessorParameter(
                        id=f"{dialect}:param-1",
                        processor_id=f"{dialect}:fx-2",
                        name="Threshold",
                        value=-18.0,
                        unit="dB",
                    )
                ],
            ),
        ],
        clips=[
            Clip(
                id=f"{dialect}:clip-1",
                track_id=f"{dialect}:track-1",
                name="Vox Verse",
                clip_type="audio",
                audio_file="audio/vox.wav",
                scene_id=f"{dialect}:scene-1",
            )
        ],
    )
    drums = Track(
        id=f"{dialect}:track-2",
        index=1,
        name="Drums",
        kind="audio",
        role="Drums",
        volume_db=-4.0,
        processors=[
            make_processor(f"{dialect}:fx-3", f"{dialect}:track-2", "Room Reverb", "Ambience")
        ],
        clips=[
            Clip(
                id=f"{dialect}:clip-2",
                track_id=f"{dialect}:track-2",
                name="Drum Loop",
                clip_type="midi",
                midi_note_count=64,
            )
        ],
    )
    verb_return = Track(
        id=f"{dialect}:return-1",
        index=0,
        name="Reverb Return",
        kind="return",
        role="Bus",
        processors=[
            make_processor(f"{dialect}:fx-4", f"{dialect}:return-1", "Hall Reverb", "Ambience")
        ],
    )
    master = Track(
        id=f"{dialect}:master",
        index=0,
        name="Master",
        kind="master",
        role="Master",
        processors=[
            make_processor(f"{dialect}:fx-5", f"{dialect}:master", "Limiter", "Dynamics")
        ],
    )
    return CanonicalSession(
        dialect=dialect,
        name="Demo",
        tempo=tempo,
        time_signature="4/4",
        scenes=[Scene(id=f"{dialect}:scene-1", index=0, name="Verse")],
        tracks=[vocal, drums, verb_return, master],
        routes=[
            Route(
                id=f"{dialect}:route-1",
                source_track_id=f"{dialect}:track-1",
                target_track_id=f"{dialect}:return-1",
                route_type="send",
                volume_db=-9.0,
            )
        ],
    )


@pytest.fixture
def demo_session() -> CanonicalSession:
    return build_demo_session()
