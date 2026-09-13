"""Offline status endpoint — lets the UI display an offline banner."""

from __future__ import annotations

from fastapi import FastAPI

from agent_server.app_deps import AppDeps
from agent_server.offline_mode import get_offline_state, get_ui_status


def register_offline_status_routes(app: FastAPI, deps: AppDeps) -> None:
    """Register the /v1/system/offline-status endpoint."""

    @app.get("/v1/system/offline-status")
    async def offline_status() -> dict:
        """Return the current offline status for UI consumption.

        The UI polls this endpoint to decide whether to show the offline
        banner. It includes:
        - Whether we believe we're offline
        - A human-readable reason
        - Which features are affected
        - Whether offline mode was forced
        """
        return get_ui_status()

    @app.get("/v1/system/offline-state")
    async def offline_state() -> dict:
        """Return the raw offline state for debugging."""
        return get_offline_state()
