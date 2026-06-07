"""Static, self-contained HTML dashboard (doc 06 Phase 7).

``render_dashboard(DashboardData) -> str`` produces one offline HTML document — inline CSS, SVG,
and vanilla JS, no external resources — so it renders air-gapped and is testable without a
browser. ``write_dashboard`` builds it from an investigation result and writes the file.
"""

from .render import render_dashboard
from .build import write_dashboard

__all__ = ["render_dashboard", "write_dashboard"]
