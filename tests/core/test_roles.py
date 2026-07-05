"""Tests for the core role/family heuristics.

Adapted from the Logic prototype's role-inference tests, the REAPER
prototype's classifier tests (real-session track names), and the Ableton
prototype's device-family coverage — plus core-only coverage for the
``knowledge_lookup`` hook and :class:`KeywordSets` overrides.
"""

from __future__ import annotations

import dataclasses

from session_explorer.core import roles
from session_explorer.core.roles import (
    DEFAULT_KEYWORDS,
    KeywordSets,
    classify_processor_family,
    classify_track_role,
    is_ambience_fx,
    is_vocal_name,
)


# ---------------------------------------------------------------------------
# Layer 1: filename-based role inference (Logic engine, benchmarked)
# ---------------------------------------------------------------------------


def test_vocal_filename_maps_to_vocal():
    result = roles.infer_role("05_Lead_Vocal_Bounce.wav")
    assert result.role == "Vocal"
    assert result.confidence > 0.5
    assert "vocal" in result.explanation.lower() or "vox" in result.explanation.lower()


def test_drums_filename_maps_to_drums():
    assert roles.infer_role("01_Drums.wav").role == "Drums"
    assert roles.infer_role("Kick.aiff").role == "Drums"


def test_bass_filename_maps_to_bass():
    assert roles.infer_role("02_Bass_DI.wav").role == "Bass"
    assert roles.infer_role("808 sub.wav").role == "Bass"


def test_mixdown_filename_maps_to_mixdown():
    assert roles.infer_role("Stereo_Mix_Bounce.wav").role == "Mixdown"
    assert roles.looks_like_mixdown("Full Mix Final.wav")


def test_reference_precedence():
    result = roles.infer_role("Vocal Reference.wav")
    assert result.role == "Reference"
    assert roles.looks_like_reference("target_ref.wav")


def test_unknown_filename_low_confidence():
    result = roles.infer_role("random_take_take3.wav")
    assert result.role == "Unknown"
    assert result.confidence <= 0.3


def test_keyword_inside_word_does_not_match():
    # 'ref' inside 'Refrain' must not make this a reference track.
    result = roles.infer_role("Refrain_Guitar.wav")
    assert result.role == "Guitar"
    assert not roles.looks_like_reference("Refrain_Guitar.wav")


def test_stereo_suffix_on_instrument_stem_is_not_mixdown():
    result = roles.infer_role("Acoustic_Guitar_Stereo.wav")
    assert result.role == "Guitar"
    assert not roles.looks_like_mixdown("Acoustic_Guitar_Stereo.wav")


def test_final_prefix_on_vocal_stem_is_not_mixdown():
    result = roles.infer_role("Final_Vocal_Comp.wav")
    assert result.role == "Vocal"
    assert not roles.looks_like_mixdown("Final_Vocal_Comp.wav")


def test_weak_keywords_still_mark_mixdown_without_instrument():
    assert roles.infer_role("Final_Mix.wav").role == "Mixdown"
    assert roles.looks_like_mixdown("Final_Mix.wav")
    assert roles.looks_like_mixdown("Bounce.wav")


def test_camelcase_names_classify():
    assert roles.infer_role("FinalMix.wav").role == "Mixdown"
    assert roles.infer_role("StereoMix.wav").role == "Mixdown"
    assert roles.infer_role("PreMaster_v2.wav").role == "Mixdown"
    assert roles.infer_role("DrumBus.wav").role == "Drums"
    assert roles.infer_role("LeadVocal.wav").role == "Vocal"


def test_plural_keyword_tolerance():
    assert roles.infer_role("06_Backing_Vocals_Bounce.wav").role == "Vocal"


def test_logic_stock_instrument_names_ground_roles():
    # Logic names tracks after the chosen patch/instrument, so exported stems
    # routinely carry stock instrument names.
    result = roles.infer_role("Ultrabeat_Bounce.wav")
    assert result.role == "Drums"
    assert not roles.looks_like_mixdown("Ultrabeat_Bounce.wav")
    assert roles.infer_role("Alchemy.wav").role == "Keys"
    result = roles.infer_role("Sculpture.wav")
    assert result.role == "Keys"
    assert "stock instrument" in result.explanation


def test_ambiguous_instruments_abstain():
    # Sampler/Quick Sampler can host anything: abstention is correct.
    assert roles.infer_role("Quick Sampler.wav").role == "Unknown"
    assert roles.infer_role("Sampler.wav").role == "Unknown"


