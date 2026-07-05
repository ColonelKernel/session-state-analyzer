"""Structural diff between two canonical sessions.

Canonicalized from the Ableton prototype's session diff. Because it reads
only canonical fields, it also works *across dialects* (Ableton demo vs its
Cubase cousin, or two REAPER revisions).

Answers "what changed between versions?" at the level producers act on:
tracks, processor chains, routes, returns, tempo — plus graph-size deltas.
Tracks are matched by case-insensitive name (ids are not assumed stable
across versions; renames therefore appear as remove + add, which the
narrative states explicitly as a limitation).
"""

from __future__ import annotations

from collections import Counter

from .graph import build_session_graph
from .models import CanonicalSession, Track


def _processor_names(track: Track) -> Counter:
    return Counter(proc.name for proc in track.processors)


def _route_targets(track: Track, session: CanonicalSession) -> Counter:
    """Outgoing routes of a track, expressed as target track names."""
    names = {t.id: (t.name or t.id) for t in session.tracks}
    return Counter(
        names.get(route.target_track_id, route.target_name or route.target_track_id or "?")
        for route in session.routes
        if route.source_track_id == track.id
        and route.mute is not True
        and route.enabled is not False
    )


def _parameter_changes(owner_label: str, old_procs, new_procs) -> list[dict]:
    """Parameter value changes between processors matched by unique name.

    Only processors whose name appears exactly once on each side are compared
    — duplicated names give no reliable instance identity.
    """
    old_by_name = Counter(p.name for p in old_procs)
    new_by_name = Counter(p.name for p in new_procs)
    changes: list[dict] = []
    for name in sorted(set(old_by_name) & set(new_by_name)):
        if old_by_name[name] != 1 or new_by_name[name] != 1:
            continue
        old_proc = next(p for p in old_procs if p.name == name)
        new_proc = next(p for p in new_procs if p.name == name)
        old_params = {p.name: p for p in old_proc.parameters}
        new_params = {p.name: p for p in new_proc.parameters}
        for param_name in sorted(set(old_params) & set(new_params)):
            if old_params[param_name].value != new_params[param_name].value:
                changes.append(
                    {
                        "owner": owner_label,
                        "processor": name,
                        "parameter": param_name,
                        "base": old_params[param_name].value,
                        "revised": new_params[param_name].value,
                        "unit": new_params[param_name].unit,
                    }
                )
    return changes


