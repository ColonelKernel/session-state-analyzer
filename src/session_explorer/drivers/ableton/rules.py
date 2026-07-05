"""The Ableton rule pack: the prototype's heuristic rules as core Rules.

The rule *logic* is ported verbatim from the prototype's
``recommendations.py`` and still runs over the native
:class:`~.native_models.ProjectState`. Each core-facing wrapper takes a
:class:`~session_explorer.core.models.CanonicalSession`, reconstructs the
native model from the lossless payload (``mapper.to_native``), runs the
verbatim rule, and namespaces ``related_node_ids`` into canonical id space
(``ableton:track-6``) so they resolve against canonical graph nodes.
Namespacing uses the session's own dialect, so the pack also behaves when
run over the ProjectState-family Cubase demo (ids become ``cubase:...``).

Descriptor-backed rules read ``session.descriptors`` (the canonical
:class:`~session_explorer.core.models.AudioDescriptorSet` is a field superset
of the native one).

This is a heuristic prototype, not an AI mixer. Each rule emits a
Recommendation with an explanation, a suggested action, an explicit caveat,
and the node ids it reasons about — inspectable and contestable.
"""

from __future__ import annotations

from statistics import median
from typing import Optional, Sequence

from ...core.driver import Rule
from ...core.ids import namespaced
from ...core.models import CanonicalSession
from ...core.models import Recommendation as CoreRecommendation
from .keywords import AMBIENCE_KEYWORDS, DEESSER_KEYWORDS, LIMITER_KEYWORDS
from .mapper import to_native
from .native_models import (
    DeviceState,
    ProjectState,
    Recommendation,
    TrackState,
)

VOCAL_KEYWORDS = ["vocal", "vox", "voice", "lead vox", "bgv"]
CORRECTIVE_FAMILIES = {"EQ", "Dynamics"}
DENSE_CHAIN_THRESHOLD = 6
LEVEL_IMBALANCE_RATIO = 2.0  # ~6 dB above the median


def _is_ambience_device(device: DeviceState) -> bool:
    name = device.name.lower()
    return device.device_family == "Ambience" or any(
        kw in name for kw in AMBIENCE_KEYWORDS
    )


def _is_vocal_track(track: TrackState) -> bool:
    name = track.name.lower()
    return track.role == "Vocal" or any(kw in name for kw in VOCAL_KEYWORDS)


def _has_corrective_device(track: TrackState) -> bool:
    for device in track.devices:
        if device.device_family in CORRECTIVE_FAMILIES:
            return True
        if any(kw in device.name.lower() for kw in DEESSER_KEYWORDS):
            return True
    return False


# ---------------------------------------------------------------------------
# Rules (verbatim prototype logic over the native ProjectState)
# ---------------------------------------------------------------------------

def rule_shared_ambience_routing(project: ProjectState) -> Optional[Recommendation]:
    """Rule 1: several tracks carry ambience devices while return routing is idle."""
    ambience_tracks = [
        track for track in project.tracks
        if any(_is_ambience_device(d) for d in track.devices)
    ]
    if len(ambience_tracks) < 2:
        return None
    sends = project.all_sends()
    active_sends = [s for s in sends if s.enabled is not False]
    if project.return_tracks and len(active_sends) >= len(ambience_tracks):
        return None

    related = [t.id for t in ambience_tracks] + [rt.id for rt in project.return_tracks]
    related += [
        d.id for t in ambience_tracks for d in t.devices if _is_ambience_device(d)
    ]
    return Recommendation(
        id="rec-shared-ambience",
        title="Consider routing ambience through shared return tracks.",
        severity="suggestion",
        confidence=0.7,
        related_node_ids=related,
        explanation=(
            "The graph shows ambience-like devices on multiple tracks, but "
            "little or no send routing to a shared return. A shared ambience "
            "return can make space easier to control and compare."
        ),
        suggested_action=(
            "Consider moving or duplicating shared reverb/delay processing to "
            "a return track and using sends from the affected tracks."
        ),
        caveat="This is a workflow suggestion, not an objective mixing rule.",
    )


