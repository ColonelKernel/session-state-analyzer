"""Heuristic role and processor-family classification.

Two complementary layers live here, both heuristic metadata only — they inform
recommendations and graph annotations, but they are never presented as ground
truth, and every result is expressible as a :class:`~.provenance.Provenance`
with ``observability="inferred"``.

1. **Filename-based track-role inference** (the benchmarked engine, ported
   verbatim from the Logic prototype). Role inference here is deliberately
   transparent: it is keyword matching over the *tokens* of a filename, and
   every result carries a confidence score and a human-readable explanation.
   It makes no claim about the actual content of a stem beyond what its name
   suggests.

2. **Generic keyword classification** of track roles and processor families
   from names (the union of the Ableton and REAPER prototype taxonomies).
   Substring matching with ordered first-match-wins semantics, plus a
   whole-token pass for short/ambiguous keywords. Drivers may override the
   tables with their own :class:`KeywordSets`, and may supply a
   ``knowledge_lookup`` consulted authoritatively before any keyword
   heuristics (e.g. a guide-derived stock-processor table).

Two design points matter for real-world exports (layer 1):

1. Matching is token-based, not substring-based, so ``Refrain_Guitar.wav`` is
   a guitar stem (not a "ref"-erence) and ``Take3`` never matches anything.
2. Mixdown detection is split into *strong* and *weak* keywords. Strong
   keywords ("stereo mix", "master", "mixdown") mark a mixdown outright. Weak
   keywords ("mix", "bounce", "stereo", "final") only mark a mixdown when the
   filename carries no instrument-role token — this is what lets
   ``05_Lead_Vocal_Bounce.wav``, ``Acoustic_Guitar_Stereo.wav`` and
   ``Final_Vocal_Comp.wav`` be read as stems, even though Logic and producers
   routinely decorate stem names with "Bounce", "Stereo" and "Final".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .matching import tokenize, tokens_equal
from .provenance import Provenance, inferred

# ===========================================================================
# Layer 1 — filename-based track-role inference (benchmarked engine)
# ===========================================================================

# Instrument / production-role keywords, checked in order. The base lists
# follow common Logic naming; the extensions marked "corpus" are generic
# production vocabulary that benchmarking against MedleyDB's instrument
# labels exposed as missing. Note the extensions were selected from misses on
# that same corpus, so the accuracy reported in docs/evaluation.md is
# in-sample vocabulary coverage, not held-out generalization.
INSTRUMENT_ROLE_KEYWORDS: dict[str, list[str]] = {
    "Vocal": ["backing vocal", "lead vox", "vocal", "vox", "voice", "bgv", "harmony",
              # corpus:
              "singer", "vocalist", "rapper", "rap", "choir"],
    "Drums": ["drums", "drum", "kick", "snare", "hihat", "hi-hat", "hat", "tom",
              "percussion", "perc", "beat",
              # corpus:
              "cymbal", "tabla", "tambourine", "clap", "shaker", "timpani", "bongo"],
    "Bass": ["bass", "sub", "808"],
    "Guitar": ["electric guitar", "acoustic guitar", "guitar", "gtr"],
    "Keys": ["keys", "piano", "rhodes", "organ", "synth", "pad", "lead synth",
             # corpus:
             "synthesizer"],
    "Strings": ["strings", "violin", "viola", "cello"],
    "Brass": ["brass", "trumpet", "trombone", "horn",
              # corpus:
              "tuba", "cornet", "euphonium"],
    "FX": ["riser", "impact", "sweep", "texture", "noise", "fx"],
    "Bus": ["bus", "group", "aux", "stem"],
}

STRONG_MIXDOWN_KEYWORDS = ["full mix", "stereo mix", "mixdown", "master"]
WEAK_MIXDOWN_KEYWORDS = ["mix", "bounce", "stereo", "final"]
MIXDOWN_KEYWORDS = STRONG_MIXDOWN_KEYWORDS + WEAK_MIXDOWN_KEYWORDS
REFERENCE_KEYWORDS = ["reference", "ref", "target"]

# Convenience mapping mirroring the spec's keyword table (used for docs/tests).
ROLE_KEYWORDS: dict[str, list[str]] = {
    "Mixdown": MIXDOWN_KEYWORDS,
    "Reference": REFERENCE_KEYWORDS,
    **INSTRUMENT_ROLE_KEYWORDS,
}

# ---------------------------------------------------------------------------
# Stock software instruments ("Logic Pro Instruments for Mac", TOC pp. 2-8,
# legacy chapter pp. 710-721), mapped to this project's role taxonomy.
# Logic names new tracks after the chosen patch or instrument ("When you
# choose a patch for a track, the track takes the name of the patch" — Logic
# Pro User Guide, p. 129), so exported stems routinely carry stock instrument
# names like "Alchemy" or "Ultrabeat". Distinctive instrument names therefore
# ground filename role inference in documented Logic vocabulary.
#
# Samplers and hosts that can play anything map to None (abstain), matching
# the evaluation's out-of-taxonomy policy. "Woodwind" also abstains: the
# taxonomy has no woodwind bucket.
#
# (The companion stock *plug-in* catalogue used for channel-strip note
# enrichment stays with the Logic driver; only role inference lives in core.)
# ---------------------------------------------------------------------------
STOCK_INSTRUMENTS: dict[str, Optional[str]] = {
    "Alchemy": "Keys",
    "Drum Kit Designer": "Drums",
    "Drum Machine Designer": "Drums",
    "Drum Synth": "Drums",
    "Ultrabeat": "Drums",
    "ES1": "Keys",
    "ES2": "Keys",
    "EFM1": "Keys",
    "ES E": "Keys",
    "ES M": "Bass",  # explicitly bass-oriented per its chapter overview
    "ES P": "Keys",
    # Vocoder — arguably voice-derived, but "synth" in the name means the
    # Keys keyword always matches first; mapped Keys so the catalog agrees
    # with actual inference behaviour.
    "EVOC 20 PolySynth": "Keys",
    "Retro Synth": "Keys",
    "Sample Alchemy": None,
    "Sampler": None,
    "Quick Sampler": None,
    "Sculpture": "Keys",
    "Studio Bass": "Bass",
    "Studio Horns": "Brass",
    "Studio Piano": "Keys",
    "Studio Strings": "Strings",
    "Vintage B3": "Keys",
    "Vintage Clav": "Keys",
    "Vintage Electric Piano": "Keys",
    "Vintage Mellotron": "Keys",
    "External Instrument": None,
    "Klopfgeist": "FX",  # Logic's metronome click instrument
    # Legacy instruments (documented names, "Legacy" chapter):
    "Church Organ": "Keys",
    "Tonewheel Organ": "Keys",
    "Electric Clav": "Keys",
    "Tuned Percussion": "Drums",
    "Woodwind": None,
}

_INSTRUMENT_INDEX = {
    tuple(tokenize(name)): (name, role)
    for name, role in STOCK_INSTRUMENTS.items()
}


def instrument_role_in_tokens(tokens: list[str]) -> Optional[tuple[str, str]]:
    """Find a documented stock instrument name as a contiguous token
    subsequence and return ``(instrument_name, role)``.

    Grounds role inference in Logic's documented behaviour of naming tracks
    after the chosen patch/instrument. Instruments mapped to ``None`` (e.g.
    Sampler) never produce a role — the correct behaviour there is abstention.
    """

    # Match ALL entries — including abstaining (None-mapped) ones — and keep
    # the longest: "Sample Alchemy" (abstain) must shadow the shorter
    # "Alchemy" (Keys) it contains, or the abstention policy is bypassed.
    best_name: Optional[str] = None
    best_role: Optional[str] = None
    best_len = 0
    for key, (name, role) in _INSTRUMENT_INDEX.items():
        n = len(key)
        if n <= best_len:
            continue
        for i in range(len(tokens) - n + 1):
            if tuple(tokens[i:i + n]) == key:
                best_name, best_role, best_len = name, role, n
                break
    if best_name is not None and best_role is not None:
        return (best_name, best_role)
    return None


@dataclass
class RoleInferenceResult:
    role: str
    confidence: float
    explanation: str
    matched_keyword: str | None = None

    def to_provenance(self, source_artifact: Optional[str] = None) -> Provenance:
        """Express this heuristic result as canonical inferred provenance."""

        return inferred(
            explanation=self.explanation,
            confidence=self.confidence,
            source_artifact=source_artifact,
        )


def _search(tokens: list[str], keywords: list[str]) -> str | None:
    """Match keywords against the token list. Multi-word keywords must appear
    as a contiguous token subsequence; individual tokens tolerate a plural
    's' (keyword 'vocal' matches the token 'vocals')."""

    for kw in keywords:
        kw_tokens = tokenize(kw)
        n = len(kw_tokens)
        for i in range(len(tokens) - n + 1):
            if all(tokens_equal(tokens[i + j], kw_tokens[j]) for j in range(n)):
                return kw
    return None


def _find_instrument_role(tokens: list[str]) -> tuple[str, str] | None:
    for role, keywords in INSTRUMENT_ROLE_KEYWORDS.items():
        kw = _search(tokens, keywords)
        if kw:
            return role, kw
    return None


def looks_like_mixdown(file_name: str) -> bool:
    tokens = tokenize(file_name)
    if _search(tokens, REFERENCE_KEYWORDS):
        return False
    if _search(tokens, STRONG_MIXDOWN_KEYWORDS):
        return True
    if _search(tokens, WEAK_MIXDOWN_KEYWORDS):
        # Weak keywords ("bounce", "mix", "stereo", "final") only mark a
        # mixdown when NO instrument evidence is present — neither a role
        # keyword nor a Logic stock instrument name ("Ultrabeat_Bounce.wav"
        # is a drum stem, not a mixdown). Must stay consistent with
        # infer_role's step order.
        if _find_instrument_role(tokens) is None and instrument_role_in_tokens(tokens) is None:
            return True
    return False


def looks_like_reference(file_name: str) -> bool:
    return _search(tokenize(file_name), REFERENCE_KEYWORDS) is not None


def infer_role(file_name: str) -> RoleInferenceResult:
    """Infer a production role from a filename.

    Returns an ``Unknown`` result with low confidence when nothing matches.
    """

    tokens = tokenize(file_name)

    # 1. Reference takes precedence.
    ref_kw = _search(tokens, REFERENCE_KEYWORDS)
    if ref_kw:
        return RoleInferenceResult("Reference", 0.7,
                                   f"Filename contains reference keyword '{ref_kw}'.", ref_kw)

    # 2. Strong mixdown keywords.
    strong = _search(tokens, STRONG_MIXDOWN_KEYWORDS)
    if strong:
        return RoleInferenceResult("Mixdown", 0.75,
                                   f"Filename contains mixdown keyword '{strong}'.", strong)

    # 3. Instrument / production role.
    instrument = _find_instrument_role(tokens)
    if instrument:
        role, kw = instrument
        confidence = 0.85 if " " in kw else 0.75
        return RoleInferenceResult(role, confidence,
                                   f"Filename contains {role.lower()} keyword '{kw}'.", kw)

    # 3b. Logic stock instrument names. Logic names new tracks after the
    # chosen patch/instrument (User Guide p. 129), so exported stems routinely
    # carry names like "Alchemy" or "Ultrabeat".
    stock = instrument_role_in_tokens(tokens)
    if stock:
        name, role = stock
        return RoleInferenceResult(
            role, 0.8,
            f"Filename contains the Logic stock instrument name '{name}' "
            "(Logic names tracks after the chosen patch/instrument).",
            name.lower(),
        )

    # 4. Weak mixdown keywords (only reached when no instrument role matched).
    weak = _search(tokens, WEAK_MIXDOWN_KEYWORDS)
    if weak:
        return RoleInferenceResult("Mixdown", 0.55,
                                   f"Filename contains mixdown keyword '{weak}' and no instrument keyword.", weak)

    return RoleInferenceResult("Unknown", 0.2,
                               "No known role keyword matched the filename.", None)


# ===========================================================================
# Layer 2 — generic keyword classification (union of Ableton + REAPER tables)
# ===========================================================================
# Order matters: families/roles are checked top-to-bottom and the first match
# wins. Keywords are matched case-insensitively as substrings of the name;
# short/ambiguous keywords live in the token tables and must match a whole
# token, never a substring.

# Default ordered track-role table. Buses first (REAPER's ordering): a
# "vocal bus" should read as a Bus, not a Vocal track.
TRACK_ROLE_KEYWORDS: List[tuple[str, List[str]]] = [
    ("Bus", ["bus", "group", "aux", "return", "submix", "verb", "delay"]),
    ("Vocal", ["lead vox", "bgv", "vocal", "vox", "voice"]),
    (
        "Drums",
        ["drum", "kick", "snare", "hat", "tom", "perc", "percussion", "cymbal",
         "overhead", "beat"],
    ),
    ("Bass", ["bass", "sub", "808"]),
    ("Guitar", ["guitar", "gtr"]),
    ("Keys", ["keys", "piano", "rhodes", "organ", "synth", "pad", "nord", "mellotron"]),
    ("FX", ["riser", "impact", "noise", "sweep", "whoosh", "fx"]),
    ("Master", ["master"]),
]

# Short/ambiguous keywords that must match a whole token, not a substring
# ("oh" for drum overheads would otherwise match inside "john"; "eq" would
# match inside "frequency"). Checked only after the substring pass finds
# nothing.
TRACK_ROLE_TOKEN_KEYWORDS: List[tuple[str, List[str]]] = [
    ("Drums", ["oh"]),
]

# Default ordered processor-family table (union of the Ableton device table
# and the REAPER FX table; REAPER's ordering and finer-grained Metering
# family kept).
FX_FAMILY_KEYWORDS: List[tuple[str, List[str]]] = [
    ("EQ", ["pro-q", "channel eq", "equalizer", "equaliser", "eight"]),
    (
        "Dynamics",
        [
            "de-esser",
            "deesser",
            "compressor",
            "comp",
            "glue",
            "limiter",
            "gate",
            "expander",
            "dynamics",
        ],
    ),
    (
        "Ambience",
        ["reverb", "delay", "echo", "room", "hall", "plate", "space", "verb"],
    ),
    (
        "Saturation",
        ["saturat", "distortion", "overdrive", "tape", "tube", "drive", "crunch",
         "amp", "cabinet"],
    ),
    ("Modulation", ["chorus", "flanger", "phaser", "tremolo", "ensemble", "auto pan"]),
    ("Pitch", ["pitch", "autotune", "auto-tune", "melodyne", "harmonizer",
               "harmoniser", "vocoder"]),
    ("Metering", ["meter", "analyzer", "analyser", "scope", "spectrograph", "tuner"]),
    ("Utility", ["gain", "trim", "utility"]),
    (
        "Instrument",
        ["wavetable", "operator", "sampler", "simpler", "drift", "analog",
         "collision", "tension"],
    ),
    ("MIDI Effect", ["arpeggiator", "chord", "scale", "velocity", "note length"]),
]

FX_FAMILY_TOKEN_KEYWORDS: List[tuple[str, List[str]]] = [
    ("EQ", ["eq"]),
]

# Keywords indicating ambience-like processing, used by recommendation rules.
AMBIENCE_KEYWORDS = ["reverb", "delay", "echo", "room", "hall", "plate", "space"]

# Keywords indicating a limiter-like device on the master chain.
LIMITER_KEYWORDS = ["limiter", "maximizer", "brickwall"]

# Keywords indicating a de-esser-like corrective device.
DEESSER_KEYWORDS = ["de-esser", "deesser", "de esser", "sibilance"]

# Families considered "ambience-like" and "dynamics-like" / "eq-like" for the
# recommendation engine and session fingerprint.
AMBIENCE_FAMILIES = {"Ambience"}
DYNAMICS_FAMILIES = {"Dynamics"}
EQ_FAMILIES = {"EQ"}

VOCAL_ROLE_KEYWORDS = ["vocal", "vox", "voice", "bgv", "lead vox"]

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")

# A driver-supplied authoritative lookup: name -> family (or None to fall
# through to the keyword heuristics). E.g. the REAPER driver's guide-derived
# stock-FX knowledge table.
KnowledgeLookup = Callable[[str], Optional[str]]


@dataclass
class KeywordSets:
    """The complete keyword vocabulary the generic classifiers run on.

    ``DEFAULT_KEYWORDS`` is the union of the Ableton and REAPER prototype
    tables; drivers override any table with their own dialect vocabulary
    (``dataclasses.replace(DEFAULT_KEYWORDS, ...)`` keeps the rest).
    Ordering is semantic: earlier entries win.
    """

    role_keywords: List[tuple[str, List[str]]] = field(
        default_factory=lambda: list(TRACK_ROLE_KEYWORDS))
    role_token_keywords: List[tuple[str, List[str]]] = field(
        default_factory=lambda: list(TRACK_ROLE_TOKEN_KEYWORDS))
    family_keywords: List[tuple[str, List[str]]] = field(
        default_factory=lambda: list(FX_FAMILY_KEYWORDS))
    family_token_keywords: List[tuple[str, List[str]]] = field(
        default_factory=lambda: list(FX_FAMILY_TOKEN_KEYWORDS))
    ambience_keywords: List[str] = field(default_factory=lambda: list(AMBIENCE_KEYWORDS))
    limiter_keywords: List[str] = field(default_factory=lambda: list(LIMITER_KEYWORDS))
    deesser_keywords: List[str] = field(default_factory=lambda: list(DEESSER_KEYWORDS))


DEFAULT_KEYWORDS = KeywordSets()


def classify_track_role(name: Optional[str], keywords: KeywordSets = DEFAULT_KEYWORDS) -> str:
    """Return a coarse production role for a track name (``"Unknown"`` if no match).

    Heuristic metadata only — never presented as ground truth.
    """

    if not name:
        return "Unknown"
    lowered = name.lower()
    for role, kws in keywords.role_keywords:
        if any(keyword in lowered for keyword in kws):
            return role
    tokens = set(_TOKEN_SPLIT_RE.split(lowered))
    for role, kws in keywords.role_token_keywords:
        if any(keyword in tokens for keyword in kws):
            return role
    return "Unknown"


def classify_processor_family(
    name: Optional[str],
    keywords: KeywordSets = DEFAULT_KEYWORDS,
    knowledge_lookup: Optional[KnowledgeLookup] = None,
) -> str:
    """Return a coarse family for a processor name (``"Unknown"`` if no match).

    A driver-supplied ``knowledge_lookup`` (e.g. a guide-derived stock-FX
    table) is consulted first and wins outright when it returns a family;
    everything else falls back to the keyword heuristics.
    """

    if not name:
        return "Unknown"
    if knowledge_lookup is not None:
        known = knowledge_lookup(name)
        if known is not None:
            return known
    lowered = name.lower()
    for family, kws in keywords.family_keywords:
        if any(keyword in lowered for keyword in kws):
            return family
    tokens = set(_TOKEN_SPLIT_RE.split(lowered))
    for family, kws in keywords.family_token_keywords:
        if any(keyword in tokens for keyword in kws):
            return family
    return "Unknown"


def is_ambience_fx(
    name: Optional[str],
    keywords: KeywordSets = DEFAULT_KEYWORDS,
    knowledge_lookup: Optional[KnowledgeLookup] = None,
) -> bool:
    """True when a processor name reads as ambience (reverb/delay/echo/...)."""

    return classify_processor_family(name, keywords, knowledge_lookup) in AMBIENCE_FAMILIES


def is_vocal_name(name: Optional[str]) -> bool:
    """True when a track name reads as a vocal role."""

    if not name:
        return False
    lowered = name.lower()
    return any(keyword in lowered for keyword in VOCAL_ROLE_KEYWORDS)
