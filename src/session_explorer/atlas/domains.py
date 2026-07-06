"""The atlas domains: the master-prompt rows of the Observability Atlas.

The four adapters spoke four different domain vocabularies (REAPER's
``temporal``, Cubase's ``musical_content`` + ``cpr_evidence`` + ``midi_content``,
Logic's ``mixer_state`` + ``plugin_chain`` + ``audio_content``, Ableton's
``parameters``). The atlas fixes a single set of canonical rows and maps every
adapter's vocabulary — both its *entity types* (for what a snapshot measured)
and its *capability domains* (for what an adapter declares it can read) — onto
them, so the four DAWs can be read down one column of concepts instead of four
incommensurable ones.

Two deliberate rows have no measurable backing yet and MUST still render:

- **Modulation** — no adapter exports MODULATION entities and no capability
  manifest declares a modulation read-domain. The row renders NOT_APPLICABLE
  everywhere. Hiding it would be dishonest: "we cannot see this" is a finding.
- **Native Features** — not an entity type at all. It is measured from the
  presence of DAW-specific payload under ``snapshot.extensions[daw]`` and
  declared from the ``cpr_evidence`` capability domain (Cubase's
  reverse-engineered ``.cpr`` scan). The atlas counts extension top-level keys.

The one non-obvious modelling choice, documented per the plan:

    CHANNEL is a mixer/signal-flow concept, not an organizational one. Both the
    CHANNEL *entity* and the ``channel`` and ``mixer_state`` *capability
    domains* (volume / pan / mute / solo) are assigned to **Routing**, not
    Structure. Structure stays TRACK/PROJECT/container organization; Routing
    owns everything about where signal goes and at what level. This keeps a
    single, simple home for mixer state rather than splitting volume/pan into a
    "Mixer" sub-concept folded under Structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set


@dataclass(frozen=True)
class AtlasDomain:
    """One canonical row of the observability atlas.

    ``entity_types`` drives the *measured* side (which snapshot entities fall
    in this domain's scope); ``capability_domains`` drives the *declared* side
    (which adapter read-section domains map here — the UNION across the four
    dialect vocabularies). ``rel_types`` names the relationships that carry the
    domain's meaning, for graph drill-down.
    """

    name: str
    entity_types: Set[str] = field(default_factory=set)
    capability_domains: Set[str] = field(default_factory=set)
    rel_types: Set[str] = field(default_factory=set)
    description: str = ""


# The master-prompt rows, in presentation order. Every atlas over any set of
# bundles has exactly these ten rows — including the two (Modulation, and
# Native-Features-where-absent) that render NOT_APPLICABLE, because an honest
# profile shows the gaps.
_DOMAINS: tuple[AtlasDomain, ...] = (
    AtlasDomain(
        name="Structure",
        entity_types={"PROJECT", "TRACK", "STRUCTURAL_CONTAINER"},
        capability_domains={"structure"},
        rel_types={"CONTAINS", "TRACK_CONTAINS_TEMPORAL_OBJECT"},
        description=(
            "Project, tracks, and organizational containers — the arrangement "
            "skeleton, not its signal flow."
        ),
    ),
    AtlasDomain(
        name="Timeline",
        entity_types={"TEMPORAL_OBJECT", "TIMELINE"},
        capability_domains={"temporal"},
        rel_types={"TRACK_CONTAINS_TEMPORAL_OBJECT", "PRECEDES"},
        description="Clips, items, and time-positioned objects on the timeline.",
    ),
    AtlasDomain(
        name="Routing",
        entity_types={"ROUTING_ENDPOINT", "ROUTING_EDGE", "CHANNEL"},
        # channel + mixer_state (volume/pan/mute/solo) live here by the
        # documented CHANNEL-is-signal-flow choice, alongside routing proper.
        capability_domains={"routing", "channel", "mixer_state"},
        rel_types={
            "CHANNEL_SENDS_TO",
            "CHANNEL_ROUTES_TO",
            "TRACK_USES_CHANNEL",
            "SUMS_TO",
        },
        description=(
            "Signal flow and mixer state — channels, sends, routes, sums, and "
            "the volume/pan/mute/solo that live on a channel."
        ),
    ),
    AtlasDomain(
        name="Processing",
        entity_types={"PROCESSOR"},
        capability_domains={"processing", "plugin_chain"},
        rel_types={"CHANNEL_PROCESSED_BY"},
        description="Inserts, plug-ins, and device chains.",
    ),
    AtlasDomain(
        name="Parameters",
        entity_types={"PARAMETER"},
        capability_domains={"parameters"},
        rel_types={"CONTROLS"},
        description="Exposed plug-in / device parameters and their values.",
    ),
    AtlasDomain(
        name="Automation",
        entity_types={"AUTOMATION"},
        capability_domains={"automation"},
        rel_types={"CONTROLS"},
        description="Automation lanes and their control targets.",
    ),
    AtlasDomain(
        name="Modulation",
        entity_types={"MODULATION"},
        # Nothing yet: no adapter exports modulation, no manifest declares it.
        # The row renders NOT_APPLICABLE everywhere — an honest empty row.
        capability_domains=set(),
        rel_types={"CONTROLS"},
        description=(
            "LFOs, envelopes, and modulation sources. No adapter observes this "
            "yet — the row is present so the gap is visible, not hidden."
        ),
    ),
    AtlasDomain(
        name="Musical Content",
        entity_types={"MUSICAL_CONTENT", "MEDIA_ASSET"},
        capability_domains={"musical_content", "midi_content"},
        rel_types={"REFERENCES_ASSET"},
        description="Notes, chords, MIDI, and referenced media assets.",
    ),
    AtlasDomain(
        name="Native Features",
        # Not an entity type: measured from snapshot.extensions[daw] payload
        # presence (see coverage.measure_domain), declared from cpr_evidence.
        entity_types=set(),
        capability_domains={"cpr_evidence"},
        rel_types=set(),
        description=(
            "DAW-specific richness carried in the namespaced extensions payload "
            "— measured by extension key presence, declared by the .cpr "
            "reverse-engineering capability."
        ),
    ),
    AtlasDomain(
        name="Audio Outcome",
        entity_types={"RENDER", "OBSERVATION"},
        capability_domains={"audio_content"},
        rel_types={"GENERATED_BY"},
        description=(
            "The rendered / observed audio result — state-to-sound, the end of "
            "the acquisition chain."
        ),
    ),
)

# Public row list and lookup. ATLAS_DOMAINS is the string row order the UI and
# tests iterate; ATLAS_DOMAINS_BY_NAME resolves a row to its AtlasDomain.
ATLAS_DOMAINS: list[str] = [d.name for d in _DOMAINS]
ATLAS_DOMAINS_BY_NAME: dict[str, AtlasDomain] = {d.name: d for d in _DOMAINS}


def atlas_domains() -> tuple[AtlasDomain, ...]:
    """The ten atlas domains, in presentation order."""
    return _DOMAINS


def get_domain(name: str) -> AtlasDomain:
    """Resolve an atlas row name to its :class:`AtlasDomain` (KeyError if unknown)."""
    return ATLAS_DOMAINS_BY_NAME[name]
