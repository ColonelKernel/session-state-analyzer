"""The closed vocabularies of the v0.2 contract, and the open rel-type registry.

Three orthogonal dimensions describe every value in a snapshot:

- **Evidence** — *how* a value entered the snapshot (observed from an
  artifact, inferred by a heuristic, asserted by a user, or known to exist
  but not recoverable).
- **Availability** — *whether* a field could be populated at all, and if not,
  why. Absence is always a stated fact, never a silent null.
- **SourceStability** — how durable the capture pathway is: an officially
  documented format will not shift under us; a reverse-engineered one may.

``EntityType`` is the small canonical core: 19 concepts, frozen for v0.2.
Everything DAW-specific lives in ``Entity.native`` and namespaced
``extensions`` — the core never grows to absorb one DAW's ontology.

``rel_type`` is deliberately a plain ``str`` with a registry rather than an
enum: relationship vocabulary evolves additively without a schema version
bump. Unknown types are flagged as validation *warnings*, never errors.
"""

from __future__ import annotations

from typing import Literal

# How a value entered the snapshot. Adapter contract uses exactly these four;
# "derived" values arrive as INFERRED with capture_method="derived_computation"
# (an analyzer-internal distinction, not a wire one).
Evidence = Literal["OBSERVED", "INFERRED", "ANNOTATED", "HIDDEN"]

EVIDENCE_VALUES: tuple[str, ...] = ("OBSERVED", "INFERRED", "ANNOTATED", "HIDDEN")

# Whether a field could be populated, and if not, why. Entities record only
# non-AVAILABLE statuses: availability is the exception ledger, not a census.
Availability = Literal[
    "AVAILABLE",
    "NOT_PRESENT",
    "INACCESSIBLE",
    "UNSUPPORTED",
    "NOT_APPLICABLE",
    "PARSE_ERROR",
    "REDACTED",
    "UNKNOWN",
]

AVAILABILITY_VALUES: tuple[str, ...] = (
    "AVAILABLE",
    "NOT_PRESENT",
    "INACCESSIBLE",
    "UNSUPPORTED",
    "NOT_APPLICABLE",
    "PARSE_ERROR",
    "REDACTED",
    "UNKNOWN",
)

# How durable the capture pathway is, best (officially documented format or
# API) to worst (a human typed it in).
SourceStability = Literal[
    "OFFICIAL_DOCUMENTED",
    "OFFICIAL_EXPORT",
    "SUPPORTED_INTEGRATION",
    "COMMUNITY_DOCUMENTED",
    "REVERSE_ENGINEERED",
    "UI_AUTOMATION",
    "HEURISTIC",
    "MANUAL",
]

SOURCE_STABILITY_VALUES: tuple[str, ...] = (
    "OFFICIAL_DOCUMENTED",
    "OFFICIAL_EXPORT",
    "SUPPORTED_INTEGRATION",
    "COMMUNITY_DOCUMENTED",
    "REVERSE_ENGINEERED",
    "UI_AUTOMATION",
    "HEURISTIC",
    "MANUAL",
)

# The 19 core concepts. Small on purpose: cross-DAW analysis needs a shared
# spine, not a union of four ontologies. DAW-native typing rides in
# ``Entity.native.native_type``.
EntityType = Literal[
    "PROJECT",
    "TIMELINE",
    "TRACK",
    "CHANNEL",
    "TEMPORAL_OBJECT",
    "MEDIA_ASSET",
    "MUSICAL_CONTENT",
    "PROCESSOR",
    "PARAMETER",
    "AUTOMATION",
    "MODULATION",
    "ROUTING_ENDPOINT",
    "ROUTING_EDGE",
    "STRUCTURAL_CONTAINER",
    "VARIANT",
    "ANNOTATION",
    "RENDER",
    "OBSERVATION",
    "INTERVENTION",
]

ENTITY_TYPE_VALUES: tuple[str, ...] = (
    "PROJECT",
    "TIMELINE",
    "TRACK",
    "CHANNEL",
    "TEMPORAL_OBJECT",
    "MEDIA_ASSET",
    "MUSICAL_CONTENT",
    "PROCESSOR",
    "PARAMETER",
    "AUTOMATION",
    "MODULATION",
    "ROUTING_ENDPOINT",
    "ROUTING_EDGE",
    "STRUCTURAL_CONTAINER",
    "VARIANT",
    "ANNOTATION",
    "RENDER",
    "OBSERVATION",
    "INTERVENTION",
)

# The core relationship registry. ``rel_type`` stays str-typed so adapters can
# introduce DAW-specific relationships additively; validation flags unknown
# types as warnings so drift is visible without being fatal.
CORE_REL_TYPES: tuple[str, ...] = (
    "TRACK_USES_CHANNEL",
    "TRACK_CONTAINS_TEMPORAL_OBJECT",
    "CHANNEL_ROUTES_TO",
    "CHANNEL_SENDS_TO",
    "CHANNEL_PROCESSED_BY",
    "CONTAINS",
    "SUMS_TO",
    "CONTROLS",
    "LINKED_WITH",
    "ALTERNATIVE_OF",
    "DERIVED_FROM",
    "SHARES_SOURCE_WITH",
    "PRECEDES",
    "REFERENCES_ASSET",
    "GENERATED_BY",
)


def is_known_rel_type(rel_type: str) -> bool:
    """Whether ``rel_type`` is in the core registry.

    Unknown types are *allowed* on the wire (additive evolution); consumers
    that care surface them via validation warnings, never errors.
    """
    return rel_type in CORE_REL_TYPES