def rule_vocal_corrective_chain(project: ProjectState) -> list[Recommendation]:
    """Rule 2: vocal-like tracks without dynamics/EQ/de-essing stages."""
    recommendations = []
    for track in project.tracks:
        if not _is_vocal_track(track):
            continue
        if _has_corrective_device(track):
            continue
        recommendations.append(
            Recommendation(
                id=f"rec-vocal-chain-{track.id}",
                title="Vocal track may benefit from a clearer corrective chain.",
                severity="suggestion",
                confidence=0.6,
                related_node_ids=[track.id] + [d.id for d in track.devices],
                explanation=(
                    f"The track name '{track.name}' suggests a vocal role, but "
                    "the device chain does not show common corrective stages "
                    "such as EQ, compression, or de-essing. Consider adding or "
                    "documenting these if they are handled elsewhere."
                ),
                suggested_action=(
                    "A possible workflow check is to confirm whether corrective "
                    "processing happens on a group, a return, or upstream — and "
                    "if not, whether the raw sound is intentional."
                ),
                caveat=(
                    "Some genres intentionally use raw vocals, so this should "
                    "be treated as a candidate workflow check."
                ),
            )
        )
    return recommendations


def rule_unused_returns(project: ProjectState) -> Optional[Recommendation]:
    """Rule 3: return tracks exist but no sends target them."""
    if not project.return_tracks:
        return None
    targeted_returns = {
        s.target_return_id for s in project.all_sends() if s.enabled is not False
    }
    unused = [rt for rt in project.return_tracks if rt.id not in targeted_returns]
    if not unused:
        return None
    return Recommendation(
        id="rec-unused-returns",
        title="Return tracks are defined but not used.",
        severity="info",
        confidence=0.85,
        related_node_ids=[rt.id for rt in unused],
        explanation=(
            "The session includes return tracks, but the graph does not show "
            "active sends. This may indicate an unfinished routing structure "
            "or an opportunity to centralize ambience and parallel processing."
        ),
        suggested_action=(
            "Consider assigning sends from tracks that need shared ambience, "
            "or removing the unused returns to keep the session legible."
        ),
        caveat="This is a heuristic, not an objective rule.",
    )


def rule_dense_device_chain(project: ProjectState) -> list[Recommendation]:
    """Rule 4: tracks with more than six devices."""
    recommendations = []
    for track in project.tracks:
        if len(track.devices) <= DENSE_CHAIN_THRESHOLD:
            continue
        recommendations.append(
            Recommendation(
                id=f"rec-dense-chain-{track.id}",
                title="Dense device chain detected.",
                severity="info",
                confidence=0.75,
                related_node_ids=[track.id] + [d.id for d in track.devices],
                explanation=(
                    f"The track '{track.name}' has {len(track.devices)} devices. "
                    "Consider grouping creative vs corrective processing, "
                    "freezing/resampling, or documenting the intent of the chain."
                ),
                suggested_action=(
                    "This could help make the session easier to revise: annotate "
                    "or reorder the chain so corrective and creative stages are "
                    "distinguishable."
                ),
                caveat=(
                    "Long chains can be entirely intentional; this is a "
                    "legibility prompt, not a correctness claim."
                ),
            )
        )
    return recommendations


def rule_master_limiter_context(
    project: ProjectState, descriptors: Sequence
) -> Optional[Recommendation]:
    """Rule 5: master limiter present but no mixdown descriptors available."""
    if not project.master_track:
        return None
    limiters = [
        d for d in project.master_track.devices
        if any(kw in d.name.lower() for kw in LIMITER_KEYWORDS)
    ]
    if not limiters:
        return None
    has_mixdown_descriptors = any(d.source_type == "mixdown" for d in descriptors)
    if has_mixdown_descriptors:
        return None
    return Recommendation(
        id="rec-master-limiter-context",
        title="Master limiter detected without loudness context.",
        severity="info",
        confidence=0.8,
        related_node_ids=[project.master_track.id] + [d.id for d in limiters],
        explanation=(
            "The master contains a limiter-like device, but no rendered "
            "mixdown descriptors are available. A loudness or peak check could "
            "help interpret whether this is safety limiting, coloration, or "
            "final-level processing."
        ),
        suggested_action=(
            "Consider uploading a rendered mixdown so RMS, peak, and loudness "
            "descriptors can contextualize the master chain."
        ),
        caveat="This is a heuristic, not an objective rule.",
    )


