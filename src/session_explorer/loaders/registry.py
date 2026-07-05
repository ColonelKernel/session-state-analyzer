"""Per-DAW presentation registry — data only, never acquisition (decision D4).

Keyed on ``snapshot.source.daw``. This registry customizes how the analyzer
*presents* a snapshot (display names, the DAW's native vocabulary for
canonical concepts) and nothing else: no parsing, no loading, no capability
claims. Unknown DAWs get an honest generic presentation rather than an error —
the contract, not this table, decides what the analyzer can consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DawPresentation:
    """Display vocabulary for one DAW's snapshots.

    ``native_vocab`` maps canonical concepts to the DAW's own nouns, so UI
    panels can label a CHANNEL "FX Channel" for Cubase and "Return Track" for
    Ableton without pretending those are the same word.
    """

    daw: str
    display_name: str
    native_vocab: dict[str, str] = field(default_factory=dict)


_GENERIC_VOCAB = {
    "TRACK": "Track",
    "CHANNEL": "Channel",
    "TEMPORAL_OBJECT": "Clip",
    "PROCESSOR": "Processor",
    "MEDIA_ASSET": "Media file",
    "STRUCTURAL_CONTAINER": "Container",
    "send": "Send",
    "effect_return": "Return",
    "main_output": "Master",
    "submix": "Group",
}

_REGISTRY: dict[str, DawPresentation] = {
    "ableton": DawPresentation(
        daw="ableton",
        display_name="Ableton Live",
        native_vocab={
            **_GENERIC_VOCAB,
            "TEMPORAL_OBJECT": "Clip",
            "PROCESSOR": "Device",
            "STRUCTURAL_CONTAINER": "Scene",
            "effect_return": "Return Track",
            "main_output": "Main / Master Track",
            "submix": "Group Track",
        },
    ),
    "reaper": DawPresentation(
        daw="reaper",
        display_name="REAPER",
        native_vocab={
            **_GENERIC_VOCAB,
            "TEMPORAL_OBJECT": "Media Item",
            "PROCESSOR": "FX",
            "effect_return": "Receive Track",
            "main_output": "Master Track",
            "submix": "Folder Track",
        },
    ),
    "logic": DawPresentation(
        daw="logic",
        display_name="Logic Pro",
        native_vocab={
            **_GENERIC_VOCAB,
            "TEMPORAL_OBJECT": "Region",
            "PROCESSOR": "Plug-in",
            "CHANNEL": "Channel Strip",
            "effect_return": "Aux Channel Strip",
            "main_output": "Stereo Out",
            "submix": "Track Stack / Summing Stack",
        },
    ),
    "cubase": DawPresentation(
        daw="cubase",
        display_name="Cubase",
        native_vocab={
            **_GENERIC_VOCAB,
            "TEMPORAL_OBJECT": "Event",
            "PROCESSOR": "Insert",
            "CHANNEL": "Mixer Channel",
            "effect_return": "FX Channel",
            "main_output": "Stereo Out",
            "submix": "Group Channel",
        },
    ),
}


def known_daws() -> list[str]:
    return sorted(_REGISTRY)


def get_presentation(daw: str) -> DawPresentation:
    """Presentation info for ``daw``; a generic fallback for unknown DAWs."""
    found = _REGISTRY.get(daw)
    if found is not None:
        return found
    return DawPresentation(
        daw=daw,
        display_name=daw.title() if daw else "Unknown DAW",
        native_vocab=dict(_GENERIC_VOCAB),
    )
