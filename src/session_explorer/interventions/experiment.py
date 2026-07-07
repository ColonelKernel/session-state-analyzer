"""The frozen effect-send experiment — P9's primary state→audio demonstration.

:func:`build_effect_send_experiment` loads the two frozen Cubase bundles
(``before`` = a vocal routed straight to the master; ``after`` = the same
session with one post-fader send added to a shared plate-reverb return), the
two render descriptors, and the ``intervention.json`` record, then runs
:func:`compare_intervention`. It is deterministic — no wall-clock, no audio
decode at call time, everything reads from disk — so two calls return equal
comparisons and the workbench and the tests see the same object.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from session_explorer.core.models import AudioDescriptorSet
from session_explorer.loaders.bundle import load_bundle

from .compare import compare_intervention
from .models import Intervention, InterventionComparison, Render

# Repo-root-relative default: src/session_explorer/interventions/ → parents[3].
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURES_DIR = _REPO_ROOT / "fixtures" / "experiments" / "effect_send"

# render_id → the descriptor file that backs it, and the render's fixed facts.
# These renders are SYNTHETIC (fixture-generated) but carry real acoustic
# descriptors of real audio — the same honesty policy as the Logic synthetic
# demo.
_RENDERS = (
    ("render:routing_a", "routing_a.descriptors.json", "routing_a.wav"),
    ("render:routing_b", "routing_b.descriptors.json", "routing_b.wav"),
)
_RENDER_FACTS = dict(sample_rate=44100, channels=1, n_samples=88200, synthetic=True)


def load_render_descriptors(
    fixtures_dir: Path | str = DEFAULT_FIXTURES_DIR,
) -> dict[str, Render]:
    """Load the frozen render descriptors into a ``render_id → Render`` map."""
    base = Path(fixtures_dir) / "renders"
    renders: dict[str, Render] = {}
    for render_id, descriptor_file, file_name in _RENDERS:
        descriptor: Optional[AudioDescriptorSet] = None
        path = base / descriptor_file
        if path.is_file():
            descriptor = AudioDescriptorSet.model_validate(
                json.loads(path.read_text(encoding="utf-8"))
            )
        renders[render_id] = Render(
            id=render_id,
            file_name=file_name,
            descriptor=descriptor,
            notes="Synthetic fixture render; descriptor only (WAV not committed).",
            **_RENDER_FACTS,
        )
    return renders


def load_intervention(
    fixtures_dir: Path | str = DEFAULT_FIXTURES_DIR,
) -> Intervention:
    """Load the frozen ``intervention.json`` record."""
    path = Path(fixtures_dir) / "intervention.json"
    return Intervention.model_validate(json.loads(path.read_text(encoding="utf-8")))


def build_effect_send_experiment(
    fixtures_dir: Path | str = DEFAULT_FIXTURES_DIR,
) -> InterventionComparison:
    """Assemble the effect-send comparison from the frozen fixture. Deterministic."""
    base = Path(fixtures_dir)
    before_bundle = load_bundle(base / "before")
    after_bundle = load_bundle(base / "after")
    intervention = load_intervention(base)
    renders = load_render_descriptors(base)
    return compare_intervention(before_bundle, after_bundle, intervention, renders)
