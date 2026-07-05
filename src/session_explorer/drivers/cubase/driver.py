"""The Cubase dialect driver.

Loads Cubase-flavoured session JSON (the built-in demo and hand-authored
sessions) into the canonical schema and exposes the Track Archive surface
inspector. Two native model families back this dialect (see
:mod:`.mapper`): the rich provenance-carrying ``SessionState`` produced by the
DAWproject extractor, and the Ableton-family ``ProjectState`` used by the demo
and session JSON. Both round-trip through ``to_native``.

Like the Ableton driver's stance on ``.als``, this driver refuses to "load" a
Cubase Track Archive ``.xml`` as session state — an archive is a partial,
class-attribute-bearing surface, not a parsed session — and directs callers to
the ``track_archive_surface`` inspector instead.

Cubase ships no rule pack yet, so ``rules()`` is empty; the shared engine
still runs (with skip-notes for dialect-hidden fields) via the core defaults.
"""

from __future__ import annotations

import json
from typing import Any

from ...core.driver import DriverInputs, Rule, SessionDriver, SurfaceInspector
from ...core.models import CanonicalSession
from ..ableton.native_models import validate_project_dict
from .demo import build_cubase_demo_session
from .mapper import to_canonical, to_native
from .track_archive_inspector import TrackArchiveInspector

_CUBASE_MARKERS = ('"dialect": "cubase"', '"daw_dialect": "cubase')


class CubaseDriver(SessionDriver):
    dialect = "cubase"
    display_name = "Cubase"
    extensions = (".json", ".xml")

    # -- detection ----------------------------------------------------------

    def sniff(self, filename: str, head: bytes) -> float:
        lower = filename.lower()
        if lower.endswith(".xml"):
            # Inspector-only path: a Track Archive is surface XML, not session
            # state. A light positive score so the picker offers it.
            text = head.decode("utf-8", errors="ignore")
            if "tracklist" in text or "MAudioTrackEvent" in text or head.lstrip()[:1] == b"<":
                return 0.5
            return 0.3
        if lower.endswith(".json"):
            text = head.decode("utf-8", errors="ignore")
            if any(marker in text for marker in _CUBASE_MARKERS):
                return 0.85
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
            if file.name.lower().endswith(".xml"):
                raise ValueError(
                    f"{file.name!r} is a Cubase Track Archive (.xml), which "
                    "this driver does not parse into session state. Use the "
                    "'track_archive_surface' inspector for a cautious surface "
                    "report instead."
                )
        raise ValueError(
            "CubaseDriver.load expects a Cubase-style session JSON file "
            "(.json) among the inputs."
        )

    # -- demo sessions --------------------------------------------------------

    def demo(self) -> CanonicalSession:
        return to_canonical(
            build_cubase_demo_session(), source_artifact="session_json"
        )

    # -- native view ----------------------------------------------------------

    def to_native(self, session: CanonicalSession):
        return to_native(session)

    # -- contributions ----------------------------------------------------------

    def rules(self) -> list[Rule]:
        # No Cubase-specific rule pack yet; the core recommendation engine
        # still runs against canonical state.
        return []

    def keywords(self) -> dict[str, Any]:
        # The Cubase demo supplies device families explicitly; role/family
        # classification reuses the Ableton keyword vocabulary via the mapper.
        return {}

    def inspectors(self) -> list[SurfaceInspector]:
        return [TrackArchiveInspector()]
