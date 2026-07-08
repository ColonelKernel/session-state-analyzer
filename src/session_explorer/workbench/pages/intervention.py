"""State→audio intervention page (P9): one change, traced to the sound.

The flagship "primary PhD demo": a single controlled A/B — a vocal routed to
the master, and the *same* session with one post-fader send added to a shared
plate-reverb return — read as one chain of three panels:

1. **State change** — the ``StateDelta``: the single added ``CHANNEL_SENDS_TO``.
2. **Signal-flow explanation** — the ``SignalFlowChange`` sentence and the
   left-to-right path the new signal travels.
3. **Acoustic delta** — the before/after render descriptors, metric by metric.

Both the Expert tab (research vocabulary, inline) and the Guided tab
(plain-language, strings from :mod:`workbench.copy`) render the same three
beats over the same frozen experiment, so the two faces cannot drift. The page
loads the frozen fixture itself and is read-only.
"""

from __future__ import annotations

import html as _html

import streamlit as st

from session_explorer.interventions import (
    InterventionComparison,
    build_effect_send_experiment,
    build_parameter_experiment,
)
from session_explorer.workbench import copy as wcopy

# The shared signal-flow language colour (same teal as CHANNEL nodes).
_CHAIN_COLOR = "#2A9D8F"

# The two frozen experiments this page can dispatch. The label is the option the
# selector shows; the builder returns an ``InterventionComparison``. The
# effect-send case carries ``added_sends`` (a routing change); the delay-feedback
# case carries ``parameter_changes`` (a value change) — Panels 2 and 3 read the
# same ``signal_flow`` / ``acoustic_delta`` either way.
_EXPERIMENTS = {
    "Effect send": build_effect_send_experiment,
    "Delay feedback": build_parameter_experiment,
}


def _load(builder=build_effect_send_experiment) -> InterventionComparison | None:
    try:
        return builder()
    except Exception:  # noqa: BLE001 - a missing fixture must not kill the app
        return None


def _path_chain_html(path: list[str]) -> str:
    """A small left-to-right chain of pills: source → target → processor → out."""
    if not path:
        return ""
    pills = []
    for hop in path:
        pills.append(
            f"<span style='display:inline-block;padding:3px 10px;margin:2px;"
            f"border-radius:12px;background:{_CHAIN_COLOR};color:#ffffff;"
            f"font-size:0.85rem'>{hop}</span>"
        )
    arrow = "<span style='color:#9AA0A6;margin:0 2px'>→</span>"
    return "<div style='line-height:1.9'>" + arrow.join(pills) + "</div>"


def _static_table(rows: list[dict]) -> None:
    """Render a small fixed table as static HTML (immediate first-frame paint).

    ``st.dataframe`` draws to a lazily-painted canvas grid: for these tiny
    fixed tables it flashes an empty box for ~a second before the rows appear.
    These tables never scroll, sort, or resize, so a plain server-rendered
    ``<table>`` is both correct and instant. Cell text is escaped — entity
    names ultimately come from DAW session data.
    """
    if not rows:
        return
    cols = list(rows[0].keys())
    head = "".join(
        "<th style='text-align:left;padding:6px 10px;font-weight:600;"
        "font-size:0.78rem;opacity:0.7;"
        "border-bottom:1px solid rgba(128,128,128,0.35)'>"
        f"{_html.escape(str(c))}</th>"
        for c in cols
    )
    body = "".join(
        "<tr>"
        + "".join(
            "<td style='padding:6px 10px;font-size:0.85rem;"
            "border-bottom:1px solid rgba(128,128,128,0.15)'>"
            f"{_html.escape(str(row.get(c, '')))}</td>"
            for c in cols
        )
        + "</tr>"
        for row in rows
    )
    st.markdown(
        "<table style='width:100%;border-collapse:collapse;margin:2px 0 8px'>"
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>",
        unsafe_allow_html=True,
    )


