"""The concept registry: canonical concepts and how each DAW implements them.

This is the P4 semantic layer between the wire format and cross-DAW analysis.
A *concept* is a production-strategy noun (``effect_return``, ``audio_source``)
that different DAWs realize with different native mechanisms. Each
:class:`ConceptEntry` records:

- ``implementations`` — per DAW, the native noun (``return_track``,
  ``fx_channel``, ``aux_channel_strip``, ``media_track``) plus the
  ``wire_types`` that adapter's bundles actually put in
  ``Entity.native.native_type``. ``wire_types`` may be empty on purpose:
  REAPER implements an effect return as a plain media track (every REAPER
  track is ``native_type="audio"``), so no native_type maps to the concept —
  recognition there is topological, which is the alignment engine's job.
- ``equivalence`` — per DAW, how faithful that implementation is to the
  concept: EXACT / CLOSE / FUNCTIONAL / STRUCTURAL / PARTIAL / NONE / UNKNOWN.
  ``effect_return`` is FUNCTIONAL everywhere: four mechanisms, one
  signal-flow result, no pretence they are the same feature.

Format decision (documented, deliberate): **this Python module is the source
of truth**, and ``concepts.yaml`` next to it is *generated* for human readers
(``to_yaml()``). PyYAML is not a dependency of the analyzer and a hand-rolled
YAML parser is a liability, so we ship data as literals and emit YAML rather
than the reverse. ``tests/analyzer/test_alignment.py`` keeps the two in sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

EquivalenceLevel = Literal[
    "EXACT",        # the same concept, natively
    "CLOSE",        # same concept with minor semantic differences
    "FUNCTIONAL",   # different mechanism, same signal-flow/production result
    "STRUCTURAL",   # expressible only through generic structure (folders, buses)
    "PARTIAL",      # a reconstruction or subset, not the full concept
    "NONE",         # the DAW (or its capture pathway) has no such concept
    "UNKNOWN",      # not yet assessed
]

EQUIVALENCE_LEVELS: tuple[str, ...] = (
    "EXACT", "CLOSE", "FUNCTIONAL", "STRUCTURAL", "PARTIAL", "NONE", "UNKNOWN",
)

# The four adapter DAW ids, exactly as they appear in snapshot.source.daw.
KNOWN_DAWS: tuple[str, ...] = ("ableton_live", "cubase", "logic_pro", "reaper")


@dataclass(frozen=True)
class Implementation:
    """How one DAW natively realizes a concept.

    ``native_type`` is the DAW's own noun for the mechanism (display/registry
    vocabulary). ``wire_types`` are the ``Entity.native.native_type`` strings
    this DAW's adapter actually emits for entities implementing the concept —
    the machine-usable reverse-lookup key. Empty ``wire_types`` means the
    concept never has a dedicated native_type on that DAW's wire (see module
    docstring), not that the mapping was forgotten.
    """

    native_type: str
    wire_types: tuple[str, ...] = ()
    notes: Optional[str] = None


@dataclass(frozen=True)
class ConceptEntry:
    concept_id: str
    description: str
    implementations: dict[str, Implementation] = field(default_factory=dict)
    equivalence: dict[str, str] = field(default_factory=dict)  # daw -> EquivalenceLevel

    def native_noun(self, daw: str) -> Optional[str]:
        impl = self.implementations.get(daw)
        return impl.native_type if impl else None


# --------------------------------------------------------------------------
# The seed registry. Order matters: concepts_for_native() reports concepts in
# this declaration order, and the alignment engine classifies specific
# concepts (effect_return, main_output, submix, scene) before generic ones
# (audio_source, track, channel).
# --------------------------------------------------------------------------

CONCEPTS: tuple[ConceptEntry, ...] = (
    ConceptEntry(
        concept_id="effect_return",
        description=(
            "A shared effect processing destination fed by sends and summed "
            "into the main output — the 'one reverb, many sources' strategy."
        ),
        implementations={
            "ableton_live": Implementation(
                "return_track", ("return",),
                notes="Dedicated Return Track fed by per-track sends A/B/C.",
            ),
            "cubase": Implementation(
                "fx_channel", ("return",),
                notes="FX Channel track targeted by channel sends.",
            ),
            "logic_pro": Implementation(
                "aux_channel_strip", (),
                notes=(
                    "Aux channel strip fed by a bus send. Never on the wire: "
                    "the evidence adapter cannot observe channel strips, so "
                    "the mechanism arrives as annotations on inferred tracks."
                ),
            ),
            "reaper": Implementation(
                "media_track", (),
                notes=(
                    "A plain media track carrying receives (AUXRECV) and the "
                    "effect FX. No dedicated native type exists; recognition "
                    "is topological (receives sends + effect processor)."
                ),
            ),
        },
        equivalence={
            "ableton_live": "FUNCTIONAL",
            "cubase": "FUNCTIONAL",
            "logic_pro": "FUNCTIONAL",
            "reaper": "FUNCTIONAL",
        },
    ),
    ConceptEntry(
        concept_id="main_output",
        description="The session's final summing destination (master / stereo out).",
        implementations={
            "ableton_live": Implementation("master_track", ("master",)),
            "cubase": Implementation("output_channel", ("master",)),
            "logic_pro": Implementation(
                "stereo_out_channel_strip", (),
                notes="Exists in Logic, never observed by the evidence adapter.",
            ),
            "reaper": Implementation(
                "master_track", (),
                notes=(
                    "The .rpp track list omits the master; only the per-track "
                    "MAINSEND flag witnesses routing to it."
                ),
            ),
        },
        equivalence={
            "ableton_live": "CLOSE",
            "cubase": "CLOSE",
            "logic_pro": "UNKNOWN",
            "reaper": "STRUCTURAL",
        },
    ),
    ConceptEntry(
        concept_id="submix",
        description="An intermediate summing stage for a group of sources.",
        implementations={
            "ableton_live": Implementation("group_track", ("group",)),
            "cubase": Implementation("group_channel", ("group",)),
            "logic_pro": Implementation(
                "track_stack", (),
                notes="Summing stacks are HIDDEN to the evidence adapter.",
            ),
            "reaper": Implementation(
                "media_track", (),
                notes="Folder parents / receive buses; generic structure only.",
            ),
        },
        equivalence={
            "ableton_live": "CLOSE",
            "cubase": "CLOSE",
            "logic_pro": "NONE",
            "reaper": "STRUCTURAL",
        },
    ),
    ConceptEntry(
        concept_id="scene",
        description="A horizontal launchable row of clips (session-view scene).",
        implementations={
            "ableton_live": Implementation("scene", ("scene",)),
        },
        equivalence={
            "ableton_live": "EXACT",
            "cubase": "NONE",
            "logic_pro": "NONE",
            "reaper": "NONE",
        },
    ),
    ConceptEntry(
        concept_id="audio_source",
        description="A lane that generates or carries source audio material.",
        implementations={
            "ableton_live": Implementation("audio_track", ("audio",)),
            "cubase": Implementation("audio_track", ("audio",)),
            "logic_pro": Implementation(
                "inferred_track", ("inferred",),
                notes="A reconstruction from an exported stem, not a parsed track.",
            ),
            "reaper": Implementation("media_track", ("audio",)),
        },
        equivalence={
            "ableton_live": "CLOSE",
            "cubase": "CLOSE",
            "logic_pro": "PARTIAL",
            "reaper": "CLOSE",
        },
    ),
    ConceptEntry(
        concept_id="track",
        description="The organizational lane: owns content and arrangement.",
        implementations={
            "ableton_live": Implementation("track", ("audio", "midi", "group")),
            "cubase": Implementation("track", ("audio", "midi", "group")),
            "logic_pro": Implementation("inferred_track", ("inferred",)),
            "reaper": Implementation("media_track", ("audio",)),
        },
        equivalence={
            "ableton_live": "CLOSE",
            "cubase": "CLOSE",
            "logic_pro": "PARTIAL",
            "reaper": "CLOSE",
        },
    ),
    ConceptEntry(
        concept_id="channel",
        description="The signal path: owns mixer state and routing.",
        implementations={
            "ableton_live": Implementation(
                "mixer_section", (),
                notes="Implicit mixer strip of every track; adapter splits it out.",
            ),
            "cubase": Implementation(
                "channel", (),
                notes="DAWproject models Channel explicitly inside Track.",
            ),
            "logic_pro": Implementation(
                "channel_strip", (),
                notes="Never observed: TRACKs carry availability channel=UNKNOWN.",
            ),
            "reaper": Implementation(
                "media_track", (),
                notes="Fused into the media track; adapter splits TRACK/CHANNEL.",
            ),
        },
        equivalence={
            "ableton_live": "CLOSE",
            "cubase": "EXACT",
            "logic_pro": "NONE",
            "reaper": "STRUCTURAL",
        },
    ),
)


class ConceptRegistry:
    """Lookup surface over :data:`CONCEPTS`.

    ``concepts_for_native(daw, native_type)`` is the reverse map the alignment
    engine uses: wire native_type → the concepts that DAW implements with it,
    in registry declaration order (specific before generic).
    """

    def __init__(self, concepts: tuple[ConceptEntry, ...] = CONCEPTS):
        self._concepts = concepts
        self._by_id = {c.concept_id: c for c in concepts}
        # (daw, wire_type) -> [concept_id, ...] in declaration order.
        self._reverse: dict[tuple[str, str], list[str]] = {}
        for concept in concepts:
            for daw, impl in concept.implementations.items():
                for wire in impl.wire_types:
                    self._reverse.setdefault((daw, wire), []).append(concept.concept_id)

    def __iter__(self):
        return iter(self._concepts)

    def concept_ids(self) -> tuple[str, ...]:
        return tuple(c.concept_id for c in self._concepts)

    def get(self, concept_id: str) -> Optional[ConceptEntry]:
        return self._by_id.get(concept_id)

    def __getitem__(self, concept_id: str) -> ConceptEntry:
        return self._by_id[concept_id]

    def implementations(self, concept_id: str) -> dict[str, Implementation]:
        return dict(self._by_id[concept_id].implementations)

    def equivalence(self, concept_id: str, daw: str) -> str:
        return self._by_id[concept_id].equivalence.get(daw, "UNKNOWN")

    def native_noun(self, concept_id: str, daw: str) -> Optional[str]:
        entry = self._by_id.get(concept_id)
        return entry.native_noun(daw) if entry else None

    def concepts_for_native(self, daw: str, native_type: Optional[str]) -> tuple[str, ...]:
        """Concepts ``daw`` implements with wire ``native_type`` (may be several).

        Declaration order = specificity order: ``('return',)`` on Ableton maps
        to ``effect_return`` before anything generic claims it.
        """
        if not native_type:
            return ()
        return tuple(self._reverse.get((daw, native_type), ()))


_DEFAULT: Optional[ConceptRegistry] = None


def get_registry() -> ConceptRegistry:
    """The shared default registry (built once from :data:`CONCEPTS`)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ConceptRegistry()
    return _DEFAULT


