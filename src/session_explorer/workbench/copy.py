"""Every plain-language string in the Guided mode, in one place.

Guided mode is the story-first, jargon-free face of the workbench. All of its
wording lives here so copy edits never touch rendering code; Expert mode keeps
its research vocabulary inside the page modules. Rendering code formats these
templates but never invents sentences of its own.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# General chrome: mode switch, sidebar, tabs
# ---------------------------------------------------------------------------

COPY: dict[str, str] = {
    # -- mode switch / sidebar ----------------------------------------------
    "mode_label": "Mode",
    "mode_guided": "Guided",
    "mode_expert": "Expert",
    "mode_help": (
        "Guided explains everything in plain language; Expert is the "
        "research workbench."
    ),
    "expert_switch_hint": "Switch to Guided for plain-language explanations.",
    "guided_tagline": "A plain-language tour of what this tool can see.",
    "glossary_title": "What do these words mean?",
    # -- tab labels -----------------------------------------------------------
    "tab_overview": "Overview",
    "tab_x04": "The same idea in four DAWs",
    "tab_atlas": "What each DAW lets us see",
    "tab_graph": "Explore the graph",
    "tab_intervention": "What one change does to the sound",
    "tab_grouping": "Groups & feedback",
    "tab_evolution": "How a song evolved",
    "tab_comparison": "How the DAWs compare",
    # -- overview -------------------------------------------------------------
    "overview_title": "What's inside a music session?",
    "overview_intro": (
        "This tool looks inside music-production sessions from four "
        "different DAWs (digital audio workstations — the programs producers "
        "make music in) and shows what can — and cannot — be known about "
        "them. Some DAWs let us read everything straight from the project "
        "file; others keep their files closed, so the picture has to be "
        "pieced together from exported audio and notes. The tool always "
        "tells you which is which."
    ),
    "load_examples": "Load all example sessions",
    "all_loaded": "All {n} example sessions are loaded.",
    "no_bundles": (
        "No sessions are loaded yet — press “Load all example "
        "sessions” on the Overview tab."
    ),
    "bar_question": "How much can we see?",
    "read_direct": "Read directly from the project file.",
    "read_reconstructed": (
        "Mostly reconstructed from exported audio and your notes — the DAW "
        "itself stays closed."
    ),
    "read_hidden": (
        "Read from the project file, but some parts exist that the DAW "
        "keeps locked away."
    ),
    "read_mixed": "Read from the session, with a few gaps.",
    "read_none": "Nothing measurable in this session yet.",
    # count units (pluralized by adding "s")
    "unit_track": "track",
    "unit_effect": "effect",
    "unit_clip": "clip",
    "unit_routing": "routing connection",
    # -- the X04 story ---------------------------------------------------------
    "x04_intro": (
        "Producers in every DAW do the same thing: send a vocal to a shared "
        "reverb, so several tracks can use one effect. Each DAW builds it "
        "differently — different names, different mechanisms — but it is the "
        "same idea. Below, the exact same production move in four DAWs, and "
        "the tool's proof that it recognizes them as the same thing."
    ),
    "x04_calls_it": "What {daw} calls it:",
    "x04_in_session": "In this session it's named “{name}”.",
    "x04_matches_header": "Do they line up?",
    "x04_match_sentence": (
        "**{a_daw}**'s *{a_noun}* and **{b_daw}**'s *{b_noun}* do the same "
        "job — matched with {pct}% confidence because {r1}, and {r2}."
    ),
    "x04_match_conflicting": (
        "**{a_daw}** and **{b_daw}**: the tool found two equally good "
        "candidates and refuses to guess between them."
    ),
    "x04_match_unmatched": (
        "**{a_daw}** and **{b_daw}**: no confident match was found."
    ),
    "x04_table_expander": "See the full comparison table (all pairs, all reasons)",
    "x04_missing": (
        "The example comparison sessions were not found on disk, so "
        "this story can't be shown."
    ),
    # -- the friendly atlas ------------------------------------------------------
    "atlas_intro": (
        "Every row is one kind of information a session can hold; every "
        "column is a DAW. Each bar shows how much of that information we "
        "could actually get for the loaded session — and how we got it."
    ),
    "atlas_row_header": "What",
    "cell_direct": "{pct} read directly",
    "cell_recovered": "{pct} pieced together or noted by you",
    "cell_locked": "{pct} locked away",
    "cell_na": "nothing to look at yet",
    "cell_declared_only": "possible, but nothing in this session",
    "atlas_closer": "Look closer",
    "atlas_closer_caption": (
        "Pick a row and a DAW to see exactly which pieces of the session sit "
        "behind each bar."
    ),
    # -- the graph ----------------------------------------------------------------
    "graph_intro": (
        "Every session becomes a map: the shapes are tracks, effects, clips "
        "and audio files, and the lines show how they're connected.  \n"
        "Colours tell you *how we know* about each piece — read directly, "
        "our best guess, something you told us, or known to exist but hidden."
    ),
    "graph_layer_question": "What do you want to see?",
    "graph_legend_title": "What the colours mean:",
}

# ---------------------------------------------------------------------------
# The state->audio intervention story (P9), in plain language
# ---------------------------------------------------------------------------

INTERVENTION: dict[str, str] = {
    "title": "One change, and what it does to the sound",
    "intro": (
        "Here is a tiny controlled experiment. We took one vocal session and "
        "made a single change: we added a reverb send to the vocal — the same "
        "session, one knob different. Then we look at three things: what "
        "changed inside the session, why that makes the sound change, and how "
        "much it actually changed."
    ),
    "what_we_did": "What we changed",
    "what_we_did_body": (
        "We added a **reverb send** from the vocal so it also feeds a shared "
        "plate-reverb effect. Nothing else was touched."
    ),
    "missing": (
        "The experiment fixture wasn't found on disk, so this story can't be "
        "shown."
    ),
    # -- beat 1: the state change ------------------------------------------------
    "state_header": "1 · What changed in the session",
    "state_lead": (
        "Only one connection was added, and nothing was removed. That single "
        "new line is the whole change:"
    ),
    "state_added_send": "Added: a send from **{source}** to **{target}**.",
    "state_added_return": (
        "To receive it, a shared **{target}** effect return appears, carrying "
        "**{processor}**."
    ),
    "state_nothing_removed": "Nothing was removed — this is a pure addition.",
    # -- beat 2: the signal flow -------------------------------------------------
    "flow_header": "2 · Why the sound changes",
    "flow_lead": (
        "Follow the new path the vocal now travels. Every stop is read "
        "straight from the session, not guessed:"
    ),
    # -- beat 3: the acoustic delta ----------------------------------------------
    "audio_header": "3 · How much the sound changed",
    "audio_lead": (
        "We measured the two renders of this session — before and after the "
        "change. The numbers agree with the story: adding the reverb send "
        "makes the vocal louder and adds a wet tail."
    ),
    "audio_synthetic_note": (
        "Honest note: both the sessions and their audio are **synthetic "
        "fixtures** — the audio is generated, not printed from a human "
        "performance, but it genuinely reflects the routing change (adding the "
        "send really does raise the level and change the spectrum). The whole "
        "chain is reproducible from the Cubase adapter."
    ),
    "audio_col_metric": "Measurement",
    "audio_col_before": "Before",
    "audio_col_after": "After",
    "audio_col_change": "Change",
    "audio_unavailable": "The renders carry no acoustic descriptors, so no sound delta is available.",
    # -- experiment selector (which controlled change to show) -------------------
    "experiment_label": "Which experiment?",
    "experiment_effect_send": "Reverb send",
    "experiment_parameter": "Delay feedback",
    # -- the parameter-change (delay feedback) variant ---------------------------
    "param_what_we_did_body": (
        "We turned **one knob**: the delay's feedback, from 0.2 up to 0.7. "
        "Nothing else in the session was touched — same tracks, same effects, "
        "same routing."
    ),
    "param_state_lead": (
        "No connection was added or removed. The only difference is a single "
        "value inside one effect:"
    ),
    "param_state_change": (
        "Changed: the **{knob}** of the delay on **{where}** went from "
        "**{before}** to **{after}**."
    ),
    "param_state_note": (
        "The session's shape is identical before and after — only this one "
        "number differs."
    ),
    "param_audio_lead": (
        "We measured the two renders — before and after turning the knob. "
        "More feedback means the echoes repeat longer, so the tail builds up "
        "and the overall level rises."
    ),
    "param_audio_synthetic_note": (
        "Honest note: both sessions and their audio are **synthetic fixtures**. "
        "This parameter A/B is shown on the REAPER-style observable path, where "
        "the feedback knob is host-readable — in Cubase the same VST3 parameter "
        "would be **hidden** (stored as an opaque blob), so it is documented as a "
        "limitation, not worked around."
    ),
}

# Plain-language names for the acoustic metrics in the Guided audio table.
INTERVENTION_METRICS: dict[str, str] = {
    "rms_db": "Loudness (average level)",
    "peak_db": "Loudest peak",
    "spectral_centroid_hz": "Brightness",
    "lufs": "Perceived loudness (LUFS)",
}

# ---------------------------------------------------------------------------
# Friendly atlas row labels: canonical domain -> (label, subtitle)
# ---------------------------------------------------------------------------

ATLAS_ROWS: dict[str, tuple[str, str]] = {
    "Structure": ("Tracks & layout", "The tracks in the session and how they're arranged."),
    "Timeline": ("Timeline & clips", "The clips and regions placed along the timeline."),
    "Routing": ("Signal routing", "Where the audio travels: sends, buses, outputs."),
    "Processing": ("Effects & processing", "The effects and instruments on each track."),
    "Parameters": ("Knobs & settings", "The individual knob values inside effects."),
    "Automation": ("Automation moves", "Recorded knob movements over time."),
    "Modulation": ("Modulation", "LFOs and other movement applied to sounds."),
    "Musical Content": ("Notes & music", "The musical notes themselves (MIDI, scores)."),
    "Native Features": ("DAW-specific extras", "Features unique to this DAW, kept alongside."),
    "Audio Outcome": ("The final sound", "The audio the session actually produces."),
}

# ---------------------------------------------------------------------------
# Guided graph layer labels -> canonical layer ids
# ---------------------------------------------------------------------------

GRAPH_LAYERS: dict[str, str] = {
    "How things are organized": "organizational",
    "How audio flows": "signal_flow",
    "Effect chains": "processing",
    "Automation & control": "automation",
    "Session versions": "variant",
    "Everything": "all",
}

# ---------------------------------------------------------------------------
# Plain words for the observability classes (legend + bars)
# ---------------------------------------------------------------------------

OBS_PLAIN: dict[str, str] = {
    "observed": "read directly",
    "inferred": "our best guess (with confidence)",
    "annotation": "you told us",
    "hidden": "exists but the DAW won't show it",
    "absent": "nothing to look at yet",
}

# ---------------------------------------------------------------------------
# Glossary: term -> plain definition
# ---------------------------------------------------------------------------

GLOSSARY: dict[str, str] = {
    "Evidence": (
        "How a fact got here: read directly from the DAW (observed), worked "
        "out from other clues (inferred), written down by you (annotated), "
        "or known to exist but unreadable (hidden)."
    ),
    "Availability": (
        "An honest note attached to anything the tool could not get — "
        "instead of leaving a silent blank, it says why the value is missing."
    ),
    "Canonical vs native": (
        "Each DAW has its own words (Return Track, FX Channel, Aux). "
        "“Native” is the DAW's own wording; “canonical” is "
        "the shared, DAW-neutral description everything is translated into "
        "so sessions can be compared."
    ),
    "Provenance": (
        "The paper trail. Every value on screen links back to a record of "
        "where it came from, how it was captured, and how confident we are."
    ),
    "Feedback loop": (
        "When audio is sent along a path that eventually returns to where it "
        "started — a ring. Producers build these on purpose (and sometimes by "
        "accident). The tool flags them as a finding, never an error."
    ),
    "Group / VCA": (
        "A DAW “group” often fuses several ideas at once: which tracks live "
        "inside it (containment), whose audio is mixed together (summing), and "
        "what it controls the level of without carrying audio (a VCA). The tool "
        "splits the one native “group” back into these distinct parts."
    ),
    "Automation": (
        "A recorded movement of a knob over time — for example a volume fade. "
        "It has a shape (a curve) and a range of values, and it drives one "
        "parameter, effect, or channel setting."
    ),
    "Variant": (
        "One saved version of a song among several — v5, v6, v7 of the same "
        "piece. Variants form a family with a lineage (which came from which), "
        "and the tool can diff two adjacent versions."
    ),
    "Compatibility level": (
        "A rung on a seven-step ladder describing what a session's data can "
        "demonstrate — from “it opens” up to “a before/after change was "
        "measured”. It is a *profile*, not a score: a DAW that reaches a higher "
        "rung is not “better”, it just happens to show a different thing."
    ),
    "Provenance completeness": (
        "How much of the paper trail actually connects. Every value points back "
        "to a record of where it came from; completeness is the share of those "
        "links that resolve — a full trail means nothing is left unexplained."
    ),
}

# ---------------------------------------------------------------------------
# Routing depth: grouping decomposition + processing chains (Expert + Guided)
# ---------------------------------------------------------------------------

DEPTH: dict[str, str] = {
    # -- expert framing ----------------------------------------------------------
    "header": "Routing depth",
    "intro": (
        "Two lenses on what a native “group” and an insert chain really are. "
        "One DAW “group” fuses concepts the canonical model keeps apart; the "
        "processing view shows the ordered device chain on a single channel."
    ),
    "grouping_header": "Group decomposition — one native noun, several concepts",
    "grouping_caption": (
        "Pick a group entity. The four columns are the distinct canonical "
        "edges it fans out into: what it Contains, what Sums into it, what it "
        "Controls (VCA), and what Routes in from outside."
    ),
    "grouping_no_groups": (
        "This session has no group-like entities (folder, submix bus, or VCA)."
    ),
    "grouping_multi": (
        "Finding: this single native “group” is **{n} distinct canonical "
        "concepts** at once — the model keeps them apart so the fusion is "
        "visible in the data, not hidden in a noun."
    ),
    "grouping_single": (
        "This “group” resolves to a single concept — it is only what its one "
        "populated column says it is."
    ),
    "col_contains": "Contains",
    "col_sums": "Sums in",
    "col_controls": "Controls (VCA)",
    "col_routes_in": "Routes in",
    "processing_header": "Processing chain — one channel, its devices in order",
    "processing_caption": (
        "Pick a channel to see the insert/device chain it hosts and the order "
        "the signal passes through them (PRECEDES)."
    ),
    "no_channels": "This session has no channels to inspect.",
    # -- guided framing ----------------------------------------------------------
    "guided_header": "Groups & feedback",
    "guided_intro": (
        "A “group” in a DAW usually does several jobs at once. This tool pulls "
        "the one name apart into the separate things it actually does — which "
        "tracks are inside it, whose sound it mixes together, and what it just "
        "controls the volume of."
    ),
    "guided_pick_group": "Pick a group to take apart:",
    "guided_col_contains": "Holds these tracks",
    "guided_col_sums": "Mixes these together",
    "guided_col_controls": "Controls the level of",
    "guided_col_routes_in": "Receives audio from",
    "guided_multi": (
        "See? This one “group” is really **{n} different jobs** rolled into a "
        "single name."
    ),
    "guided_feedback_header": "Feedback loops",
    "guided_feedback_body": (
        "Sometimes audio is sent along a path that loops back to where it "
        "began — a feedback ring. When a loaded session has one, the tool marks "
        "it in red on the “Explore the graph” tab and calls it out as a "
        "finding (never an error)."
    ),
}

# ---------------------------------------------------------------------------
# Parameter influence: base + automation + modulation + effective (Expert)
# ---------------------------------------------------------------------------

PARAM_INFLUENCE: dict[str, str] = {
    "header": "Parameter influence",
    "intro": (
        "For one parameter (or one automated channel field), what actually "
        "sets its value: its base setting, any automation lane that moves it "
        "over time, any modulation that shapes it, and the honest effective "
        "reading. We never fabricate a value at a single instant — automation "
        "is reported as a range, not a point."
    ),
    "pick_target": "Parameter / automated field",
    "no_targets": (
        "This session exposes no parameters or automated fields to inspect."
    ),
    "base_header": "Base value",
    "base_none": "No static base value is stored for this target.",
    "automation_header": "Automation",
    "automation_none": "No automation lane drives this target.",
    "modulation_header": "Modulation",
    "modulation_none": "No modulation source shapes this target.",
    "effective_header": "Effective value",
}

# ---------------------------------------------------------------------------
# Session evolution: variant lineage + adjacent diffs (Expert + Guided)
# ---------------------------------------------------------------------------

EVOLUTION: dict[str, str] = {
    "header": "Session evolution",
    "intro": (
        "How one song changed across saved versions — the variant family, its "
        "lineage graph, and what changed between each adjacent pair (v1→v2, "
        "v2→v3)."
    ),
    "guided_header": "How a song evolved",
    "guided_intro": (
        "The same song, saved as several versions over time. Below is the "
        "family tree of versions and, for each step, exactly what changed."
    ),
    "pick_family": "Version family",
    "lineage_header": "Lineage",
    "diff_header": "What changed, step by step",
    "unavailable": (
        "Session-evolution data isn't available yet: the variants module or the "
        "variant fixtures (fixtures/variants) are not present. This exhibit "
        "will light up once the same-song variant bundles land."
    ),
}

# ---------------------------------------------------------------------------
# Plain-language rewrites for the alignment engine's reasons.
# Matched by prefix; "{detail}" receives whatever follows the first colon.
# Unmatched reasons fall back to the engine's own (already readable) words.
# ---------------------------------------------------------------------------

REASON_PLAIN: tuple[tuple[str, str], ...] = (
    ("both are effect_return implementations", "both play the role of a shared effect return"),
    ("name tokens overlap", "their names share “{detail}”"),
    ("both expose a mixer channel", "both show up as a mixer channel"),
    ("both receive ≥1 send", "both receive audio sent from other tracks"),
    ("both send to ≥1 destination", "both send audio onward"),
    ("both route to the main output", "both feed the main output"),
    ("both carry a reverb-family processor", "both carry a reverb effect"),
    ("same canonical entity type", "both are the same kind of building block"),
    ("linked media assets share content hash", "they point at identical audio files"),
)

# ---------------------------------------------------------------------------
# Adapter comparison dashboard (Phase 3): profiles side by side (Expert + Guided)
# ---------------------------------------------------------------------------

# Plain one-line glosses for the seven compatibility-ladder rungs, used as the
# Guided ladder-chip tooltips. Keyed by rung index (0..6).
LADDER_RUNGS_PLAIN: dict[int, str] = {
    0: "It opens and checks out",
    1: "It has tracks and a mixer",
    2: "Its signal routing is wired up",
    3: "It has a timeline or automation",
    4: "It has scenes, movement, or versions",
    5: "Its sound was actually rendered",
    6: "A before/after change was measured",
}

COMPARISON: dict[str, str] = {
    # -- expert framing ----------------------------------------------------------
    "header": "Adapter comparison",
    "intro": (
        "Every loaded DAW as one column, every row a measurable facet of what "
        "its capture demonstrates — schema conformance, coverage, the evidence "
        "mix, provenance, the compatibility ladder, declared capability, and "
        "cross-DAW alignment. Read across a row to see how four instruments "
        "differ; read down a column for one adapter's whole profile."
    ),
    "caption_not_ranking": (
        "Profiles, side by side — not a ranking. Different instruments see "
        "different things."
    ),
    "col_header": "Measure",
    "row_schema": "Schema valid",
    "row_schema_desc": "Re-validates against the v0.2 contract with zero errors.",
    "row_coverage": "Domain coverage",
    "row_coverage_desc": (
        "Share of applicable items recovered by any means (observed + inferred "
        "+ annotated), summed across all ten atlas domains."
    ),
    "row_evidence": "Evidence mix",
    "row_evidence_desc": (
        "The whole-session epistemic mix — the same bar the atlas draws, "
        "summed over every domain."
    ),
    "evidence_legend": (
        "<span style='color:#2E86DE'>■</span> observed &nbsp;·&nbsp; "
        "<span style='color:#27AE60'>■</span> inferred &nbsp;·&nbsp; "
        "<span style='color:#F39C12'>■</span> annotated &nbsp;·&nbsp; "
        "<span style='color:#C0392B'>■</span> hidden &nbsp;·&nbsp; "
        "<span style='color:#7F8C8D'>■</span> unsupported / unknown"
    ),
    "row_provenance": "Provenance completeness",
    "row_provenance_desc": (
        "Share of every entity-field and relationship provenance reference that "
        "resolves into the deduplicated provenance store."
    ),
    "row_conformance": "Fixture conformance",
    "row_conformance_desc": (
        "Load-time validation errors / warnings, and whether the adapter's "
        "shipped validation report agrees with our own re-validation."
    ),
    "row_ladder": "Compatibility ladder",
    "row_ladder_desc": (
        "The L0..L6 reached set — a profile, not a rank. Real profiles are "
        "frequently non-contiguous."
    ),
    "ladder_legend": (
        "L0 loadable · L1 structural · L2 signal-flow · L3 temporal · "
        "L4 behavioral · L5 acoustic-outcome · L6 controlled-intervention. "
        "✓ reached · ~ reached (provisional) · · not reached."
    ),
    "row_capabilities": "Declared read capability",
    "row_capabilities_desc": (
        "What the adapter's capability manifest claims it can read — field "
        "count and support distribution (independent of any one capture)."
    ),
    "row_alignment": "Alignment confidence",
    "row_alignment_desc": (
        "Mean confidence of the X04 cross-DAW alignment over every pair this "
        "DAW participates in (the shared effect-return strategy)."
    ),
    "downloads_header": "Downloads",
    "downloads_caption": (
        "The measurable profile of the loaded bundles, as committed artifacts: "
        "the full metrics report and the compatibility-ladder document."
    ),
    "download_metrics": "Download metrics report (JSON)",
    "download_ladder": "Download compatibility ladder (Markdown)",
    # -- guided framing ----------------------------------------------------------
    "guided_header": "How the DAWs compare",
    "guided_intro": (
        "Four different DAWs, side by side. Each column is one DAW; each row "
        "asks one plain question about what we could learn from it. This is "
        "**not a scoreboard** — every DAW shows a different slice of a session, "
        "so “more” on one row never means “better”."
    ),
    "guided_col_header": "What we ask",
    "grow_schema": "Does it open cleanly?",
    "grow_schema_desc": "Whether the exported session passes every honesty check.",
    "grow_coverage": "How much could we see?",
    "grow_coverage_desc": "The share of the session we could recover, one way or another.",
    "grow_evidence": "How did we see it?",
    "grow_evidence_desc": "Read directly, pieced together, told to us, or locked away.",
    "grow_provenance": "Is the paper trail complete?",
    "grow_provenance_desc": "How much of every value links back to where it came from.",
    "grow_conformance": "Does the adapter's own check agree?",
    "grow_conformance_desc": "Any errors or warnings, and whether the DAW's exporter agrees with us.",
    "grow_ladder": "What can this session show?",
    "grow_ladder_desc": (
        "Seven things a session might demonstrate, from “it opens” to “a "
        "before/after change was measured”. Hover a chip to read it."
    ),
    "guided_ladder_legend": (
        "Each chip is one thing a session can show. ✓ yes · ~ partly (still "
        "growing) · · not this one. A fuller row isn't a better DAW — just a "
        "different one."
    ),
    "grow_capabilities": "What does it promise it can read?",
    "grow_capabilities_desc": "What the DAW's adapter says it can read, before any one session.",
    "grow_alignment": "Do its ideas line up with the others?",
    "grow_alignment_desc": "How confidently the same production move matches across DAWs.",
    "guided_downloads_header": "Take it with you",
    "guided_downloads_caption": (
        "Download the full comparison as data: the numbers report and the "
        "“what each session can show” ladder."
    ),
}
