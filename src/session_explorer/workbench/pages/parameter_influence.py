"""Parameter influence page: what actually sets one parameter's value.

For a chosen PARAMETER — or an automated CHANNEL/processor field — this page
lays out the four things that determine its value, honestly:

- **base value** — the parameter's own static setting;
- **automation** — any ``CONTROLS``-linked AUTOMATION lane that moves it over
  time, summarised by its curve, point count and value range;
- **modulation** — any MODULATION source (LFO, sidechain, …) shaping it;
- **effective value** — the base plus an *explicit* "automated: range
  [min, max]" note. We never fabricate a value at a single instant t — an
  automated value is a range over time, and it is reported as one.

The page is read-only and reuses the shared static-table renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import streamlit as st

from canonical_snapshot import CanonicalDAWSnapshot
from session_explorer.loaders import SnapshotBundle, get_presentation
from session_explorer.workbench import copy as wcopy

from .intervention import _fmt_value, _static_table

_CONTROL_SOURCE_TYPES = ("AUTOMATION", "MODULATION")


# ---------------------------------------------------------------------------
# The influence model (local to this page, per the plan)
# ---------------------------------------------------------------------------


@dataclass
class _AutomationSource:
    name: str
    field: Optional[str] = None
    unit: Optional[str] = None
    curve: Optional[str] = None
    point_count: Optional[int] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    first_value: Optional[object] = None
    last_value: Optional[object] = None


@dataclass
class _ModulationSource:
    name: str
    source_type: Optional[str] = None
    depth: Optional[object] = None
    unit: Optional[str] = None
    rate: Optional[object] = None


@dataclass
class ParameterInfluence:
    """What sets one target's value: base + automation + modulation."""

    target_id: str
    target_label: str
    target_type: str
    base_value: Optional[object] = None
    base_unit: Optional[str] = None
    automation: List[_AutomationSource] = field(default_factory=list)
    modulation: List[_ModulationSource] = field(default_factory=list)

    def effective_text(self) -> str:
        """Base value + an explicit automated range — never a value at time t."""
        base = _fmt_value(self.base_value)
        base_part = base if self.base_value is not None else "(no static base)"
        if self.base_unit:
            base_part = f"{base_part} {self.base_unit}"
        if not self.automation:
            return base_part
        ranges = []
        for a in self.automation:
            lo = _fmt_value(a.value_min)
            hi = _fmt_value(a.value_max)
            unit = f" {a.unit}" if a.unit else ""
            ranges.append(f"[{lo}, {hi}]{unit}")
        return f"{base_part} · automated: range {' / '.join(ranges)}"


def _channel_field_value(
    entity, field_name: Optional[str]
) -> tuple[Optional[object], Optional[str]]:
    """A channel/processor field's static value, trying ``field`` then ``field_db``."""
    if field_name is None:
        return None, None
    props = entity.properties
    for key in (field_name, f"{field_name}_db"):
        if key in props:
            unit = "dB" if key.endswith("_db") else props.get("unit")
            return props[key], unit
    return None, None


def parameter_influence(
    snapshot: CanonicalDAWSnapshot, target_id: str
) -> ParameterInfluence:
    """Resolve everything that sets ``target_id``'s value: base + automation + modulation.

    ``target_id`` may name a PARAMETER entity (its ``value`` is the base) or a
    CHANNEL/PROCESSOR that an AUTOMATION lane drives via a ``CONTROLS`` edge
    carrying a ``field`` (the base is then that field's static reading). The
    CONTROLS / LINKED_WITH edges whose target is this entity are walked to their
    AUTOMATION and MODULATION sources.
    """
    entity = snapshot.entity_by_id(target_id)
    target_type = entity.entity_type if entity is not None else "UNKNOWN"
    target_label = (entity.name if entity and entity.name else target_id)

    # The field the automation controls (present on a channel-field CONTROLS
    # edge), used both to label and to find the base value for non-PARAMETERs.
    controlled_field: Optional[str] = None
    automation: List[_AutomationSource] = []
    modulation: List[_ModulationSource] = []

    for rel in snapshot.relationships_of_type("CONTROLS"):
        if rel.target != target_id:
            continue
        source = snapshot.entity_by_id(rel.source)
        if source is None:
            continue
        rel_field = rel.properties.get("field")
        if rel_field and controlled_field is None:
            controlled_field = rel_field
        if source.entity_type == "AUTOMATION":
            props = source.properties
            automation.append(
                _AutomationSource(
                    name=source.name or source.id,
                    field=rel_field,
                    unit=props.get("unit"),
                    curve=props.get("curve"),
                    point_count=props.get("point_count"),
                    value_min=props.get("value_min"),
                    value_max=props.get("value_max"),
                    first_value=props.get("first_value"),
                    last_value=props.get("last_value"),
                )
            )
        elif source.entity_type == "MODULATION":
            props = source.properties
            modulation.append(
                _ModulationSource(
                    name=source.name or source.id,
                    source_type=props.get("source_type"),
                    depth=props.get("depth"),
                    unit=props.get("unit"),
                    rate=props.get("rate"),
                )
            )

    # Sidechain / LFO modulation may ride a LINKED_WITH edge instead.
    for rel in snapshot.relationships_of_type("LINKED_WITH"):
        other_id = None
        if rel.target == target_id:
            other_id = rel.source
        elif rel.source == target_id:
            other_id = rel.target
        if other_id is None:
            continue
        source = snapshot.entity_by_id(other_id)
        if source is None or source.entity_type != "MODULATION":
            continue
        if any(m.name == (source.name or source.id) for m in modulation):
            continue
        props = source.properties
        modulation.append(
            _ModulationSource(
                name=source.name or source.id,
                source_type=props.get("source_type"),
                depth=props.get("depth"),
                unit=props.get("unit"),
                rate=props.get("rate"),
            )
        )

    # Base value + unit.
    base_value: Optional[object] = None
    base_unit: Optional[str] = None
    if entity is not None:
        if target_type == "PARAMETER":
            props = entity.properties
            base_value = props.get("value")
            if base_value is None:
                base_value = props.get("normalized_value")
            base_unit = props.get("unit") or None
        else:
            base_value, base_unit = _channel_field_value(entity, controlled_field)

    if controlled_field:
        target_label = f"{target_label} · {controlled_field}"

    return ParameterInfluence(
        target_id=target_id,
        target_label=target_label,
        target_type=target_type,
        base_value=base_value,
        base_unit=base_unit,
        automation=automation,
        modulation=modulation,
    )


