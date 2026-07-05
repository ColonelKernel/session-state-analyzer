"""Ableton dialect keyword tables and classifiers.

Ported verbatim from the Ableton prototype's ``utils.py``. These tables keep
the ORIGINAL Ableton dict semantics — their own insertion ordering and the
bare ``"eq"`` substring behaviour — because
:func:`~.native_models.validate_project_dict` backfills roles/families with
them and the ported golden tests must behave identically to the source repo.

The core union tables in :mod:`session_explorer.core.roles` deliberately
differ (REAPER-first ordering, token-only ``"eq"``); do not substitute them
here.

Keyword-based classification of device families and track roles. These
classifications are heuristic metadata only — they inform recommendations and
graph annotations, but they are never presented as ground truth.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Device family classification
# ---------------------------------------------------------------------------

DEVICE_FAMILY_KEYWORDS: dict[str, list[str]] = {
    "EQ": ["eq", "equalizer", "eight", "pro-q", "channel eq"],
    "Dynamics": [
        "comp",
        "compressor",
        "glue",
        "limiter",
        "gate",
        "expander",
        "de-esser",
        "deesser",
    ],
    "Ambience": ["reverb", "delay", "echo", "room", "hall", "plate", "space"],
    "Saturation": [
        "saturator",
        "saturat",
        "distortion",
        "overdrive",
        "amp",
        "cabinet",
        "tape",
        "tube",
    ],
    "Modulation": ["chorus", "flanger", "phaser", "tremolo", "auto pan"],
    "Pitch": ["pitch", "autotune", "auto-tune", "melodyne", "harmonizer", "vocoder"],
    "Utility": ["utility", "gain", "trim", "meter", "analyzer", "tuner"],
    "Instrument": [
        "wavetable",
        "operator",
        "sampler",
        "simpler",
        "drift",
        "analog",
        "collision",
        "tension",
    ],
    "MIDI Effect": ["arpeggiator", "chord", "scale", "velocity", "note length"],
}

# Keywords indicating ambience-like processing, used by recommendation rules.
AMBIENCE_KEYWORDS = ["reverb", "delay", "echo", "room", "hall", "plate", "space"]

# Keywords indicating a limiter-like device on the master chain.
LIMITER_KEYWORDS = ["limiter", "maximizer", "brickwall"]

# Keywords indicating a de-esser-like corrective device.
DEESSER_KEYWORDS = ["de-esser", "deesser", "de esser", "sibilance"]


def classify_device_family(device_name: str | None) -> str:
    """Classify a device into a coarse family from its name.

    Returns "Unknown" when no keyword matches. This is a heuristic label,
    not a definitive taxonomy.
    """
    if not device_name:
        return "Unknown"
    name = device_name.lower()
    for family, keywords in DEVICE_FAMILY_KEYWORDS.items():
        if any(keyword in name for keyword in keywords):
            return family
    return "Unknown"


# ---------------------------------------------------------------------------
# Track role classification
# ---------------------------------------------------------------------------

TRACK_ROLE_KEYWORDS: dict[str, list[str]] = {
    "Vocal": ["vocal", "vox", "voice", "lead vox", "bgv"],
    "Drums": ["drum", "kick", "snare", "hat", "tom", "perc", "percussion", "beat"],
    "Bass": ["bass", "sub", "808"],
    "Guitar": ["guitar", "gtr"],
    "Keys": ["keys", "piano", "rhodes", "organ", "synth", "pad"],
    "FX": ["fx", "riser", "impact", "noise", "sweep"],
    "Bus": ["bus", "group", "aux", "return", "verb", "delay"],
    "Master": ["master"],
}


def classify_track_role(track_name: str | None) -> str:
    """Classify a track's likely role from its name.

    Returns "Unknown" when no keyword matches. Heuristic metadata only.
    """
    if not track_name:
        return "Unknown"
    name = track_name.lower()
    for role, keywords in TRACK_ROLE_KEYWORDS.items():
        if any(keyword in name for keyword in keywords):
            return role
    return "Unknown"
