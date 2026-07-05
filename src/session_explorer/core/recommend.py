"""The recommendation rule engine and the core cross-DAW rule pack.

Rules are explainable by construction: each one cites the graph nodes it
looked at, states its reasoning, and carries a caveat. The engine consults
the session dialect's observation matrix — a rule whose required state field
is *hidden* for this dialect/artifact is skipped with an explicit info note
instead of silently, turning partial observability into visible product
behavior.

Dialect drivers contribute their own rule packs (REAPER's guide-cited rules,
Logic's evidence rules) on top of — or instead of — the core pack below; the
core rules are the consolidated, canonical-schema versions of the heuristics
all three prototypes shared.
"""

from __future__ import annotations

from typing import Optional

from .driver import Rule
from .ids import make_id
from .models import CanonicalSession, Recommendation, Track
from .observability import hidden_fields
from .roles import DEFAULT_KEYWORDS, AMBIENCE_FAMILIES

_SEVERITY_ORDER = {"warning": 0, "suggestion": 1, "info": 2}

DENSE_CHAIN_THRESHOLD = 6
LEVEL_IMBALANCE_DB = 12.0


def run_rules(
    session: CanonicalSession,
    rules: list[Rule],
    artifact_type: Optional[str] = None,
) -> list[Recommendation]:
    """Evaluate rules against a session, honoring the observability boundary."""
    artifact = artifact_type or session.metadata.get("source_artifact")
    hidden = set(hidden_fields(session.dialect, artifact)) if artifact else set()

    recommendations: list[Recommendation] = []
    for rule in rules:
        blocked = sorted(set(rule.requires) & hidden)
        if blocked:
            recommendations.append(
                Recommendation(
                    id=make_id("rec"),
                    title=f"Rule '{rule.rule_id}' not evaluable for this session",
                    severity="info",
                    confidence=1.0,
                    explanation=(
                        f"This rule needs {', '.join(blocked)}, which the "
                        f"{session.dialect} evidence source ({artifact}) does not "
                        "reveal."
                    ),
                    suggested_action=(
                        "Provide additional evidence (annotations, richer exports) "
                        "to move the observability boundary."
                    ),
                    caveat="Skipping is deliberate: absence of evidence is not evidence of absence.",
                )
            )
            continue
        recommendations.extend(rule.fn(session))

    recommendations.sort(
        key=lambda r: (_SEVERITY_ORDER.get(r.severity, 3), -r.confidence)
    )
    return recommendations


# ---------------------------------------------------------------------------
# Core cross-DAW rules (canonical-schema consolidations of shared heuristics)
# ---------------------------------------------------------------------------


def _regular_tracks(session: CanonicalSession) -> list[Track]:
    return [t for t in session.tracks if t.kind not in ("return", "master")]


def _bus_like_tracks(session: CanonicalSession) -> list[Track]:
    return [t for t in session.tracks if t.kind in ("return", "aux") or t.role == "Bus"]


def rule_shared_ambience(session: CanonicalSession) -> list[Recommendation]:
    """Multiple per-track ambience processors with no shared bus routing."""
    carriers = [
        t
        for t in _regular_tracks(session)
        if any((p.family or "") in AMBIENCE_FAMILIES for p in t.processors)
    ]
    if len(carriers) < 2:
        return []
    routed_sources = {r.source_track_id for r in session.routes if r.source_track_id}
    unrouted = [t for t in carriers if t.id not in routed_sources]
    if len(unrouted) < 2:
        return []
    return [
        Recommendation(
            id=make_id("rec"),
            title="Consider routing ambience through a shared bus",
            severity="suggestion",
            confidence=0.7,
            related_node_ids=[t.id for t in unrouted],
            explanation=(
                f"{len(unrouted)} tracks carry their own ambience processors "
                "and no sends to a shared bus/return were observed. A shared "
                "ambience bus usually eases level control and creates a more "
                "coherent space."
            ),
            suggested_action=(
                "Move reverb/delay to a bus or return track and send the "
                "individual tracks to it."
            ),
            caveat=(
                "Per-track ambience is a legitimate aesthetic choice; this is a "
                "workflow observation, not a rule."
            ),
        )
    ]


def rule_unused_returns(session: CanonicalSession) -> list[Recommendation]:
    """Return/bus tracks that carry processors but receive no routes."""
    targets = {r.target_track_id for r in session.routes if r.target_track_id}
    unused = [
        t
        for t in _bus_like_tracks(session)
        if t.processors and t.id not in targets
    ]
    if not unused:
        return []
    names = ", ".join(f"'{t.name}'" for t in unused)
    return [
        Recommendation(
            id=make_id("rec"),
            title="Bus/return tracks defined but not receiving sends",
            severity="info",
            confidence=0.8,
            related_node_ids=[t.id for t in unused],
            explanation=(
                f"{names} carry processors but no observed route feeds them, so "
                "their chains are silent as far as the session graph shows."
            ),
            suggested_action="Send tracks to them, or remove them to reduce clutter.",
            caveat=(
                "Routing that the evidence source does not expose (or that is "
                "automated in) would not appear here."
            ),
        )
    ]


