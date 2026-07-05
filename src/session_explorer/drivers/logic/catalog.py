"""Catalogue of Logic Pro's documented stock plug-ins.

Sourced from Apple's official guides ("Logic Pro Effects for Mac", 390 pp.,
and "Logic Pro Instruments for Mac", 752 pp.), enumerated from their tables of
contents, legacy chapters, and named mentions. Two uses:

1. **Channel-strip note enrichment.** A user note that names "Channel EQ" or
   "DeEsser 2" can be recognised as documented Logic stock processing and
   tagged with its category — third-party or unrecognised names simply stay
   untagged. The note remains a user assertion either way; recognition adds
   vocabulary, not trust.
2. **Role inference.** The stock *instrument* table and
   ``instrument_role_in_tokens`` were promoted to
   :mod:`session_explorer.core.roles` (the benchmarked role-inference engine
   lives there now); they are re-exported here for compatibility rather than
   duplicated.

Category vocabulary for plug-ins: eq, dynamics, reverb, delay, modulation,
distortion, filter, imaging, pitch, utility, metering, amps_pedals,
multi_effects, specialized.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from ...core.matching import tokenize
from ...core.roles import (  # promoted to core; re-exported for compatibility
    STOCK_INSTRUMENTS,
    instrument_role_in_tokens,
)

# --------------------------------------------------------------------------- #
# Stock audio effect plug-ins ("Logic Pro Effects for Mac", TOC pp. 2-6).
# --------------------------------------------------------------------------- #
STOCK_PLUGINS: dict[str, str] = {
    "Amp Designer": "amps_pedals",
    "Bass Amp Designer": "amps_pedals",
    "Pedalboard": "amps_pedals",
    "Delay Designer": "delay",
    "Echo": "delay",
    "Sample Delay": "delay",
    "Stereo Delay": "delay",
    "Tape Delay": "delay",
    "Bitcrusher": "distortion",
    "ChromaGlow": "distortion",
    "Clip Distortion": "distortion",
    "Distortion": "distortion",
    "Distortion II": "distortion",
    "Overdrive": "distortion",
    "Phase Distortion": "distortion",
    "Adaptive Limiter": "dynamics",
    "Compressor": "dynamics",
    "DeEsser 2": "dynamics",
    "Enveloper": "dynamics",
    "Expander": "dynamics",
    "Limiter": "dynamics",
    "Multipressor": "dynamics",
    "Noise Gate": "dynamics",
    "Surround Compressor": "dynamics",
    "Channel EQ": "eq",
    "Linear Phase EQ": "eq",
    "Match EQ": "eq",
    "Single Band EQ": "eq",
    "Vintage Console EQ": "eq",
    "Vintage Graphic EQ": "eq",
    "Vintage Tube EQ": "eq",
    "AutoFilter": "filter",
    "EVOC 20 Filterbank": "filter",
    "EVOC 20 TrackOscillator": "filter",
    "Fuzz-Wah": "filter",
    "Spectral Gate": "filter",
    "Binaural Post-Processing": "imaging",
    "Direction Mixer": "imaging",
    "Spatial Audio Monitoring": "imaging",
    "Stereo Spread": "imaging",
    "BPM Counter": "metering",
    "Correlation Meter": "metering",
    "Level Meter": "metering",
    "Loudness Meter": "metering",
    "MultiMeter": "metering",
    "Surround MultiMeter": "metering",
    "Tuner": "metering",
    "Chorus": "modulation",
    "Ensemble": "modulation",
    "Flanger": "modulation",
    "Microphaser": "modulation",
    "Modulation Delay": "modulation",
    "Phaser": "modulation",
    "Ringshifter": "modulation",
    "Rotor Cabinet": "modulation",
    "Scanner Vibrato": "modulation",
    "Spreader": "modulation",
    "Tremolo": "modulation",
    "Beat Breaker": "multi_effects",
    "Phat FX": "multi_effects",
    "Remix FX": "multi_effects",
    "Step FX": "multi_effects",
    "Pitch Correction": "pitch",
    "Pitch Shifter": "pitch",
    "Vocal Transformer": "pitch",
    "ChromaVerb": "reverb",
    "EnVerb": "reverb",
    "Quantec Room Simulator": "reverb",
    "SilverVerb": "reverb",
    "Space Designer": "reverb",
    "Exciter": "specialized",
    "Mastering Assistant": "specialized",
    "SubBass": "specialized",
    "Auto Sampler": "utility",
    "Down Mixer": "utility",
    "Gain": "utility",
    "I/O": "utility",
    "Multichannel Gain": "utility",
    "Test Oscillator": "utility",
}

# Legacy effects ("Logic Pro Effects for Mac", Legacy chapter pp. 365-388).
# "DeEsser" here is the predecessor of the current "DeEsser 2"; "Bass Amp" and
# "Guitar Amp Pro" precede Bass Amp Designer / Amp Designer.
LEGACY_PLUGINS: dict[str, str] = {
    "Bass Amp": "amps_pedals",
    "Guitar Amp Pro": "amps_pedals",
    "DeEsser": "dynamics",
    "Ducker": "dynamics",
    "Silver Compressor": "dynamics",
    "Silver Gate": "dynamics",
    "DJ EQ": "eq",
    "Fat EQ": "eq",
    "Silver EQ": "eq",
    "High Cut": "eq",
    "High Pass Filter": "eq",
    "High Shelving EQ": "eq",
    "Low Cut": "eq",
    "Low Pass Filter": "eq",
    "Low Shelving EQ": "eq",
    "Parametric EQ": "eq",
    "AVerb": "reverb",
    "GoldVerb": "reverb",
    "PlatinumVerb": "reverb",
    "Denoiser": "specialized",
    "Grooveshifter": "specialized",
    "Speech Enhancer": "specialized",
}


class PluginInfo(NamedTuple):
    name: str
    category: str
    generation: str  # "current" | "legacy"


def _token_index() -> dict[tuple, PluginInfo]:
    index: dict[tuple, PluginInfo] = {}
    for name, category in LEGACY_PLUGINS.items():
        index[tuple(tokenize(name))] = PluginInfo(name, category, "legacy")
    # Current entries win on collision.
    for name, category in STOCK_PLUGINS.items():
        index[tuple(tokenize(name))] = PluginInfo(name, category, "current")
    return index


_PLUGIN_INDEX = _token_index()


def lookup_plugin(name: str) -> Optional[PluginInfo]:
    """Recognise a documented Logic stock plug-in by (token-exact) name.

    Third-party or unrecognised names return ``None`` — that is expected, not
    an error; recognition only adds vocabulary to user-provided notes.
    """

    return _PLUGIN_INDEX.get(tuple(tokenize(name)))


# --------------------------------------------------------------------------- #
# Knowledge-lookup bridge for the generic classifier
# (:func:`session_explorer.core.roles.classify_processor_family`): guide
# category -> core processor family. Categories with no clean family
# counterpart map to None so the keyword heuristics take over.
# --------------------------------------------------------------------------- #
_CATEGORY_TO_FAMILY: dict[str, Optional[str]] = {
    "eq": "EQ",
    "dynamics": "Dynamics",
    "reverb": "Ambience",
    "delay": "Ambience",
    "modulation": "Modulation",
    "distortion": "Saturation",
    "amps_pedals": "Saturation",
    "pitch": "Pitch",
    "metering": "Metering",
    "utility": "Utility",
    "filter": None,
    "imaging": None,
    "multi_effects": None,
    "specialized": None,
}


def stock_family(name: str) -> Optional[str]:
    """A ``core.roles.KnowledgeLookup``: documented stock plug-in -> family.

    Returns ``None`` for third-party names and for categories without a clean
    family counterpart, letting the generic keyword heuristics decide.
    """

    info = lookup_plugin(name)
    if info is None:
        return None
    return _CATEGORY_TO_FAMILY.get(info.category)


__all__ = [
    "STOCK_PLUGINS",
    "LEGACY_PLUGINS",
    "STOCK_INSTRUMENTS",
    "PluginInfo",
    "lookup_plugin",
    "instrument_role_in_tokens",
    "stock_family",
]
