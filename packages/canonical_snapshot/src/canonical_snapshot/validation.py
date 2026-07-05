"""Snapshot validation: loud, referential, and never silent.

``validate_snapshot`` performs a strict parse plus the referential checks the
pydantic layer cannot express: id uniqueness, endpoint existence, provenance
resolution, and the exactly-one-PROJECT invariant. Schema incompatibility
raises :class:`IncompatibleSchemaError` — the analyzer must never quietly
reinterpret a snapshot written against a different contract.

Errors are contract violations. Warnings are honesty prompts: an unknown
``rel_type`` (additive evolution at work), a TRACK with no channel and no
availability record saying why, a confidence value on an OBSERVED record
(confidence belongs only where it is meaningful).
"""

from __future__ import annotations

from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .enums import is_known_rel_type
from .models import SCHEMA_VERSION, CanonicalDAWSnapshot


class IncompatibleSchemaError(Exception):
    """The payload was written against an incompatible schema version."""


class ValidationReport(BaseModel):
    """The outcome of validating one snapshot (serialized as ``validation.json``)."""

    model_config = ConfigDict(extra="forbid")

    valid: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


def _major_minor(version: str) -> tuple[str, str]:
    parts = version.split(".")
    if len(parts) < 2:
        return version, ""
    return parts[0], parts[1]


def _check_schema_version(version: str) -> None:
    expected = _major_minor(SCHEMA_VERSION)
    got = _major_minor(str(version))
    if got != expected:
        raise IncompatibleSchemaError(
            f"Snapshot schema_version {version!r} is incompatible with this "
            f"contract ({SCHEMA_VERSION!r}): major.minor must match "
            f"{expected[0]}.{expected[1]}. Refusing to reinterpret a snapshot "
            "written against a different contract — re-export it with a "
            "compatible adapter or upgrade the canonical-snapshot package."
        )


def validate_snapshot(
    payload: Union[dict, CanonicalDAWSnapshot],
) -> ValidationReport:
    """Strictly parse and referentially check one snapshot.

    Accepts a raw JSON-decoded dict or an already-constructed
    :class:`CanonicalDAWSnapshot`. Raises :class:`IncompatibleSchemaError` on
    a schema major.minor mismatch (never silent); all other problems land in
    the returned :class:`ValidationReport`.
    """

    report = ValidationReport()

    # -- schema-version gate (raises; incompatibility is not a report line) --
    if isinstance(payload, CanonicalDAWSnapshot):
        _check_schema_version(payload.schema_version)
        snapshot = payload
    else:
        version = payload.get("schema_version", "")
        if not version:
            report.errors.append("schema_version is missing.")
            return report
        _check_schema_version(version)
        try:
            snapshot = CanonicalDAWSnapshot.model_validate(payload)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(part) for part in err["loc"])
                report.errors.append(f"parse: {loc}: {err['msg']}")
            return report

    # -- referential checks ------------------------------------------------
    entity_ids: set[str] = set()
    for entity in snapshot.entities:
        if entity.id in entity_ids:
            report.errors.append(f"duplicate entity id: {entity.id!r}")
        entity_ids.add(entity.id)

    prov_ids = {record.id for record in snapshot.provenance}

    projects = snapshot.entities_of_type("PROJECT")
    if len(projects) != 1:
        report.errors.append(
            f"snapshot must contain exactly one PROJECT entity, found {len(projects)}."
        )
    elif snapshot.project != projects[0].id:
        report.errors.append(
            f"snapshot.project is {snapshot.project!r} but the PROJECT entity "
            f"id is {projects[0].id!r}."
        )

    for entity in snapshot.entities:
        for field, prov_ref in entity.prov.items():
            if prov_ref not in prov_ids:
                report.errors.append(
                    f"entity {entity.id!r}: prov[{field!r}] references unknown "
                    f"provenance record {prov_ref!r}."
                )

    rel_ids: set[str] = set()
    for rel in snapshot.relationships:
        if rel.id in rel_ids:
            report.errors.append(f"duplicate relationship id: {rel.id!r}")
        rel_ids.add(rel.id)
        if rel.source not in entity_ids:
            report.errors.append(
                f"relationship {rel.id!r} ({rel.rel_type}): source "
                f"{rel.source!r} is not an entity in this snapshot."
            )
        if rel.target not in entity_ids:
            report.errors.append(
                f"relationship {rel.id!r} ({rel.rel_type}): target "
                f"{rel.target!r} is not an entity in this snapshot."
            )
        if rel.prov_ref is not None and rel.prov_ref not in prov_ids:
            report.errors.append(
                f"relationship {rel.id!r}: prov_ref {rel.prov_ref!r} does not "
                "resolve in snapshot.provenance."
            )
        if not is_known_rel_type(rel.rel_type):
            report.warnings.append(
                f"relationship {rel.id!r} uses rel_type {rel.rel_type!r}, "
                "which is not in the core registry (allowed — additive "
                "evolution — but worth knowing)."
            )

    # -- honesty warnings ----------------------------------------------------
    tracks_with_channel = {
        rel.source
        for rel in snapshot.relationships
        if rel.rel_type == "TRACK_USES_CHANNEL"
    }
    for track in snapshot.entities_of_type("TRACK"):
        if track.id in tracks_with_channel:
            continue
        if "channel" in track.availability:
            continue
        report.warnings.append(
            f"TRACK {track.id!r} has no TRACK_USES_CHANNEL relationship and no "
            "availability record for 'channel'. If the channel truly was not "
            "observable, say so: availability['channel'] = 'UNKNOWN' (or the "
            "applicable status)."
        )

    for record in snapshot.provenance:
        if record.evidence == "OBSERVED" and record.confidence is not None:
            report.warnings.append(
                f"provenance record {record.id!r} is OBSERVED but carries "
                f"confidence={record.confidence}. Confidence belongs only "
                "where it is meaningful (heuristics, annotations); a parsed "
                "value is not a calibrated estimate."
            )

    # -- stats ---------------------------------------------------------------
    by_type: dict[str, int] = {}
    for entity in snapshot.entities:
        by_type[entity.entity_type] = by_type.get(entity.entity_type, 0) + 1
    report.stats = {
        "entities": len(snapshot.entities),
        "entities_by_type": by_type,
        "relationships": len(snapshot.relationships),
        "provenance_records": len(snapshot.provenance),
        "warnings_in_snapshot": len(snapshot.warnings),
        "failures": len(snapshot.failures),
    }

    report.valid = not report.errors
    return report
