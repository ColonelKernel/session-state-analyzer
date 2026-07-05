# X04 — Effect return (cross-DAW flagship fixture)

## Semantic intent

**A vocal source sends signal to a shared reverb processing destination which
routes to the main output.**

That is the entire fixture definition. It is deliberately stated as a
*production strategy* — a semantic intent — and not as a sequence of button
presses in any DAW. Each DAW implements this one strategy with a different
native mechanism, and the point of X04 is that the analyzer can recognize the
strategy across all four mechanisms without erasing any of them.

## Entities (fixture roles)

| fixture_role | concept (registry) | meaning |
|---|---|---|
| `vocal_source` | `audio_source` | The vocal lane that generates/carries the dry signal |
| `reverb_return` | `effect_return` | The shared destination that wets the signal with reverb |
| `main_out` | `main_output` | The session's summing destination |

## Relationships (intent-level)

- `vocal_source` **sends_to** `reverb_return`
- `reverb_return` **processed_by** a reverb processor
- `reverb_return` **routes_to** `main_out`

## Native implementations (what each DAW calls this)

| DAW | mechanism | native noun | wire shape in the bundle |
|---|---|---|---|
| Ableton Live | Return Track + per-track send | `return_track` | `CHANNEL` (native_type `return`, role `effect_return`), incoming `CHANNEL_SENDS_TO` |
| Cubase | FX Channel + send | `fx_channel` | `CHANNEL` (native_type `return`, role `effect_return`), incoming `CHANNEL_SENDS_TO`, `CHANNEL_ROUTES_TO` master |
| REAPER | plain media track + receive (`AUXRECV`) | `media_track` | `TRACK`+`CHANNEL` pair (native_type `audio`), incoming `CHANNEL_SENDS_TO`, `main_send` native flag |
| Logic Pro | aux channel strip fed by a bus send — **never observed**; asserted via evidence + channel-strip notes | `aux_channel_strip` | `TRACK` (native_type `inferred`, `availability.channel = UNKNOWN`) + `ANNOTATION` entities carrying the send/bus/plug-in assertions |

Same strategy, four mechanisms, one analyzable representation. The registry
(`src/session_explorer/registry/`) records the `effect_return` equivalences as
**FUNCTIONAL**: the mechanisms achieve the same signal-flow result without
being the same feature.

## Captures: what these inputs are, honestly

The `inputs/` directories contain **hand-authored implementations of the
intent**, written in each DAW's real input format and run through the real
adapter pipelines (`export-canonical` in each explorer repo) to produce the
frozen `bundles/`. They are not screenshots of a running DAW:

- `reaper/x04.rpp` — hand-written REAPER 7 project text (COMMUNITY_DOCUMENTED
  format), parsed by the real `.rpp` parser.
- `ableton/x04_session.json` — hand-written ProjectState JSON in the shape the
  Live extension exports (exported here as `session_json` / MANUAL, not
  `extension_json`, because no extension produced it).
- `cubase/x04.dawproject` — hand-written DAWproject XML, zipped by
  `inputs/make_inputs.py`, parsed by the real DAWproject extractor.
- `logic/` — an evidence folder: two synthesized silent/tone stems (stdlib WAV
  writer, same approach as the Logic repo's demo), a session manifest, and a
  channel-strip notes CSV. This is the ANNOTATED pathway: sends, buses, and
  the Space Designer plug-in enter as user assertions, never as observed
  Logic state. The `Reverb Return` stem exists because printing a return is
  itself a real evidence-capture practice; its role is asserted by the
  manifest.

Each capture therefore carries an honest source stability (COMMUNITY_DOCUMENTED
/ MANUAL / HEURISTIC as its adapter reports), and the captures are
**replaceable**: when real DAW captures of the same intent exist, they drop
into `inputs/` and re-export into `bundles/` **without changing this fixture
definition**. The intent is the fixture; the captures are its current
witnesses.

## Regenerating

```
python fixtures/cross-daw/X04_effect_return/inputs/make_inputs.py   # wavs + dawproject zip
# then run each adapter repo's export-canonical over its input, --out bundles/<daw>
```