def rule_vocal_corrective_chain(session: CanonicalSession) -> list[Recommendation]:
    """Vocal tracks without any corrective dynamics (de-esser-like) processor."""
    keywords = DEFAULT_KEYWORDS.deesser_keywords
    results = []
    for track in _regular_tracks(session):
        if track.role != "Vocal" or not track.processors:
            continue
        has_deesser = any(
            any(k in p.name.lower() for k in keywords) for p in track.processors
        )
        if has_deesser:
            continue
        results.append(
            Recommendation(
                id=make_id("rec"),
                title=f"Vocal track '{track.name}' may benefit from a corrective chain",
                severity="suggestion",
                confidence=0.55,
                related_node_ids=[track.id],
                explanation=(
                    "The track reads as a vocal but its observed chain has no "
                    "de-esser-like processor; sibilance control is a common "
                    "corrective step on lead vocals."
                ),
                suggested_action="Consider a de-esser or dynamic EQ tuned to sibilance.",
                caveat=(
                    "The vocal may not need it, sibilance may be handled "
                    "upstream, or the role classification may be wrong — it is "
                    "a name-based heuristic."
                ),
            )
        )
    return results


def rule_dense_chain(session: CanonicalSession) -> list[Recommendation]:
    """Processor chains long enough to deserve a second look."""
    results = []
    for track in session.tracks:
        n = len([p for p in track.processors if p.chain == "main"])
        if n <= DENSE_CHAIN_THRESHOLD:
            continue
        results.append(
            Recommendation(
                id=make_id("rec"),
                title=f"Dense processor chain on '{track.name}'",
                severity="info",
                confidence=0.6,
                related_node_ids=[track.id],
                explanation=(
                    f"{n} processors in series exceed the typical "
                    f"{DENSE_CHAIN_THRESHOLD}-stage chain; gain staging and "
                    "phase behavior get harder to reason about as chains grow."
                ),
                suggested_action=(
                    "Audit the chain order and consider consolidating overlapping "
                    "processors."
                ),
                caveat="Long chains are sometimes exactly what the sound needs.",
            )
        )
    return results


def rule_level_imbalance(session: CanonicalSession) -> list[Recommendation]:
    """Very large fader spread across regular tracks."""
    volumes = [
        (t, t.volume_db) for t in _regular_tracks(session) if t.volume_db is not None
    ]
    if len(volumes) < 2:
        return []
    loudest = max(volumes, key=lambda pair: pair[1])
    quietest = min(volumes, key=lambda pair: pair[1])
    spread = loudest[1] - quietest[1]
    if spread <= LEVEL_IMBALANCE_DB:
        return []
    return [
        Recommendation(
            id=make_id("rec"),
            title="Large fader spread between tracks",
            severity="suggestion",
            confidence=0.5,
            related_node_ids=[loudest[0].id, quietest[0].id],
            explanation=(
                f"'{loudest[0].name}' sits {round(spread, 1)} dB above "
                f"'{quietest[0].name}'. Spreads past {LEVEL_IMBALANCE_DB} dB "
                "sometimes indicate gain staging done at the fader instead of "
                "at the clip/input stage."
            ),
            suggested_action="Check clip gain / input gain before mixing with faders.",
            caveat=(
                "Faders only tell part of the story: clip gain, processor "
                "makeup gain, and automation are not included."
            ),
        )
    ]


def rule_master_limiter_context(session: CanonicalSession) -> list[Recommendation]:
    """A limiter on the master chain without loudness measurement context."""
    masters = session.tracks_of_kind("master")
    if not masters:
        return []
    keywords = DEFAULT_KEYWORDS.limiter_keywords
    limiters = [
        p
        for p in masters[0].processors
        if any(k in p.name.lower() for k in keywords)
    ]
    if not limiters:
        return []
    has_loudness = any(
        d.available and d.integrated_loudness_lufs is not None
        for d in session.descriptors
    )
    if has_loudness:
        return []
    return [
        Recommendation(
            id=make_id("rec"),
            title="Master limiter without loudness context",
            severity="info",
            confidence=0.6,
            related_node_ids=[masters[0].id] + [p.id for p in limiters],
            explanation=(
                "The master chain ends in a limiter but no integrated-loudness "
                "measurement is attached to the session, so how hard it works "
                "is unknown."
            ),
            suggested_action=(
                "Attach a mixdown for descriptor extraction, or check integrated "
                "LUFS against your delivery target."
            ),
            caveat="A limiter set for safety margin only is perfectly reasonable.",
        )
    ]


CORE_RULES: list[Rule] = [
    Rule(
        rule_id="core.shared_ambience",
        fn=rule_shared_ambience,
        requires=["plugin_chain", "bus_routing"],
        description="Per-track ambience with no shared bus",
    ),
    Rule(
        rule_id="core.unused_returns",
        fn=rule_unused_returns,
        requires=["plugin_chain", "bus_routing"],
        description="Bus/return tracks receiving no sends",
    ),
    Rule(
        rule_id="core.vocal_corrective_chain",
        fn=rule_vocal_corrective_chain,
        requires=["plugin_chain"],
        description="Vocal tracks without corrective processing",
    ),
    Rule(
        rule_id="core.dense_chain",
        fn=rule_dense_chain,
        requires=["plugin_chain"],
        description="Unusually long processor chains",
    ),
    Rule(
        rule_id="core.level_imbalance",
        fn=rule_level_imbalance,
        requires=["mixer_state"],
        description="Very large fader spread",
    ),
    Rule(
        rule_id="core.master_limiter_context",
        fn=rule_master_limiter_context,
        requires=["plugin_chain"],
        description="Master limiter without loudness measurement",
    ),
]
