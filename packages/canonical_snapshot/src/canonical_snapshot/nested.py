"""The v0.1 nested canonical session — the adapters' internal intermediate.

Moved verbatim from the analyzer's ``session_explorer.core.models`` +
``session_explorer.core.provenance`` (see ``docs/PIVOT.md`` in the analyzer
repo). The four DAW adapters' mappers produce this nested ``CanonicalSession``
form; :func:`canonical_snapshot.from_nested.flatten_session` converts it to
the flat v0.2 :class:`~canonical_snapshot.models.CanonicalDAWSnapshot` wire
format. The nested form never appears on the wire.

Every dialect driver maps its native model into these canonical entities.
Losslessness is guaranteed by three layers:

1. **Canonical fields** — the unified vocabulary below, populated by every
   driver.
2. **The project-level ``native`` payload** — the complete ``model_dump()`` of
   the driver's verbatim native model. ``driver.to_native()`` re-validates it,
   so ``to_native(to_canonical(x)) == x`` is a testable property and nothing a
   DAW exposes can be dropped by accident.
3. **Entity-level ``extras`` + ``raw_source``** — structured DAW-specific
   values (a REAPER track's ``pan_law``, an Ableton clip's ``warp_enabled``)
   surfaced in the *unified* view without switching to native mode, plus the
   untouched raw source material each prototype already preserved.

Time fields are unit-tagged and never coerced: Ableton/Cubase clips live in
beats (``start_time_beats``), REAPER media items in seconds
(``position_seconds``); a canonical :class:`Clip` carries whichever domain its
dialect observed.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field

CANONICAL_SCHEMA_VERSION = "1.0.0"

Severity = Literal["info", "suggestion", "warning"]

# str, not an enum: new dialects should not require a core schema change.
KNOWN_DIALECTS = ("ableton", "cubase", "reaper", "logic")

TrackKind = Literal["audio", "midi", "group", "return", "master", "aux", "inferred", "unknown"]


# ---------------------------------------------------------------------------
# Provenance (formerly session_explorer.core.provenance)
# ---------------------------------------------------------------------------
#
# Provenance: where a value came from and how much to trust it.
#
# Generalizes the Logic prototype's observability bookkeeping to every dialect.
# Each canonical entity carries a :class:`Provenance`; individual fields whose
# origin differs from the entity's (a heuristic ``role`` on an otherwise parsed
# track, say) get an entry in the entity's ``field_provenance``.

Observability = Literal["observed", "inferred", "annotation", "hidden", "derived"]

OBSERVABILITY_VALUES: tuple[str, ...] = (
    "observed",
    "inferred",
    "annotation",
    "hidden",
    "derived",
)


class Provenance(BaseModel):
    """How a value entered the canonical session.

    ``source_artifact`` names the evidence artifact type from the dialect's
    observation matrix (``"rpp_file"``, ``"extension_json"``, ``"exported_audio"``,
    ...). ``confidence`` is 1.0 for directly parsed values; heuristics report
    their own calibrated confidence and a human-readable ``explanation``.
    """

    observability: Observability = "observed"
    source_artifact: Optional[str] = None
    confidence: float = 1.0
    explanation: Optional[str] = None


OBSERVED = Provenance(observability="observed")


def inferred(
    explanation: Optional[str] = None,
    confidence: float = 0.5,
    source_artifact: Optional[str] = None,
) -> Provenance:
    """Convenience constructor for heuristic-derived values."""
    return Provenance(
        observability="inferred",
        confidence=confidence,
        explanation=explanation,
        source_artifact=source_artifact,
    )


def annotation(
    explanation: Optional[str] = None,
    confidence: float = 0.5,
    source_artifact: Optional[str] = None,
) -> Provenance:
    """Convenience constructor for user-asserted values (never DAW facts)."""
    return Provenance(
        observability="annotation",
        confidence=confidence,
        explanation=explanation,
        source_artifact=source_artifact,
    )


# ---------------------------------------------------------------------------
# Session models (formerly session_explorer.core.models)
# ---------------------------------------------------------------------------


class ProcessorParameter(BaseModel):
    """One host-visible parameter of a processor (VST3-aligned superset)."""

    id: str
    processor_id: str
    name: str
    value: Union[float, str, bool, None] = None
    normalized_value: Optional[float] = None
    unit: Optional[str] = None
    is_automated: Optional[bool] = None
    is_visible_to_host: Optional[bool] = None


class Processor(BaseModel):
    """A device / FX / plug-in in a track's chain.

    Union of Ableton's ``DeviceState`` and REAPER's ``FxState``; Logic
    channel-strip-note plugins arrive with ``provenance.observability ==
    "annotation"``.
    """

    id: str
    track_id: str
    index: int = 0
    name: str
    kind: Optional[str] = None  # native type: "VST3" / "JS" / "AU" / Live device type
    family: Optional[str] = None  # heuristic family: EQ / Dynamics / Ambience / ...
    enabled: Optional[bool] = None  # False when bypassed
    offline: Optional[bool] = None  # unloaded/offline; independent of ``enabled``
    chain: str = "main"  # "main" | "rec" (REAPER record-input/monitoring FX)
    preset: Optional[str] = None
    parameters: list[ProcessorParameter] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    field_provenance: dict[str, Provenance] = Field(default_factory=dict)
    extras: dict[str, Any] = Field(default_factory=dict)
    raw_source: Any = None


class Clip(BaseModel):
    """A clip / media item on a track.

    Beats-domain fields (Ableton/Cubase) and seconds-domain fields (REAPER)
    coexist, unit-tagged; drivers fill the domain they observed and never
    convert between them.
    """

    id: str
    track_id: str
    scene_id: Optional[str] = None
    name: Optional[str] = None
    clip_type: Literal["audio", "midi", "unknown"] = "unknown"
    # beats domain (Ableton session clips, Cubase arranger events)
    start_time_beats: Optional[float] = None
    length_beats: Optional[float] = None
    loop_start_beats: Optional[float] = None
    loop_end_beats: Optional[float] = None
    warp_enabled: Optional[bool] = None
    midi_note_count: Optional[int] = None
    # seconds domain (REAPER media items)
    position_seconds: Optional[float] = None
    length_seconds: Optional[float] = None
    audio_file: Optional[str] = None
    source_type: Optional[str] = None  # e.g. "WAVE", "MP3", "FLAC", "MIDI"
    provenance: Provenance = Field(default_factory=Provenance)
    extras: dict[str, Any] = Field(default_factory=dict)
    raw_source: Any = None


class Route(BaseModel):
    """A directed routing relationship (send / receive) between tracks.

    Adopts REAPER's superset shape — the richest routing model of the three
    prototypes. Ableton sends map into it with ``route_type="send"`` and the
    return track as target; unresolvable sources keep ``route_type=
    "unresolved"`` with a warning on the session.
    """

    id: str
    source_track_id: Optional[str] = None
    source_name: Optional[str] = None  # description of an unresolved source
    target_track_id: Optional[str] = None
    target_name: Optional[str] = None
    route_type: str = "send"  # "send" | "receive" | "unresolved"
    send_mode: Optional[int] = None  # REAPER SDK semantics; None elsewhere
    volume: Optional[float] = None  # linear send gain, 1.0 = +0dB
    volume_db: Optional[float] = None
    pan: Optional[float] = None  # -1..+1
    mute: Optional[bool] = None
    enabled: Optional[bool] = None  # Ableton send enabled flag
    # Channel-level routing detail (P6). Populated ONLY when the adapter
    # actually decoded per-channel wiring (e.g. REAPER AUXRECV channel
    # offsets); left ``None`` otherwise, which the flattener reads as
    # "stereo-implicit" — the honest default rather than an invented
    # channel spec.
    source_channels: Optional[list[int]] = None  # 0-based source channel indices
    target_channels: Optional[list[int]] = None  # 0-based target channel indices
    channel_count: Optional[int] = None  # how many channels this connection carries
    channel_layout: Optional[str] = None  # native layout label ("stereo" / "mono" / ...)
    provenance: Provenance = Field(default_factory=Provenance)
    extras: dict[str, Any] = Field(default_factory=dict)
    raw_source: Any = None


class Scene(BaseModel):
    """A session-grid scene (Ableton paradigm; absent in linear dialects)."""

    id: str
    index: int = 0
    name: Optional[str] = None
    tempo: Optional[float] = None
    provenance: Provenance = Field(default_factory=Provenance)
    extras: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Temporal control: automation lanes and modulation sources (P7)
# ---------------------------------------------------------------------------


class AutomationPoint(BaseModel):
    """One breakpoint on an automation lane.

    ``time`` is unit-tagged by ``time_domain`` (beats or seconds), never
    coerced — the same rule as :class:`Clip`. ``curve`` names the segment
    shape leaving this point ("linear", "hold", "bezier", ...).
    """

    time: float
    value: float
    time_domain: Literal["beats", "seconds"] = "beats"
    curve: str = "linear"


class Automation(BaseModel):
    """A recorded automation lane and what it controls.

    Targets exactly one of: a canonical PARAMETER entity
    (``target_parameter_id``), a processor field (``target_processor_id`` +
    ``parameter_name``), or a channel mixer field (``target_channel_field`` on
    ``target_track_id``). When none resolve, the lane still becomes an
    AUTOMATION entity whose target availability is a stated UNKNOWN.
    """

    id: str
    parameter_name: str
    target_track_id: Optional[str] = None
    target_processor_id: Optional[str] = None
    target_parameter_id: Optional[str] = None
    target_channel_field: Optional[str] = None
    unit: Optional[str] = None
    read_enabled: Optional[bool] = None
    write_enabled: Optional[bool] = None
    muted: Optional[bool] = None
    points: list[AutomationPoint] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    field_provenance: dict[str, Provenance] = Field(default_factory=dict)
    extras: dict[str, Any] = Field(default_factory=dict)
    raw_source: Any = None


class Modulation(BaseModel):
    """A modulation source (LFO, sidechain, envelope follower, ...) and target.

    Modulation is a live control relationship rather than a recorded lane; its
    targets follow the same resolution rules as :class:`Automation`.
    ``source_track_id`` names the audio source for a sidechain / audio-driven
    modulator. Modulation typically arrives ANNOTATED — no adapter observes it
    from a project file yet.
    """

    id: str
    source_type: Literal["lfo", "sidechain", "envelope_follower", "audio_driven", "macro"]
    parameter_name: Optional[str] = None
    target_track_id: Optional[str] = None
    target_processor_id: Optional[str] = None
    target_parameter_id: Optional[str] = None
    target_channel_field: Optional[str] = None
    source_track_id: Optional[str] = None
    depth: Optional[float] = None
    rate: Optional[float] = None
    unit: Optional[str] = None
    provenance: Provenance = Field(default_factory=Provenance)
    field_provenance: dict[str, Provenance] = Field(default_factory=dict)
    extras: dict[str, Any] = Field(default_factory=dict)
    raw_source: Any = None


class Track(BaseModel):
    """A track of any kind.

    Ableton return/master tracks fold in as ``kind="return"`` /
    ``kind="master"`` (the native view restores the split); Logic's
    evidence-reconstructed tracks arrive as ``kind="inferred"`` with inferred
    provenance — the UI must always badge them as such.
    """

    id: str
    index: int = 0
    name: Optional[str] = None
    kind: TrackKind = "audio"
    role: Optional[str] = None  # heuristic role: Vocal / Drums / Bass / ...
    color: Optional[str] = None  # "#rrggbb" when observable
    volume_db: Optional[float] = None
    pan: Optional[float] = None  # -1.0 (L) .. +1.0 (R)
    mute: Optional[bool] = None
    solo: Optional[bool] = None
    armed: Optional[bool] = None
    group_id: Optional[str] = None  # parent group/folder track id
    # Whether this group/folder track sums its children into a group channel
    # (P6 grouping honesty). ``None`` ⇒ decide from ``extras`` flags, else the
    # honest default that a group is a summing bus (see ``from_nested``).
    sums_children: Optional[bool] = None
    # VCA / edit-group control: ids of the tracks whose level/edit this track
    # controls (distinct from summing — a VCA scales level without carrying
    # audio). Emitted as CONTROLS edges, never SUMS_TO.
    controls: list[str] = Field(default_factory=list)
    clips: list[Clip] = Field(default_factory=list)
    processors: list[Processor] = Field(default_factory=list)
    descriptor_id: Optional[str] = None
    confidence: float = 1.0
    provenance: Provenance = Field(default_factory=Provenance)
    field_provenance: dict[str, Provenance] = Field(default_factory=dict)
    extras: dict[str, Any] = Field(default_factory=dict)
    raw_source: Any = None
    warnings: list[str] = Field(default_factory=list)


class HiddenStateMarker(BaseModel):
    """An explicit record of DAW-native state the evidence does not reveal.

    Core for every dialect: a parsed ``.rpp`` hides plug-in-internal state, an
    extension export hides automation — these gaps are product substance, not
    footnotes.
    """

    id: str
    target_id: str
    hidden_state_type: str
    description: str
    consequence: str
    possible_sources: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    """An explainable, graph-derived suggestion.

    Every recommendation carries an explicit ``caveat`` to preserve producer
    agency: these are heuristics meant to support reflection, not objective
    mixing rules. ``references`` cites literature grounding (e.g. the official
    REAPER guides) when a dialect rule pack provides it.
    """

    id: str
    title: str
    severity: Severity = "suggestion"
    confidence: float = 0.5
    related_node_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    suggested_action: str = ""
    caveat: str = "This is a graph-based heuristic, not an objective mixing rule."
    references: list[str] = Field(default_factory=list)


class AudioDescriptorSet(BaseModel):
    """Acoustic descriptors for one audio file — the union of all prototypes.

    Whole-file and silence-gated (``active_*``) level descriptors both exist
    because full-song-length stems are mostly silence outside their section;
    ``available``/``unavailable_reason`` keep the pipeline honest when audio
    or the audio backend is missing.
    """

    id: Optional[str] = None
    source_id: Optional[str] = None
    source_type: str = "file"  # "file" | "track" | "clip" | "mixdown" | "audio_evidence"
    node_id: Optional[str] = None  # graph node id of the associated audio_file
    file_path: Optional[str] = None
    file_name: str = ""
    available: bool = False
    unavailable_reason: Optional[str] = None

    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    rms_mean: Optional[float] = None
    rms_std: Optional[float] = None
    peak_amplitude: Optional[float] = None
    dynamic_range_db: Optional[float] = None  # approximation (peak vs noise floor)
    activity_ratio: Optional[float] = None
    active_rms_mean: Optional[float] = None
    active_duration_seconds: Optional[float] = None
    dynamic_range_active_db: Optional[float] = None
    stereo_width_ratio: Optional[float] = None
    spectral_centroid_mean: Optional[float] = None
    spectral_bandwidth_mean: Optional[float] = None
    spectral_rolloff_mean: Optional[float] = None
    zero_crossing_rate_mean: Optional[float] = None
    onset_strength_mean: Optional[float] = None
    estimated_tempo: Optional[float] = None
    integrated_loudness_lufs: Optional[float] = None  # via pyloudnorm if available
    # Extra descriptors computed only when Essentia is installed.
    spectral_complexity_mean: Optional[float] = None
    danceability: Optional[float] = None
    extra: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Evidence models (promoted to core from the Logic prototype: any dialect may
# attach exported stems, MIDI, or user annotations alongside its session)
# ---------------------------------------------------------------------------


class AudioEvidence(BaseModel):
    """A single exported audio file and what we can infer about it."""

    id: str
    file_name: str
    file_path: Optional[str] = None
    upload_name: Optional[str] = None
    inferred_track_name: Optional[str] = None
    inferred_role: Optional[str] = None
    role_explanation: Optional[str] = None
    is_mixdown: bool = False
    is_reference: bool = False
    track_index: Optional[int] = None
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    descriptor_id: Optional[str] = None
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class MidiEvidence(BaseModel):
    id: str
    file_name: str
    track_count: Optional[int] = None
    note_count: Optional[int] = None
    tempo_estimates: list[float] = Field(default_factory=list)
    time_signatures: list[str] = Field(default_factory=list)
    instrument_names: list[str] = Field(default_factory=list)
    track_names: list[str] = Field(default_factory=list)
    note_range: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class MusicXmlEvidence(BaseModel):
    id: str
    file_name: str
    part_count: Optional[int] = None
    measure_count: Optional[int] = None
    part_names: list[str] = Field(default_factory=list)
    detected_keys: list[str] = Field(default_factory=list)
    detected_time_signatures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ChannelStripNote(BaseModel):
    """A user-provided annotation about a track's channel strip.

    These are *assertions by the user*, not state extracted from the DAW. The
    graph and UI must always present them as such.
    """

    id: str
    track_name: str
    role: Optional[str] = None
    plugins: list[str] = Field(default_factory=list)
    sends: list[str] = Field(default_factory=list)
    bus: Optional[str] = None
    notes: Optional[str] = None
    confidence: float = 0.5


class ReferenceTrackEvidence(BaseModel):
    id: str
    file_name: str
    file_path: Optional[str] = None
    descriptor_id: Optional[str] = None
    notes: Optional[str] = None


class StemSumReconciliation(BaseModel):
    """Result of summing aligned stems and comparing against the mixdown.

    A low residual means the exported stems largely explain the mixdown; a
    high residual is signal evidence that bus/master processing (or missing
    stems, or misalignment) separates the two.
    """

    id: str
    mixdown_audio_id: str
    stem_audio_ids: list[str] = Field(default_factory=list)
    fitted_gain: Optional[float] = None
    residual_db: Optional[float] = None
    correlation: Optional[float] = None
    band_residuals_db: dict[str, float] = Field(default_factory=dict)
    interpretation: str = ""
    warnings: list[str] = Field(default_factory=list)


class ReferenceComparison(BaseModel):
    """Descriptive comparison between the mixdown and a reference track.

    Band deltas are level-independent (each file's per-band energy fraction).
    A reference is a point of comparison, never an objective target.
    """

    id: str
    mixdown_audio_id: str
    reference_id: str
    lufs_delta: Optional[float] = None
    crest_delta_db: Optional[float] = None
    stereo_width_delta: Optional[float] = None
    band_deltas_db: dict[str, float] = Field(default_factory=dict)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    """Evidence artifacts attached to a session (any dialect)."""

    audio_files: list[AudioEvidence] = Field(default_factory=list)
    midi_evidence: Optional[MidiEvidence] = None
    musicxml_evidence: Optional[MusicXmlEvidence] = None
    channel_strip_notes: list[ChannelStripNote] = Field(default_factory=list)
    reference_tracks: list[ReferenceTrackEvidence] = Field(default_factory=list)
    stem_sum_reconciliation: Optional[StemSumReconciliation] = None
    reference_comparisons: list[ReferenceComparison] = Field(default_factory=list)


class NativePayload(BaseModel):
    """The complete native model of the originating dialect — the losslessness guarantee."""

    dialect: str
    model_name: str  # native model class name, e.g. "ProjectState" / "SessionEvidence"
    model: dict[str, Any]


class CanonicalSession(BaseModel):
    """The unified session: canonical vocabulary + full native payload."""

    schema_version: str = CANONICAL_SCHEMA_VERSION
    dialect: str
    name: str = "Untitled Session"
    source_file: Optional[str] = None
    tempo: Optional[float] = None
    time_signature: Optional[str] = None  # "4/4"; native components kept in extras
    sample_rate: Optional[int] = None
    tracks: list[Track] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    # Temporal control + variants (P7/P8). All additive with empty/absent
    # defaults, so every existing mapper keeps producing identical output.
    automation: list[Automation] = Field(default_factory=list)
    modulation: list[Modulation] = Field(default_factory=list)
    variant_label: Optional[str] = None  # this session's variant name, if declared
    variant_family: Optional[str] = None  # the variant set it belongs to
    derived_from_snapshot_id: Optional[str] = None  # lineage (properties only here)
    evidence: Optional[EvidenceBundle] = None
    hidden_state_markers: list[HiddenStateMarker] = Field(default_factory=list)
    descriptors: list[AudioDescriptorSet] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    extras: dict[str, Any] = Field(default_factory=dict)
    native: Optional[NativePayload] = None

    # -- convenience accessors -------------------------------------------

    def all_clips(self) -> list[Clip]:
        return [clip for track in self.tracks for clip in track.clips]

    def all_processors(self) -> list[Processor]:
        return [proc for track in self.tracks for proc in track.processors]

    def track_by_id(self, track_id: str) -> Optional[Track]:
        for track in self.tracks:
            if track.id == track_id:
                return track
        return None

    def tracks_of_kind(self, kind: str) -> list[Track]:
        return [track for track in self.tracks if track.kind == kind]


def to_dict(obj: Any) -> Any:
    """Recursively convert models / containers into JSON-serialisable data."""
    if isinstance(obj, BaseModel):
        return to_dict(obj.model_dump())
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    return obj
