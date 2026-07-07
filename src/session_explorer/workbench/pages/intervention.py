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

import pandas as pd
import streamlit as st

from session_explorer.interventions import (
    InterventionComparison,
    build_effect_send_experiment,
)
from session_explorer.workbench import copy as wcopy

# The shared signal-flow language colour (same teal as CHANNEL nodes).
_CHAIN_COLOR = "#2A9D8F"


def _load() -> InterventionComparison | None:
    try:
        return build_effect_send_experiment()
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


def render_expert() -> None:
    """Expert 'State to audio' tab: the three panels in research vocabulary."""
    st.header("State → audio: one controlled intervention")
    comparison = _load()
    if comparison is None:
        st.info(
            "The effect-send experiment fixture was not found under "
            "fixtures/experiments/effect_send."
        )
        return

    iv = comparison.intervention
    st.markdown(f"**Semantic intervention.** {iv.description}")
    cubase_native = iv.native_implementations.get("cubase")
    if cubase_native:
        st.caption(f"Cubase native implementation: {cubase_native}")

    st.divider()

    # -- Panel 1: state change ------------------------------------------------
    st.subheader("1 · State change")
    sd = comparison.state_delta
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
        st.dataframe(pd.DataFrame(added), hide_index=True, width="stretch")
    with changed_col:
        st.markdown("**Changed / removed**")
        other = [
            {"kind": "changed", "type": r.type, "label": r.label} for r in sd.changed
        ] + [
            {"kind": "removed", "type": r.type, "label": r.label}
            for r in sd.removed_entities + sd.removed_relationships
        ]
        if other:
            st.dataframe(pd.DataFrame(other), hide_index=True, width="stretch")
            st.caption(
                "Changed items are incidental (the vocal track's index shifts "
                "when the return channel is inserted; the project name/source "
                "path differ). Nothing was removed."
            )
        else:
            st.caption("Nothing changed or removed.")

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
        st.dataframe(
            pd.DataFrame(_metric_rows(comparison)), hide_index=True, width="stretch"
        )
        st.caption(ad.summary)
    st.caption(
        "Honest labelling: the .dawproject inputs and their renders are "
        "SYNTHETIC fixtures — fixture-generated audio that genuinely reflects "
        "the routing change — reproducible via the Cubase adapter."
    )


# ---------------------------------------------------------------------------
# Guided
# ---------------------------------------------------------------------------


def render_guided() -> None:
    """Guided tab: the same three beats in plain language (copy from copy.py)."""
    C = wcopy.INTERVENTION
    st.header(C["title"])
    st.markdown(C["intro"])

    comparison = _load()
    if comparison is None:
        st.info(C["missing"])
        return

    st.markdown(f"**{C['what_we_did']}.** {C['what_we_did_body']}")
    st.divider()

    sd = comparison.state_delta
    flow = comparison.signal_flow
    path = flow.path

    # -- beat 1 ---------------------------------------------------------------
    st.subheader(C["state_header"])
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
    st.markdown(C["audio_lead"])
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
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown(f"_{ad.summary}_")
    st.info(C["audio_synthetic_note"])
