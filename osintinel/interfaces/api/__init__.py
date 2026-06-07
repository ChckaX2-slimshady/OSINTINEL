"""Read-only dashboard service layer (doc 06 Phase 7).

The JSON contract a REST API serves and the static dashboard renders. Framework-agnostic and
dependency-free; a FastAPI app would simply return ``build_dashboard_data(result).model_dump()``.
"""

from .service import DashboardData, build_dashboard_data, dashboard_json, replay_iteration

__all__ = ["DashboardData", "build_dashboard_data", "dashboard_json", "replay_iteration"]
