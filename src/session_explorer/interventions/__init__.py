"""Controlled state→audio interventions (P9).

A single semantic change ("add a post-fader effect send from the vocal to a
shared reverb return") realized natively in a DAW, captured as two frozen
canonical snapshots plus two renders, and read back as one chain:

    state delta  →  signal-flow explanation  →  acoustic delta

The models describe the controlled A/B; :mod:`compare` computes the chain;
:mod:`experiment` freezes the flagship effect-send demonstration.
"""

from __future__ import annotations

from .compare import (
    acoustic_delta,
    compare_intervention,
    explain_signal_flow,
    snapshot_delta,
)
from .experiment import (
    DEFAULT_FIXTURES_DIR,
    build_effect_send_experiment,
    load_intervention,
    load_render_descriptors,
)
from .models import (
    AcousticDelta,
    AcousticMetric,
    DeltaRecord,
    Intervention,
    InterventionComparison,
    Observation,
    Render,
    SemanticParameterRole,
    SignalFlowChange,
    StateDelta,
)

__all__ = [
    "AcousticDelta",
    "AcousticMetric",
    "DeltaRecord",
    "Intervention",
    "InterventionComparison",
    "Observation",
    "Render",
    "SemanticParameterRole",
    "SignalFlowChange",
    "StateDelta",
    "acoustic_delta",
    "compare_intervention",
    "explain_signal_flow",
    "snapshot_delta",
    "build_effect_send_experiment",
    "load_intervention",
    "load_render_descriptors",
    "DEFAULT_FIXTURES_DIR",
]
