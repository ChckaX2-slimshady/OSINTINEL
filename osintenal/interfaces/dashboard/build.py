"""Build a dashboard HTML file from an investigation result (doc 06 Phase 7)."""

from __future__ import annotations

from pathlib import Path

from ..api.service import build_dashboard_data
from .render import render_dashboard


def write_dashboard(result, path: str | Path) -> Path:
    """Project ``result`` → dashboard data → self-contained HTML, written to ``path``."""
    data = build_dashboard_data(result)
    html = render_dashboard(data)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    return p
