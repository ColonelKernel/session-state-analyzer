"""The REAPER dialect driver: ``.rpp`` files in, canonical sessions out."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from ...core.driver import DriverInputs, Rule, SessionDriver
from ...core.models import CanonicalSession
from .fx_knowledge import STOCK_FX, WORKFLOWS, StockFx, Workflow, lookup_stock_fx
from .keywords import REAPER_KEYWORDS
from .mapper import to_canonical, to_native
from .native_models import ProjectState
from .rpp_parser import parse_rpp
from .rules import REAPER_RULES

_EXAMPLE_RELATIVE = Path("data") / "examples" / "reaper" / "example_project.rpp"


def _example_project_path() -> Path:
    """Locate the monorepo demo project relative to this file."""

    for parent in Path(__file__).resolve().parents:
        candidate = parent / _EXAMPLE_RELATIVE
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not locate {_EXAMPLE_RELATIVE} above {Path(__file__).resolve()}"
    )


class ReaperKnowledge:
    """The driver's knowledge catalogue: guide-derived stock-FX and workflows."""

    stock_fx = STOCK_FX
    workflows = WORKFLOWS

    def lookup(self, name: Optional[str]) -> Optional[StockFx]:
        """Stock-FX entry for a parsed processor name (``None`` for third-party)."""

        return lookup_stock_fx(name)

    def workflow(self, key: str) -> Workflow:
        return WORKFLOWS[key]


class ReaperDriver(SessionDriver):
    """Dialect driver for REAPER ``.rpp`` project files."""

    dialect = "reaper"
    display_name = "REAPER"
    extensions = (".rpp",)

    # -- required -----------------------------------------------------------

    def sniff(self, filename: str, head: bytes) -> float:
        if filename.lower().endswith(".rpp"):
            return 0.95
        if head:
            if head.lstrip().startswith(b"<REAPER_PROJECT"):
                return 0.95
            if b"<REAPER_PROJECT" in head:
                return 0.95
        return 0.0

    def load(self, inputs: DriverInputs) -> CanonicalSession:
        if not inputs.files:
            raise ValueError("The REAPER driver needs an .rpp file to load.")
        uploaded = inputs.files[0]
        # Tolerant decode: .rpp is text, but never fail on stray bytes.
        text = uploaded.data.decode("utf-8", errors="replace")
        project = parse_rpp(text, source_file=uploaded.name)
        session = to_canonical(project, source_artifact="rpp_file")
        base_dir = inputs.folder or inputs.options.get("audio_base_dir")
        if base_dir:
            # Base directory for resolving relative audio paths (descriptor
            # extraction); recorded on the session rather than rewriting the
            # observed native paths.
            session.metadata["audio_base_dir"] = str(base_dir)
        return session

    def demo(self) -> CanonicalSession:
        path = _example_project_path()
        text = path.read_text(encoding="utf-8", errors="replace")
        project = parse_rpp(text, source_file=str(path))
        session = to_canonical(project, source_artifact="rpp_file")
        session.metadata["audio_base_dir"] = str(path.parent)
        return session

    def to_native(self, session: CanonicalSession) -> ProjectState:
        return to_native(session)

    # -- optional hooks -------------------------------------------------------

    def rules(self) -> list[Rule]:
        return list(REAPER_RULES)

    def knowledge(self) -> ReaperKnowledge:
        return ReaperKnowledge()

    def keywords(self) -> dict[str, Any]:
        return {"keyword_sets": REAPER_KEYWORDS}