# --------------------------------------------------------------------------
# YAML generation (concepts.yaml is OUTPUT, not input — see module docstring)
# --------------------------------------------------------------------------

def _yq(text: str) -> str:
    """Quote a YAML scalar defensively (double-quoted style)."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_yaml(concepts: tuple[ConceptEntry, ...] = CONCEPTS) -> str:
    """Render the registry as human-readable YAML.

    Emitter, not parser: the analyzer never reads this back (PyYAML is not a
    dependency). Regenerate with
    ``python -m session_explorer.registry.concepts``.
    """
    lines: list[str] = [
        "# GENERATED from session_explorer/registry/concepts.py — do not edit.",
        "# The Python module is the source of truth; this file exists for humans.",
        "concepts:",
    ]
    for concept in concepts:
        lines.append(f"  - concept_id: {concept.concept_id}")
        lines.append(f"    description: {_yq(concept.description)}")
        lines.append("    implementations:")
        for daw, impl in concept.implementations.items():
            lines.append(f"      {daw}:")
            lines.append(f"        native_type: {impl.native_type}")
            if impl.wire_types:
                lines.append(
                    "        wire_types: ["
                    + ", ".join(impl.wire_types)
                    + "]"
                )
            else:
                lines.append("        wire_types: []")
            if impl.notes:
                lines.append(f"        notes: {_yq(impl.notes)}")
        lines.append("    equivalence:")
        for daw, level in concept.equivalence.items():
            lines.append(f"      {daw}: {level}")
    return "\n".join(lines) + "\n"


def write_yaml(path: Optional[Path] = None) -> Path:
    target = path or Path(__file__).with_name("concepts.yaml")
    target.write_text(to_yaml(), encoding="utf-8")
    return target


if __name__ == "__main__":  # pragma: no cover
    print(f"wrote {write_yaml()}")