# ---------------------------------------------------------------------------
# Candidate discovery + rendering
# ---------------------------------------------------------------------------


def _candidate_targets(snapshot: CanonicalDAWSnapshot) -> List[str]:
    """Every PARAMETER plus every AUTOMATION/MODULATION-controlled field.

    VCA/edit-group ``CONTROLS`` edges (a group controlling a channel's level)
    are deliberately excluded — that fusion belongs on the Routing-depth page,
    not here; this page is about what drives a *parameter's value*.
    """
    ids: List[str] = []
    seen: set[str] = set()

    def _push(entity_id: Optional[str]) -> None:
        if entity_id and entity_id not in seen:
            seen.add(entity_id)
            ids.append(entity_id)

    for entity in snapshot.entities:
        if entity.entity_type == "PARAMETER":
            _push(entity.id)
    for rel in snapshot.relationships_of_type("CONTROLS"):
        source = snapshot.entity_by_id(rel.source)
        if source is not None and source.entity_type in _CONTROL_SOURCE_TYPES:
            _push(rel.target)
    return ids


def _target_option_label(snapshot: CanonicalDAWSnapshot, target_id: str) -> str:
    entity = snapshot.entity_by_id(target_id)
    if entity is None:
        return target_id
    driven = any(
        rel.target == target_id
        and (
            (src := snapshot.entity_by_id(rel.source)) is not None
            and src.entity_type in _CONTROL_SOURCE_TYPES
        )
        for rel in snapshot.relationships_of_type("CONTROLS")
    )
    flag = " · automated" if driven else ""
    return f"{entity.entity_type} · {entity.name or target_id}{flag}"


def _bundle_label(bundle: SnapshotBundle) -> str:
    daw = bundle.snapshot.source.daw
    try:
        display = get_presentation(daw).display_name
    except Exception:  # noqa: BLE001 - unknown daw still gets a label
        display = daw
    return f"{display} ({bundle.dir.name})"


def _automation_rows(influence: ParameterInfluence) -> list[dict]:
    rows = []
    for a in influence.automation:
        rows.append(
            {
                "lane": a.name,
                "field": a.field or "—",
                "curve": a.curve or "—",
                "points": "—" if a.point_count is None else str(a.point_count),
                "range": f"[{_fmt_value(a.value_min)}, {_fmt_value(a.value_max)}]"
                + (f" {a.unit}" if a.unit else ""),
            }
        )
    return rows


def _modulation_rows(influence: ParameterInfluence) -> list[dict]:
    rows = []
    for m in influence.modulation:
        rows.append(
            {
                "source": m.name,
                "type": m.source_type or "—",
                "depth": "—"
                if m.depth is None
                else f"{_fmt_value(m.depth)}" + (f" {m.unit}" if m.unit else ""),
                "rate": "—" if m.rate is None else _fmt_value(m.rate),
            }
        )
    return rows


def render(bundles: List[SnapshotBundle]) -> None:
    """Expert 'Parameter influence' tab."""
    st.header(wcopy.PARAM_INFLUENCE["header"])
    st.caption(wcopy.PARAM_INFLUENCE["intro"])

    if not bundles:
        st.info("Select at least one bundle in the sidebar.")
        return

    bundle = (
        bundles[0]
        if len(bundles) == 1
        else st.selectbox(
            "Session", bundles, format_func=_bundle_label, key="param_influence_bundle"
        )
    )
    if bundle is None:
        return
    snapshot = bundle.snapshot

    targets = _candidate_targets(snapshot)
    if not targets:
        st.info(wcopy.PARAM_INFLUENCE["no_targets"])
        return

    target_id = st.selectbox(
        wcopy.PARAM_INFLUENCE["pick_target"],
        targets,
        format_func=lambda t: _target_option_label(snapshot, t),
        key="param_influence_target",
    )
    influence = parameter_influence(snapshot, target_id)

    base_col, eff_col = st.columns(2)
    with base_col:
        st.markdown(f"**{wcopy.PARAM_INFLUENCE['base_header']}**")
        if influence.base_value is None:
            st.caption(wcopy.PARAM_INFLUENCE["base_none"])
        else:
            unit = f" {influence.base_unit}" if influence.base_unit else ""
            st.markdown(f"`{_fmt_value(influence.base_value)}{unit}`")
    with eff_col:
        st.markdown(f"**{wcopy.PARAM_INFLUENCE['effective_header']}**")
        st.markdown(f"`{influence.effective_text()}`")

    st.divider()

    st.markdown(f"**{wcopy.PARAM_INFLUENCE['automation_header']}**")
    if influence.automation:
        _static_table(_automation_rows(influence))
    else:
        st.caption(wcopy.PARAM_INFLUENCE["automation_none"])

    st.markdown(f"**{wcopy.PARAM_INFLUENCE['modulation_header']}**")
    if influence.modulation:
        _static_table(_modulation_rows(influence))
    else:
        st.caption(wcopy.PARAM_INFLUENCE["modulation_none"])
