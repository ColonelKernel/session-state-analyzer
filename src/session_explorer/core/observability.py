"""The declarative observation model, generalized across dialects.

The latent object of interest is the DAW session state S — track roles,
plug-in chains, parameter values, automation, sends, buses, groupings. What
the explorer receives is a set of evidence artifacts E, and each artifact type
has an observation function O(dialect, artifact_type) describing which parts
of S it **reveals** (directly observable), **constrains** (supports inference
with stated confidence), **asserts** (user-provided claims, trusted as
annotations rather than observations), and **hides** (not recoverable from
this artifact).

Originally the heart of the Logic evidence prototype; here every dialect gets
a matrix, so partial observability is a product-wide fact rather than a
Logic-only one: a parsed ``.rpp`` still hides plug-in-internal parameter
state, an Ableton extension export still hides automation, and the UI/rules
treat those gaps explicitly for all DAWs.

The hidden-state marker catalogue and per-track hidden-field lists are
*derived* from these tables rather than hard-coded, so the table is the single
thing to edit when a new evidence source moves the observability boundary.
"""

from __future__ import annotations

OBSERVATION_MODEL_VERSION = "1.0.0"

# The session-state fields this product reasons about. A fuller treatment
# would enumerate parameter-level state; field granularity is enough to make
# the observability boundary explicit.
SESSION_STATE_FIELDS = [
    "track_name",
    "role",
    "audio_content",
    "plugin_chain",
    "plugin_parameters",
    "automation",
    "sends",
    "bus_routing",
    "track_stack",
    "mixer_state",
]

# O(dialect, artifact_type): what each evidence artifact reveals / constrains /
# asserts / hides. The Logic matrix is the original from the evidence
# prototype (verbatim semantics); the other dialects' matrices are grounded in
# what their parsers/exporters demonstrably cover.
OBSERVATION_MODEL: dict[str, dict[str, dict[str, list[str]]]] = {
    "logic": {
        "exported_audio": {
            "reveals": ["audio_content"],
            "constrains": ["track_name", "role"],
            "hides": [
                "plugin_chain",
                "automation",
                "sends",
                "bus_routing",
                "track_stack",
            ],
        },
        "midi_export": {
            "reveals": ["track_name"],
            "constrains": ["role"],
            "hides": [
                "plugin_chain",
                "automation",
                "sends",
                "bus_routing",
                "track_stack",
            ],
        },
        "musicxml_export": {
            "reveals": ["track_name"],
            "constrains": ["role"],
            "hides": [
                "plugin_chain",
                "automation",
                "sends",
                "bus_routing",
                "track_stack",
            ],
        },
        "channel_strip_note": {
            # User assertions: treated as annotations, not observations.
            "asserts": ["role", "plugin_chain", "sends", "bus_routing"],
            "hides": ["automation", "track_stack"],
        },
        "session_manifest": {
            "asserts": ["role", "track_name"],
            "hides": [
                "plugin_chain",
                "automation",
                "sends",
                "bus_routing",
                "track_stack",
            ],
        },
        "reference_track": {
            "reveals": ["audio_content"],
            "constrains": [],
            "hides": [],
        },
    },
    "reaper": {
        # A parsed .rpp reveals structure but not plug-in-private state: the
        # parser deliberately does not decode plug-in parameter blobs,
        # envelopes, take FX, or item fades.
        "rpp_file": {
            "reveals": [
                "track_name",
                "plugin_chain",
                "sends",
                "bus_routing",
                "mixer_state",
                "audio_content",
            ],
            "constrains": ["role"],
            "hides": ["plugin_parameters", "automation", "track_stack"],
        },
        "exported_audio": {
            "reveals": ["audio_content"],
            "constrains": ["track_name", "role"],
            "hides": ["plugin_chain", "automation", "sends", "bus_routing"],
        },
    },
    "ableton": {
        # Extension API 1.0.0 omissions are recorded as hides: no automation
        # state, no dB mixer values, no track colors, no device on/off.
        "extension_json": {
            "reveals": [
                "track_name",
                "plugin_chain",
                "sends",
                "bus_routing",
                "track_stack",
                "audio_content",
            ],
            "constrains": ["role"],
            "hides": ["plugin_parameters", "automation", "mixer_state"],
        },
        # A hand-authored or demo session JSON asserts whatever it contains.
        "session_json": {
            "reveals": [
                "track_name",
                "plugin_chain",
                "sends",
                "bus_routing",
                "mixer_state",
            ],
            "constrains": ["role"],
            "hides": ["plugin_parameters", "automation"],
        },
        # The .als surface inspector counts tags; it observes almost nothing.
        "als_surface": {
            "reveals": [],
            "constrains": ["track_name", "plugin_chain"],
            "hides": [
                "role",
                "audio_content",
                "plugin_parameters",
                "automation",
                "sends",
                "bus_routing",
                "track_stack",
                "mixer_state",
            ],
        },
        "exported_audio": {
            "reveals": ["audio_content"],
            "constrains": ["track_name", "role"],
            "hides": ["plugin_chain", "automation", "sends", "bus_routing"],
        },
    },
    "cubase": {
        "session_json": {
            "reveals": [
                "track_name",
                "plugin_chain",
                "sends",
                "bus_routing",
                "mixer_state",
            ],
            "constrains": ["role"],
            "hides": ["plugin_parameters", "automation"],
        },
        "track_archive_surface": {
            "reveals": [],
            "constrains": ["track_name", "plugin_chain"],
            "hides": [
                "role",
                "audio_content",
                "plugin_parameters",
                "automation",
                "sends",
                "bus_routing",
                "track_stack",
                "mixer_state",
            ],
        },
        "exported_audio": {
            "reveals": ["audio_content"],
            "constrains": ["track_name", "role"],
            "hides": ["plugin_chain", "automation", "sends", "bus_routing"],
        },
    },
}

# Which channel-strip-note content lifts which hidden field from a track
# (Logic evidence pathway; annotation-capable dialects share the mapping).
NOTE_FIELD_ASSERTIONS = {
    "plugins": "plugin_chain",
    "sends": "sends",
    "bus": "bus_routing",
}

# Evidence sources that could, in principle, fill hidden-state gaps.
POSSIBLE_SOURCES = [
    "user channel-strip notes",
    "screenshots",
    "manual export documentation",
    "future DAW integration",
    "partner-provided session metadata",
]


def artifact_types(dialect: str) -> list[str]:
    return list(OBSERVATION_MODEL.get(dialect, {}).keys())


def observation_for(dialect: str, artifact_type: str) -> dict[str, list[str]]:
    """O(dialect, artifact_type); empty mapping when unknown."""
    return OBSERVATION_MODEL.get(dialect, {}).get(artifact_type, {})


def hidden_fields(dialect: str, artifact_type: str) -> list[str]:
    return list(observation_for(dialect, artifact_type).get("hides", []))


def annotated_fields_from_note(note) -> list[str]:
    """Which state fields a channel-strip note asserts, given its content."""
    fields = []
    for attr, field in NOTE_FIELD_ASSERTIONS.items():
        if getattr(note, attr, None):
            fields.append(field)
    return fields


def hidden_fields_for_track(
    annotated_fields: list[str],
    dialect: str = "logic",
    artifact_type: str = "exported_audio",
) -> list[str]:
    """Track-level hidden fields, minus those the user has annotated."""
    return [f for f in hidden_fields(dialect, artifact_type) if f not in annotated_fields]