def diff_sessions(base: CanonicalSession, revised: CanonicalSession) -> dict:
    """Compute a structural diff and a human-readable narrative."""
    narrative: list[str] = []

    tempo_change = None
    if base.tempo != revised.tempo:
        tempo_change = {"base": base.tempo, "revised": revised.tempo}
        narrative.append(f"Tempo changed from {base.tempo} to {revised.tempo} BPM.")

    def _regular(session: CanonicalSession) -> dict[str, Track]:
        return {
            (t.name or t.id).lower(): t
            for t in session.tracks
            if t.kind not in ("return", "master")
        }

    base_tracks = _regular(base)
    revised_tracks = _regular(revised)

    tracks_added = [revised_tracks[k].name for k in revised_tracks if k not in base_tracks]
    tracks_removed = [base_tracks[k].name for k in base_tracks if k not in revised_tracks]
    for name in tracks_added:
        narrative.append(f"Track added: '{name}'.")
    for name in tracks_removed:
        narrative.append(f"Track removed: '{name}'.")

    track_changes: list[dict] = []
    for key in sorted(set(base_tracks) & set(revised_tracks)):
        old, new = base_tracks[key], revised_tracks[key]
        processors_added = list((_processor_names(new) - _processor_names(old)).elements())
        processors_removed = list((_processor_names(old) - _processor_names(new)).elements())
        routes_added = list(
            (_route_targets(new, revised) - _route_targets(old, base)).elements()
        )
        routes_removed = list(
            (_route_targets(old, base) - _route_targets(new, revised)).elements()
        )
        volume_change = (
            {"base": old.volume_db, "revised": new.volume_db}
            if old.volume_db != new.volume_db
            else None
        )
        clip_count_change = (
            {"base": len(old.clips), "revised": len(new.clips)}
            if len(old.clips) != len(new.clips)
            else None
        )
        if not any(
            [processors_added, processors_removed, routes_added, routes_removed,
             volume_change, clip_count_change]
        ):
            continue
        track_changes.append(
            {
                "track": new.name,
                "processors_added": processors_added,
                "processors_removed": processors_removed,
                "routes_added": routes_added,
                "routes_removed": routes_removed,
                "volume_db_change": volume_change,
                "clip_count_change": clip_count_change,
            }
        )
        parts = []
        if processors_added:
            parts.append("added " + ", ".join(processors_added))
        if processors_removed:
            parts.append("removed " + ", ".join(processors_removed))
        if routes_added:
            parts.append("new send to " + ", ".join(routes_added))
        if routes_removed:
            parts.append("send removed to " + ", ".join(routes_removed))
        if volume_change:
            parts.append(
                f"volume {volume_change['base']} → {volume_change['revised']} dB"
            )
        if clip_count_change:
            parts.append(
                f"clips {clip_count_change['base']} → {clip_count_change['revised']}"
            )
        narrative.append(f"'{new.name}': " + "; ".join(parts) + ".")

    def _named_counter(session: CanonicalSession, kind: str) -> Counter:
        return Counter(t.name for t in session.tracks_of_kind(kind))

    returns_added = list(
        (_named_counter(revised, "return") - _named_counter(base, "return")).elements()
    )
    returns_removed = list(
        (_named_counter(base, "return") - _named_counter(revised, "return")).elements()
    )
    for name in returns_added:
        narrative.append(f"Return track added: '{name}'.")
    for name in returns_removed:
        narrative.append(f"Return track removed: '{name}'.")

    parameter_changes: list[dict] = []
    for key in sorted(set(base_tracks) & set(revised_tracks)):
        old, new = base_tracks[key], revised_tracks[key]
        parameter_changes.extend(
            _parameter_changes(new.name, old.processors, new.processors)
        )
    base_master = base.tracks_of_kind("master")
    revised_master = revised.tracks_of_kind("master")
    if base_master and revised_master:
        parameter_changes.extend(
            _parameter_changes(
                base_master[0].name or "Master",
                base_master[0].processors,
                revised_master[0].processors,
            )
        )
    for change in parameter_changes:
        unit = f" {change['unit']}" if change["unit"] else ""
        narrative.append(
            f"'{change['owner']}' · {change['processor']}: {change['parameter']} "
            f"{change['base']} → {change['revised']}{unit}."
        )

    def _master_processors(session: CanonicalSession) -> Counter:
        masters = session.tracks_of_kind("master")
        if not masters:
            return Counter()
        return Counter(p.name for p in masters[0].processors)

    master_added = list((_master_processors(revised) - _master_processors(base)).elements())
    master_removed = list((_master_processors(base) - _master_processors(revised)).elements())
    if master_added:
        narrative.append("Master chain added: " + ", ".join(master_added) + ".")
    if master_removed:
        narrative.append("Master chain removed: " + ", ".join(master_removed) + ".")

    base_graph = build_session_graph(base)
    revised_graph = build_session_graph(revised)
    stats = {
        "base_nodes": base_graph.number_of_nodes(),
        "revised_nodes": revised_graph.number_of_nodes(),
        "base_edges": base_graph.number_of_edges(),
        "revised_edges": revised_graph.number_of_edges(),
    }

    if not narrative:
        narrative.append("No structural differences detected.")

    caveats = [
        "Tracks are matched by name; a renamed track appears as a removal "
        "plus an addition.",
        "Parameter changes are diffed only for processors whose name is "
        "unique within their chain on both sides.",
    ]
    if base.dialect != revised.dialect:
        caveats.append(
            f"Cross-dialect diff ({base.dialect} vs {revised.dialect}): only "
            "canonical fields are compared; dialect-specific state in "
            "extras/native is not diffed."
        )

    return {
        "base_session": base.name,
        "revised_session": revised.name,
        "base_dialect": base.dialect,
        "revised_dialect": revised.dialect,
        "tempo_change": tempo_change,
        "tracks_added": tracks_added,
        "tracks_removed": tracks_removed,
        "track_changes": track_changes,
        "returns_added": returns_added,
        "returns_removed": returns_removed,
        "master_processors_added": master_added,
        "master_processors_removed": master_removed,
        "parameter_changes": parameter_changes,
        "graph_stats": stats,
        "narrative": narrative,
        "caveats": caveats,
    }
