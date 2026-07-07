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