def _fmt_value(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _param_change_rows(comparison: InterventionComparison) -> list[dict]:
    """One row per changed parameter: name, role, before→after value."""
    rows = []
    for pc in comparison.state_delta.parameter_changes:
        rows.append(
            {
                "parameter": pc.name,
                "role": pc.role or "—",
                "before": _fmt_value(pc.before_value),
                "after": _fmt_value(pc.after_value),
            }
        )
    return rows


def _metric_rows(comparison: InterventionComparison) -> list[dict]:
    rows = []
    for m in comparison.acoustic_delta.metrics:
        delta = "—" if m.delta is None else f"{m.delta:+g} {m.unit}".strip()
        direction = f" ({m.direction})" if m.direction else ""
        rows.append(
            {
                "metric": m.name,
                "before": "—" if m.before is None else f"{m.before:g}",
                "after": "—" if m.after is None else f"{m.after:g}",
                "change": delta + direction,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Expert
# ---------------------------------------------------------------------------


def _panel_state_change_expert(comparison: InterventionComparison) -> None:
    """Panel 1, experiment-agnostic: an added send OR a parameter change."""
    st.subheader("1 · State change")
    sd = comparison.state_delta

    if sd.parameter_changes and not sd.added_sends:
        # The delay-feedback case: a pure value change on an existing parameter.
        pc = sd.parameter_changes[0]
        role = f" ({pc.role})" if pc.role else ""
        st.markdown(
            f"**Parameter change{role}:** {pc.name} "
            f"{_fmt_value(pc.before_value)} → {_fmt_value(pc.after_value)}"
        )
        _static_table(_param_change_rows(comparison))
        st.caption(
            f"{len(sd.parameter_changes)} parameter(s) changed · no entities or "
            "relationships added or removed — the graph shape is identical, only "
            "one value differs."
        )
        return

    # The effect-send case: one added routing relationship (+ its return).
    if sd.added_sends:
        send = sd.added_sends[0]
        st.markdown(f"**+{len(sd.added_sends)} send:** {send.label}")
    st.caption(
        f"{len(sd.added_entities)} entities added · "
        f"{len(sd.added_relationships)} relationships added · "
        f"{len(sd.removed_entities)} entities removed · "
        f"{len(sd.removed_relationships)} relationships removed"
    )
    added_col, changed_col = st.columns(2)
    with added_col:
        st.markdown("**Added**")
        added = [
            {"kind": "entity", "type": r.type, "label": r.label}
            for r in sd.added_entities
        ] + [
            {"kind": "relationship", "type": r.type, "label": r.label}
            for r in sd.added_relationships
        ]
        _static_table(added)
    with changed_col:
        st.markdown("**Changed / removed**")
        other = [
            {"kind": "changed", "type": r.type, "label": r.label} for r in sd.changed
        ] + [
            {"kind": "removed", "type": r.type, "label": r.label}
            for r in sd.removed_entities + sd.removed_relationships
        ]
        if other:
            _static_table(other)
            st.caption(
                "Changed items are incidental (the vocal track's index shifts "
                "when the return channel is inserted; the project name/source "
                "path differ). Nothing was removed."
            )
        else:
            st.caption("Nothing changed or removed.")


def render_expert() -> None:
    """Expert 'State to audio' tab: the three panels in research vocabulary."""
    st.header("State → audio: one controlled intervention")

    choice = st.radio(
        "Experiment",
        list(_EXPERIMENTS),
        horizontal=True,
        key="intervention_experiment_expert",
    )
    comparison = _load(_EXPERIMENTS[choice])
    if comparison is None:
        st.info(
            f"The '{choice}' experiment fixture was not found under "
            "fixtures/experiments."
        )
        return

    iv = comparison.intervention
    st.markdown(f"**Semantic intervention.** {iv.description}")
    for daw, note in sorted(iv.native_implementations.items()):
        label = "Honesty note" if daw == "note" else f"{daw.capitalize()} native implementation"
        st.caption(f"{label}: {note}")

    st.divider()

    # -- Panel 1: state change ------------------------------------------------
    _panel_state_change_expert(comparison)

    st.divider()

    # -- Panel 2: signal-flow explanation ------------------------------------
    st.subheader("2 · Signal-flow explanation")
    st.markdown(comparison.signal_flow.summary)
    if comparison.signal_flow.path:
        st.markdown(
            _path_chain_html(comparison.signal_flow.path), unsafe_allow_html=True
        )

    st.divider()

    # -- Panel 3: acoustic delta ---------------------------------------------
    st.subheader("3 · Acoustic delta")
    ad = comparison.acoustic_delta
    if not ad.available or not ad.metrics:
        st.info(ad.unavailable_reason or "No acoustic delta available.")
    else:
        _static_table(_metric_rows(comparison))
        st.caption(ad.summary)
    st.caption(
        "Honest labelling: the inputs and their renders are SYNTHETIC "
        "fixtures — fixture-generated audio that genuinely reflects the change "
        "(the added send raises the level; the higher feedback lengthens the "
        "tail) — reproducible from the adapters."
    )


# ---------------------------------------------------------------------------
# Guided
# ---------------------------------------------------------------------------


def render_guided() -> None:
    """Guided tab: the same three beats in plain language (copy from copy.py).

    A selector chooses between the two frozen experiments — a reverb send
    (routing change) and a delay-feedback tweak (parameter change). Beat 1
    branches on which kind of change it is; beats 2 and 3 are identical either
    way, reading the same signal-flow sentence and acoustic table.
    """
    C = wcopy.INTERVENTION
    st.header(C["title"])
    st.markdown(C["intro"])

    choice = st.radio(
        C["experiment_label"],
        [C["experiment_effect_send"], C["experiment_parameter"]],
        horizontal=True,
        key="intervention_experiment_guided",
    )
    is_param = choice == C["experiment_parameter"]
    comparison = _load(
        build_parameter_experiment if is_param else build_effect_send_experiment
    )
    if comparison is None:
        st.info(C["missing"])
        return

    body_key = "param_what_we_did_body" if is_param else "what_we_did_body"
    st.markdown(f"**{C['what_we_did']}.** {C[body_key]}")
    st.divider()

    sd = comparison.state_delta
    flow = comparison.signal_flow
    path = flow.path

    # -- beat 1 ---------------------------------------------------------------
    st.subheader(C["state_header"])
    if is_param and sd.parameter_changes:
        pc = sd.parameter_changes[0]
        st.markdown(C["param_state_lead"])
        st.markdown(
            C["param_state_change"].format(
                knob=pc.role or pc.name,
                before=_fmt_value(pc.before_value),
                after=_fmt_value(pc.after_value),
                where=path[1] if len(path) >= 2 else pc.name,
            )
        )
        st.caption(C["param_state_note"])
    else:
        st.markdown(C["state_lead"])
        if sd.added_sends and len(path) >= 2:
            st.markdown(
                C["state_added_send"].format(source=path[0], target=path[1])
            )
            if len(path) >= 3:
                st.markdown(
                    C["state_added_return"].format(target=path[1], processor=path[2])
                )
        st.caption(C["state_nothing_removed"])

    st.divider()

    # -- beat 2 ---------------------------------------------------------------
    st.subheader(C["flow_header"])
    st.markdown(C["flow_lead"])
    if path:
        st.markdown(_path_chain_html(path), unsafe_allow_html=True)
    st.markdown(f"_{flow.summary}_")

    st.divider()

    # -- beat 3 ---------------------------------------------------------------
    st.subheader(C["audio_header"])
    st.markdown(C["param_audio_lead"] if is_param else C["audio_lead"])
    ad = comparison.acoustic_delta
    if not ad.available or not ad.metrics:
        st.info(C["audio_unavailable"])
    else:
        rows = []
        for m in ad.metrics:
            label = wcopy.INTERVENTION_METRICS.get(m.name, m.name)
            delta = "—" if m.delta is None else f"{m.delta:+g} {m.unit}".strip()
            if m.direction and m.direction != "unchanged":
                delta += f" — {m.direction}"
            rows.append(
                {
                    C["audio_col_metric"]: label,
                    C["audio_col_before"]: "—" if m.before is None else f"{m.before:g}",
                    C["audio_col_after"]: "—" if m.after is None else f"{m.after:g}",
                    C["audio_col_change"]: delta,
                }
            )
        _static_table(rows)
        st.markdown(f"_{ad.summary}_")
    st.info(C["param_audio_synthetic_note"] if is_param else C["audio_synthetic_note"])