def rule_level_imbalance(descriptors: Sequence) -> Optional[Recommendation]:
    """Rule 6: one file's RMS or peak is well above the session median."""
    measured = [d for d in descriptors if d.rms_mean is not None]
    if len(measured) < 2:
        return None
    rms_median = median(d.rms_mean for d in measured)
    if rms_median <= 0:
        return None
    outliers = [d for d in measured if d.rms_mean > rms_median * LEVEL_IMBALANCE_RATIO]
    if not outliers:
        return None
    names = ", ".join(d.file_path or d.source_id for d in outliers)
    return Recommendation(
        id="rec-level-imbalance",
        title="Potential level imbalance detected.",
        severity="suggestion",
        confidence=0.55,
        related_node_ids=[d.source_id for d in outliers],
        explanation=(
            "One associated audio file has substantially higher RMS or peak "
            f"level than the session median ({names}). This may be "
            "intentional, but it is worth checking in context."
        ),
        suggested_action=(
            "A possible workflow check is to audition the louder material "
            "against the rest of the session and confirm the balance is "
            "deliberate."
        ),
        caveat=(
            "Descriptor levels are computed per file, not in the mix context; "
            "this is a heuristic, not an objective rule."
        ),
    )


# ---------------------------------------------------------------------------
# Core-facing wrappers
# ---------------------------------------------------------------------------


def _to_core(rec: Recommendation, dialect: str) -> CoreRecommendation:
    return CoreRecommendation(
        id=rec.id,
        title=rec.title,
        severity=rec.severity,
        confidence=rec.confidence,
        related_node_ids=[
            namespaced(dialect, str(node_id))
            for node_id in rec.related_node_ids
            if node_id
        ],
        explanation=rec.explanation,
        suggested_action=rec.suggested_action,
        caveat=rec.caveat,
    )


def _wrap(recs, session: CanonicalSession) -> list[CoreRecommendation]:
    if recs is None:
        return []
    if isinstance(recs, Recommendation):
        recs = [recs]
    return [_to_core(rec, session.dialect) for rec in recs]


def shared_ambience_routing(session: CanonicalSession) -> list[CoreRecommendation]:
    return _wrap(rule_shared_ambience_routing(to_native(session)), session)


def vocal_corrective_chain(session: CanonicalSession) -> list[CoreRecommendation]:
    return _wrap(rule_vocal_corrective_chain(to_native(session)), session)


def unused_returns(session: CanonicalSession) -> list[CoreRecommendation]:
    return _wrap(rule_unused_returns(to_native(session)), session)


def dense_device_chain(session: CanonicalSession) -> list[CoreRecommendation]:
    return _wrap(rule_dense_device_chain(to_native(session)), session)


def master_limiter_context(session: CanonicalSession) -> list[CoreRecommendation]:
    return _wrap(
        rule_master_limiter_context(to_native(session), session.descriptors), session
    )


def level_imbalance(session: CanonicalSession) -> list[CoreRecommendation]:
    return _wrap(rule_level_imbalance(session.descriptors), session)


ABLETON_RULES: list[Rule] = [
    Rule(
        rule_id="ableton.shared_ambience",
        fn=shared_ambience_routing,
        requires=["plugin_chain", "sends", "bus_routing"],
        description="Per-track ambience devices while return routing is idle",
    ),
    Rule(
        rule_id="ableton.vocal_corrective_chain",
        fn=vocal_corrective_chain,
        requires=["track_name", "plugin_chain"],
        description="Vocal-like tracks without corrective stages",
    ),
    Rule(
        rule_id="ableton.unused_returns",
        fn=unused_returns,
        requires=["sends", "bus_routing"],
        description="Return tracks exist but no sends target them",
    ),
    Rule(
        rule_id="ableton.dense_device_chain",
        fn=dense_device_chain,
        requires=["plugin_chain"],
        description="Tracks with dense (>6) device chains",
    ),
    Rule(
        rule_id="ableton.master_limiter_context",
        fn=master_limiter_context,
        requires=["plugin_chain"],
        description="Master limiter without mixdown loudness context",
    ),
    Rule(
        rule_id="ableton.level_imbalance",
        fn=level_imbalance,
        requires=[],
        description="Descriptor RMS outliers vs the session median",
    ),
]


def generate_recommendations(session: CanonicalSession) -> list[CoreRecommendation]:
    """Run the full Ableton rule pack directly (no observability gating).

    Golden-parity helper mirroring the prototype's
    ``generate_recommendations``; production code should prefer
    ``session_explorer.core.recommend.run_rules(session, ABLETON_RULES)``.
    """

    recommendations: list[CoreRecommendation] = []
    for rule in ABLETON_RULES:
        recommendations.extend(rule.fn(session))
    return recommendations
