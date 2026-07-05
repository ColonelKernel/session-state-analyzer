"""Capability manifests: what an adapter can even *attempt* to observe.

Coverage in a snapshot says what one capture actually yielded; a capability
manifest says what the adapter's pathways support at all — per operation mode
(read / write / live observation / render), per domain, per field. The two
dimensions are kept separate on purpose: "we did not see automation in this
session" and "this adapter cannot see automation" are different facts.

Applicability is likewise separate from support: an Ableton scene grid is
NOT_APPLICABLE to REAPER, which is not the same as REAPER support being NONE.

``validation_status`` keeps manifests honest: a capability is CLAIMED until a
fixture test promotes it to TESTED.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import SourceStability


class _CapabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldCapability(_CapabilityModel):
    """What one adapter pathway can do for one canonical field."""

    applicability: Literal["APPLICABLE", "NOT_APPLICABLE", "UNKNOWN"] = "UNKNOWN"
    support: Literal["FULL", "PARTIAL", "NONE"] = "NONE"
    capture_method: Optional[str] = None
    source_stability: Optional[SourceStability] = None
    tested_daw_version: Optional[str] = None
    validation_status: Literal["TESTED", "UNTESTED", "CLAIMED"] = "CLAIMED"


class DomainCapability(_CapabilityModel):
    """Per-field capabilities for one session-state domain."""

    fields: dict[str, FieldCapability] = Field(default_factory=dict)


class CapabilitySection(_CapabilityModel):
    """One adapter's capabilities across the four operation modes.

    Each mode maps domain name → :class:`DomainCapability`. Read, write, live
    observation, and render are SEPARATE: being able to parse a value from a
    project file implies nothing about being able to write it back.
    """

    read: dict[str, DomainCapability] = Field(default_factory=dict)
    write: dict[str, DomainCapability] = Field(default_factory=dict)
    live_observation: dict[str, DomainCapability] = Field(default_factory=dict)
    render: dict[str, DomainCapability] = Field(default_factory=dict)


class CapabilityManifest(CapabilitySection):
    """A :class:`CapabilitySection` plus the identity of the adapter claiming it."""

    manifest_version: str = "0.2.0"
    daw: str = ""
    daw_version: Optional[str] = None
    adapter: str = ""
    adapter_version: str = ""
    notes: list[str] = Field(default_factory=list)


class AdapterDescriptor(_CapabilityModel):
    """The bundle-level identity card (``adapter_descriptor.json``).

    Human-scannable summaries per mode; the machine-readable detail lives in
    the capability manifest. ``known_limitations`` is the adapter's own honest
    statement of what it cannot see — product substance, not a footnote.
    """

    adapter_id: str
    daw: str
    capture_modes: list[str] = Field(default_factory=list)
    read: str = ""
    write: str = ""
    live_observation: str = ""
    render: str = ""
    known_limitations: list[str] = Field(default_factory=list)