def test_longer_abstaining_name_shadows_contained_instrument():
    # "Sample Alchemy" (abstain) contains "Alchemy" (Keys): the longest match
    # must win or the abstention policy is bypassed.
    assert roles.infer_role("Sample Alchemy.wav").role == "Unknown"


def test_keywords_take_precedence_over_instrument_names():
    # An explicit role keyword OUTSIDE the instrument name disambiguates.
    result = roles.infer_role("Alchemy Bass.wav")
    assert result.role == "Bass"
    assert result.confidence == 0.75
    assert "keyword" in result.explanation


def test_stock_instrument_name_credited_over_contained_keyword():
    # A documented stock instrument name whose own tokens contain a role
    # keyword (e.g. "Studio Horns" contains "horn") must be credited to the
    # catalog — 0.80 with a named explanation — not shadowed at 0.75 by the
    # bare keyword.
    for name, role in [("Studio Horns", "Brass"), ("Studio Strings", "Strings"),
                       ("Studio Bass", "Bass"), ("Studio Piano", "Keys")]:
        result = roles.infer_role(f"{name}.wav")
        assert result.role == role, name
        assert result.confidence == 0.8, name
        assert f"stock instrument name '{name}'" in result.explanation, name


def test_role_inference_result_expressible_as_provenance():
    result = roles.infer_role("05_Lead_Vocal_Bounce.wav")
    prov = result.to_provenance(source_artifact="exported_audio")
    assert prov.observability == "inferred"
    assert prov.confidence == result.confidence
    assert prov.explanation == result.explanation
    assert prov.source_artifact == "exported_audio"


# ---------------------------------------------------------------------------
# Layer 2: generic processor-family classification
# ---------------------------------------------------------------------------


def test_fx_metering_family():
    assert classify_processor_family("JS: analysis/loudness_meter") == "Metering"
    assert classify_processor_family("Frequency Analyzer") == "Metering"
    assert classify_processor_family("SPAN Spectrum Analyzer") == "Metering"


def test_fx_eq_keyword_matches_tokens_not_substrings():
    # "eq" inside "frequency" must not classify as EQ...
    assert classify_processor_family("Frequency Shifter Thing") != "EQ"
    # ...but a real bare "EQ" token still does, and common names stay stable.
    assert classify_processor_family("SSL EQ") == "EQ"
    assert classify_processor_family("VST3: Pro-Q 3 (FabFilter)") == "EQ"


def test_ableton_stock_devices_classify():
    assert classify_processor_family("EQ Eight") == "EQ"
    assert classify_processor_family("Glue Compressor") == "Dynamics"
    assert classify_processor_family("Hybrid Reverb") == "Ambience"
    assert classify_processor_family("Saturator") == "Saturation"
    assert classify_processor_family("Auto Pan") == "Modulation"
    assert classify_processor_family("Auto-Tune Pro") == "Pitch"
    assert classify_processor_family("Wavetable") == "Instrument"
    assert classify_processor_family("Arpeggiator") == "MIDI Effect"
    assert classify_processor_family("Utility") == "Utility"


def test_unrecognised_names_stay_unknown():
    # REVerence (Cubase's convolution reverb) shares no keyword — without a
    # dialect knowledge table it must abstain rather than guess.
    assert classify_processor_family("REVerence") == "Unknown"
    assert classify_processor_family(None) == "Unknown"
    assert classify_processor_family("") == "Unknown"


# ---------------------------------------------------------------------------
# Layer 2: generic track-role classification
# ---------------------------------------------------------------------------


def test_real_session_names_classify():
    # Names observed in a real REAPER 7 multitrack session.
    assert classify_track_role("Nord L_Ride_5_Step") == "Keys"
    assert classify_track_role("OH L_Ride_5_Step") == "Drums"
    assert classify_track_role("OH R_Ride_5_Step") == "Drums"
    assert classify_track_role("Snare Top_Ride_5_Step") == "Drums"
    assert classify_track_role("Cristian Bass") == "Bass"


def test_short_tokens_do_not_match_inside_words():
    # "oh" must only match as a whole token, never inside a word.
    assert classify_track_role("John Vocal") == "Vocal"
    assert classify_track_role("Johnny Lead") == "Unknown"


def test_section_labels_do_not_leak_into_roles():
    # Take/section suffixes like "_Ride_5_Step" appear on EVERY track of a real
    # session; "ride" therefore must not be a drums keyword.
    assert classify_track_role("Spirals of Doubt_v6 Guitar_Ride_5_Step") == "Guitar"
    assert classify_track_role("Zach Bass_Ride_5_Step") == "Bass"


