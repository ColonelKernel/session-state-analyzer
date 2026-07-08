"""Writing a :class:`MetricsReport` to disk.

A thin JSON serializer used later by the dataset export (§57 ``metrics/`` tree)
and by a workbench download button. It is deliberately dependency-free and does
no computation — hand it a report and an output directory and it writes
``metrics.json``. It is not invoked at import time anywhere.
"""

from __future__ import annotations

from pathlib import Path

from .models import MetricsReport

METRICS_FILENAME = "metrics.json"


def write_metrics(report: MetricsReport, out_dir: Path | str) -> Path:
    """Write ``report`` to ``<out_dir>/metrics.json`` and return the path.

    Creates ``out_dir`` (and parents) if needed. The JSON is pretty-printed and
    newline-terminated so it diffs cleanly under version control.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / METRICS_FILENAME
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
