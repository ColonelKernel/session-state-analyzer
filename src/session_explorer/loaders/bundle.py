"""Loading adapter-exported snapshot bundles (the 5-file layout).

An adapter's ``export-canonical`` command writes a directory:

    adapter_descriptor.json    who captured this, and what they claim to see
    capabilities.json          the machine-readable capability manifest
    native.json                the verbatim DAW-native payload (may be large)
    canonical.snapshot.json    the flat v0.2 CanonicalDAWSnapshot  [required]
    validation.json            the adapter's own validation report at export

Only the canonical snapshot is required; a missing descriptor, manifest, or
shipped validation report degrades to a load warning rather than a failure —
a degraded-but-honest bundle is still a contract demonstration. The snapshot
is *always* re-validated on load (``validate_snapshot``): the analyzer trusts
the contract, not the exporter's homework.

``native.json`` is loaded lazily: it exists for provenance drill-down, not
for analysis, and can dwarf the snapshot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from canonical_snapshot import (
    AdapterDescriptor,
    CanonicalDAWSnapshot,
    CapabilityManifest,
    ValidationReport,
    validate_snapshot,
)

SNAPSHOT_FILE = "canonical.snapshot.json"
DESCRIPTOR_FILE = "adapter_descriptor.json"
CAPABILITIES_FILE = "capabilities.json"
NATIVE_FILE = "native.json"
VALIDATION_FILE = "validation.json"


@dataclass
class SnapshotBundle:
    """One loaded adapter bundle.

    ``validation`` is the analyzer's own load-time report (authoritative);
    ``shipped_validation`` is whatever the adapter wrote at export time, kept
    for comparison. ``native`` loads ``native.json`` on first access and
    returns ``None`` (with a recorded warning) when the file is absent.
    """

    dir: Path
    snapshot: CanonicalDAWSnapshot
    validation: ValidationReport
    descriptor: Optional[AdapterDescriptor] = None
    capabilities: Optional[CapabilityManifest] = None
    shipped_validation: Optional[dict[str, Any]] = None
    load_warnings: list[str] = field(default_factory=list)
    _native_cache: Optional[dict[str, Any]] = field(default=None, repr=False)
    _native_loaded: bool = field(default=False, repr=False)

    @property
    def native(self) -> Optional[dict[str, Any]]:
        """The verbatim native payload, loaded lazily; ``None`` when absent."""
        if not self._native_loaded:
            self._native_loaded = True
            path = self.dir / NATIVE_FILE
            if path.is_file():
                self._native_cache = json.loads(path.read_text(encoding="utf-8"))
            else:
                self.load_warnings.append(
                    f"{NATIVE_FILE} missing from bundle {self.dir}; native "
                    "drill-down unavailable."
                )
        return self._native_cache


def load_snapshot(path_to_json: Path | str) -> CanonicalDAWSnapshot:
    """Load and strictly parse one ``canonical.snapshot.json``.

    Raises :class:`~canonical_snapshot.IncompatibleSchemaError` on a schema
    major.minor mismatch and :class:`ValueError` when the payload fails the
    contract — a snapshot that does not validate is not silently usable.
    """
    path = Path(path_to_json)
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = validate_snapshot(payload)
    if report.errors:
        raise ValueError(
            f"{path} is not a valid v0.2 snapshot: " + "; ".join(report.errors[:5])
        )
    return CanonicalDAWSnapshot.model_validate(payload)


def load_bundle(path: Path | str) -> SnapshotBundle:
    """Load a 5-file bundle directory into a :class:`SnapshotBundle`.

    ``canonical.snapshot.json`` is required (raises ``FileNotFoundError``);
    the sidecar files are tolerated missing, with explicit load warnings.
    """
    bundle_dir = Path(path)
    snapshot_path = bundle_dir / SNAPSHOT_FILE
    if not snapshot_path.is_file():
        raise FileNotFoundError(
            f"Bundle {bundle_dir} has no {SNAPSHOT_FILE}; a bundle without a "
            "canonical snapshot is not a bundle."
        )

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    validation = validate_snapshot(payload)
    snapshot = CanonicalDAWSnapshot.model_validate(payload)

    load_warnings: list[str] = []

    descriptor: Optional[AdapterDescriptor] = None
    descriptor_path = bundle_dir / DESCRIPTOR_FILE
    if descriptor_path.is_file():
        descriptor = AdapterDescriptor.model_validate(
            json.loads(descriptor_path.read_text(encoding="utf-8"))
        )
    else:
        load_warnings.append(
            f"{DESCRIPTOR_FILE} missing: adapter identity is only what the "
            "snapshot's source block claims."
        )

    capabilities: Optional[CapabilityManifest] = None
    capabilities_path = bundle_dir / CAPABILITIES_FILE
    if capabilities_path.is_file():
        capabilities = CapabilityManifest.model_validate(
            json.loads(capabilities_path.read_text(encoding="utf-8"))
        )
    elif snapshot.capabilities is not None:
        capabilities = snapshot.capabilities
        load_warnings.append(
            f"{CAPABILITIES_FILE} missing: using the manifest embedded in the "
            "snapshot."
        )
    else:
        load_warnings.append(
            f"{CAPABILITIES_FILE} missing: capability-gated analyses will "
            "treat this adapter's support as unknown."
        )

    shipped_validation: Optional[dict[str, Any]] = None
    shipped_path = bundle_dir / VALIDATION_FILE
    if shipped_path.is_file():
        shipped_validation = json.loads(shipped_path.read_text(encoding="utf-8"))
    else:
        load_warnings.append(
            f"{VALIDATION_FILE} missing: the adapter shipped no validation "
            "report of its own."
        )

    return SnapshotBundle(
        dir=bundle_dir,
        snapshot=snapshot,
        validation=validation,
        descriptor=descriptor,
        capabilities=capabilities,
        shipped_validation=shipped_validation,
        load_warnings=load_warnings,
    )
