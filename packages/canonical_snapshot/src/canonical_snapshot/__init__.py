"""canonical-snapshot: the v0.2 contract between DAW adapters and the analyzer.

Public API:

- :mod:`.enums` — Evidence / Availability / SourceStability / EntityType and
  the open ``rel_type`` registry.
- :mod:`.models` — the flat wire format (``CanonicalDAWSnapshot``).
- :mod:`.capabilities` — capability manifests and adapter descriptors.
- :mod:`.validation` — ``validate_snapshot`` and the loud schema gate.
- :mod:`.nested` — the v0.1 nested intermediate adapters use internally.
- :mod:`.from_nested` — ``flatten_session()``, the one nested→flat converter.
"""

from .capabilities import (
    AdapterDescriptor,
    CapabilityManifest,
    CapabilitySection,
    DomainCapability,
    FieldCapability,
)
from .enums import (
    AVAILABILITY_VALUES,
    Availability,
    CORE_REL_TYPES,
    ENTITY_TYPE_VALUES,
    EVIDENCE_VALUES,
    EntityType,
    Evidence,
    SOURCE_STABILITY_VALUES,
    SourceStability,
    is_known_rel_type,
)
from .from_nested import ROLE_TO_SEMANTIC, flatten_session
from .models import (
    SCHEMA_VERSION,
    CanonicalDAWSnapshot,
    DomainCoverage,
    Entity,
    FailureRecord,
    NativeRef,
    ProvenanceRecord,
    Relationship,
    SourceInfo,
)
from .validation import (
    IncompatibleSchemaError,
    ValidationReport,
    validate_snapshot,
)

__version__ = "0.2.0"

__all__ = [
    # enums
    "Evidence",
    "Availability",
    "SourceStability",
    "EntityType",
    "EVIDENCE_VALUES",
    "AVAILABILITY_VALUES",
    "SOURCE_STABILITY_VALUES",
    "ENTITY_TYPE_VALUES",
    "CORE_REL_TYPES",
    "is_known_rel_type",
    # models
    "SCHEMA_VERSION",
    "NativeRef",
    "ProvenanceRecord",
    "Entity",
    "Relationship",
    "SourceInfo",
    "DomainCoverage",
    "FailureRecord",
    "CanonicalDAWSnapshot",
    # capabilities
    "FieldCapability",
    "DomainCapability",
    "CapabilitySection",
    "CapabilityManifest",
    "AdapterDescriptor",
    # validation
    "ValidationReport",
    "IncompatibleSchemaError",
    "validate_snapshot",
    # converter
    "flatten_session",
    "ROLE_TO_SEMANTIC",
    "__version__",
]
