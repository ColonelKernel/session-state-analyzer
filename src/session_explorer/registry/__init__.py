"""Concept registry: canonical concepts ↔ per-DAW native implementations.

Data-only, like the presentation registry (D4): it names and relates concepts,
it never parses or acquires anything. ``concepts.yaml`` in this package is
generated from :mod:`.concepts` for human readers — the Python module is the
source of truth (PyYAML is not a dependency).
"""

from .concepts import (
    CONCEPTS,
    EQUIVALENCE_LEVELS,
    KNOWN_DAWS,
    ConceptEntry,
    ConceptRegistry,
    EquivalenceLevel,
    Implementation,
    get_registry,
    to_yaml,
    write_yaml,
)

__all__ = [
    "CONCEPTS",
    "EQUIVALENCE_LEVELS",
    "KNOWN_DAWS",
    "ConceptEntry",
    "ConceptRegistry",
    "EquivalenceLevel",
    "Implementation",
    "get_registry",
    "to_yaml",
    "write_yaml",
]
