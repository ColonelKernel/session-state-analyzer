# Modulation — one ANNOTATED sidechain (atlas Modulation row exhibit)

## Semantic intent

**A kick channel sidechains (ducks) a bass channel's gain.**

That is the whole fixture. It exists for one reason: the Observability Atlas
carries a **Modulation** row that is `NOT_APPLICABLE` across every real adapter,
because none of the four DAWs' current pathways observe modulation. A row that
is empty everywhere is honest, but it needs to be *measurable somewhere* to
prove it is a real channel and not dead UI. This bundle is that "somewhere".

## Honesty note

This is a **synthetic** fixture — no DAW behind it. The modulation is a user
**assertion** about intent (`ANNOTATED`, confidence 0.6), never state read from
a project file. It is generated through the real `flatten_session` +
`validate_snapshot` pipeline (`inputs/make_inputs.py`), so it cannot drift.

## Wire shape

- a `MODULATION` entity (`source_type=sidechain`), its `"*"` provenance
  `ANNOTATED` — this is what flips the atlas Modulation cell from
  `NOT_APPLICABLE` to measured;
- a `CONTROLS` edge `modulation → bass channel` (`target=channel_field`,
  `field=gain`) — what the modulation drives;
- a `LINKED_WITH` edge `kick channel → modulation` (`kind=sidechain_source`) —
  the audio source that drives the sidechain.

No modulation *read-capability* is declared, so the atlas cell is measured
purely from the entity present in this capture, not from any adapter claim.

## Regenerating

```
python fixtures/modulation/inputs/make_inputs.py
```