def test_precedence_is_preserved():
    # Earlier families win: a mellotron guitar patch reads as Guitar (Guitar is
    # checked before Keys), and a vocal bus reads as Bus (bus-first ordering).
    assert classify_track_role("Mellotron Guitar") == "Guitar"
    assert classify_track_role("Mellotron") == "Keys"
    assert classify_track_role("Vocal Bus") == "Bus"


def test_ableton_role_vocabulary_kept_in_union():
    assert classify_track_role("Beat 1") == "Drums"
    assert classify_track_role("Master") == "Master"
    assert classify_track_role(None) == "Unknown"


# ---------------------------------------------------------------------------
# Helper predicates
# ---------------------------------------------------------------------------


def test_is_ambience_fx():
    assert is_ambience_fx("ChromaVerb")
    assert is_ambience_fx("Tape Delay")
    assert not is_ambience_fx("Compressor")
    assert not is_ambience_fx(None)


def test_is_vocal_name():
    assert is_vocal_name("Lead Vox")
    assert is_vocal_name("BGV Stack")
    assert not is_vocal_name("Guitar DI")
    assert not is_vocal_name(None)


# ---------------------------------------------------------------------------
# knowledge_lookup hook (driver-supplied authoritative tables)
# ---------------------------------------------------------------------------


def test_knowledge_lookup_is_consulted_first():
    # ReaEQ carries no core keyword — only a dialect knowledge table (e.g. the
    # REAPER driver's guide-derived stock-FX table) can identify it.
    def lookup(name: str):
        return "EQ" if "reaeq" in name.lower() else None

    assert classify_processor_family("VST: ReaEQ (Cockos)") == "Unknown"
    assert classify_processor_family("VST: ReaEQ (Cockos)", knowledge_lookup=lookup) == "EQ"


def test_knowledge_lookup_wins_over_keywords():
    # The authoritative table overrides what keywords would have said.
    assert classify_processor_family("Compressor") == "Dynamics"
    assert (
        classify_processor_family("Compressor", knowledge_lookup=lambda n: "Utility")
        == "Utility"
    )


def test_knowledge_lookup_none_falls_through_to_keywords():
    assert (
        classify_processor_family("Glue Compressor", knowledge_lookup=lambda n: None)
        == "Dynamics"
    )


def test_knowledge_lookup_feeds_is_ambience_fx():
    # "Seventh Heaven" (a convolution reverb) carries no ambience keyword —
    # only the knowledge table can mark it.
    lookup = lambda n: "Ambience" if n == "Seventh Heaven" else None  # noqa: E731
    assert not is_ambience_fx("Seventh Heaven")
    assert is_ambience_fx("Seventh Heaven", knowledge_lookup=lookup)


# ---------------------------------------------------------------------------
# KeywordSets overrides (drivers ship their own vocabulary)
# ---------------------------------------------------------------------------


def test_keyword_sets_override_roles():
    custom = dataclasses.replace(
        DEFAULT_KEYWORDS,
        role_keywords=[("Stems", ["stem"]), ("Vocal", ["vocal"])],
        role_token_keywords=[],
    )
    assert classify_track_role("Vocal Stem Print", custom) == "Stems"
    # The default vocabulary no longer applies under the override...
    assert classify_track_role("Kick", custom) == "Unknown"
    # ...and the module default is untouched.
    assert classify_track_role("Kick") == "Drums"


def test_keyword_sets_override_families():
    custom = dataclasses.replace(
        DEFAULT_KEYWORDS,
        family_keywords=[("Spatial", ["reverb", "delay"])],
        family_token_keywords=[],
    )
    assert classify_processor_family("Valhalla Reverb", custom) == "Spatial"
    assert classify_processor_family("SSL EQ", custom) == "Unknown"  # token table replaced
    assert classify_processor_family("SSL EQ") == "EQ"


def test_default_keyword_sets_carry_rule_vocabularies():
    # Recommendation rules read these lists off the KeywordSets they get.
    assert "maximizer" in DEFAULT_KEYWORDS.limiter_keywords
    assert "sibilance" in DEFAULT_KEYWORDS.deesser_keywords
    assert "reverb" in DEFAULT_KEYWORDS.ambience_keywords


def test_keyword_sets_instances_do_not_share_state():
    a = KeywordSets()
    a.role_keywords.append(("Zither", ["zither"]))
    assert ("Zither", ["zither"]) not in KeywordSets().role_keywords
    assert classify_track_role("Zither") == "Unknown"
