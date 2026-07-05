"""The Ableton dialect driver.

Loads Ableton-style session JSON (hand-authored sessions, the demo pair, and
Session State Exporter extension output) into the canonical schema, exposes
the ``.als`` surface inspector, and contributes the Ableton rule pack and
keyword vocabulary.

``load`` is deliberately strict about ``.als`` files: a Live Set is gzipped
proprietary XML that this product does not parse, so the driver refuses to
"load" one and directs callers to the ``als_surface`` inspector instead —
surface inspection is never passed off as session state.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ...core.driver import DriverInputs, Rule, SessionDriver, SurfaceInspector
from ...core.models import CanonicalSession
from . import keywords as kw
from .als_inspector import AlsInspector
from .demo import build_demo_session, build_demo_session_revision
from .mapper import to_canonical, to_native
from .native_models import ProjectState, validate_project_dict

GZIP_MAGIC = b"\x1f\x8b"

_CUBASE_MARKERS = ('"dialect": "cubase"', '"daw_dialect": "cubase')


class AbletonDriver(SessionDriver):
    dialect = "ableton"
    display_name = "Ableton Live"
    extensions = (".json", ".als")

    # -- detection ----------------------------------------------------------

    def sniff(self, filename: str, head: bytes) -> float:
        lower = filename.lower()
        if lower.endswith(".als"):
            # Inspector-only path: a real Live Set is gzipped XML.
            return 0.9 if head[:2] == GZIP_MAGIC else 0.5
        if lower.endswith(".json"):
            text = head.decode("utf-8", errors="ignore")
            if any(marker in text for marker in _CUBASE_MARKERS):
                return 0.0
            if '"schema_version"' in text and '"tracks"' in text:
                return 0.7
        return 0.0

    # -- loading ------------------------------------------------------------

    def load(self, inputs: DriverInputs) -> CanonicalSession:
        for file in inputs.files:
            if not file.name.lower().endswith(".json"):
                continue
            payload = json.loads(file.data.decode("utf-8"))
            project = validate_project_dict(payload)
            source_artifact = inputs.options.get("source_artifact", "session_json")
            session = to_canonical(project, source_artifact=source_artifact)
            session.source_file = file.name
            return session
        for file in inputs.files:
            if file.name.lower().endswith(".als"):
                raise ValueError(
                    f"{file.name!r} is an Ableton Live Set (.als), which this "
                    "driver does not parse into session state. Use the "
                    "'als_surface' inspector for a cautious surface report "
                    "instead."
                )
        raise ValueError(
            "AbletonDriver.load expects an Ableton-style session JSON file "
            "(.json) among the inputs."
        )

    # -- demo sessions --------------------------------------------------------

    def demo(self) -> CanonicalSession:
        return to_canonical(build_demo_session(), source_artifact="session_json")

    def demo_revision(self) -> Optional[CanonicalSession]:
        return to_canonical(
            build_demo_session_revision(), source_artifact="session_json"
        )

    # -- native view ----------------------------------------------------------

    def to_native(self, session: CanonicalSession) -> ProjectState:
        return to_native(session)

    # -- contributions ----------------------------------------------------------

    def rules(self) -> list[Rule]:
        from .rules import ABLETON_RULES

        return list(ABLETON_RULES)

    def keywords(self) -> dict[str, Any]:
        return {
            "role_keywords": kw.TRACK_ROLE_KEYWORDS,
            "family_keywords": kw.DEVICE_FAMILY_KEYWORDS,
            "ambience_keywords": kw.AMBIENCE_KEYWORDS,
            "limiter_keywords": kw.LIMITER_KEYWORDS,
            "deesser_keywords": kw.DEESSER_KEYWORDS,
            "classify_track_role": kw.classify_track_role,
            "classify_device_family": kw.classify_device_family,
        }

    def inspectors(self) -> list[SurfaceInspector]:
        return [AlsInspector()]
