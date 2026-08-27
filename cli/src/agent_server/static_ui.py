"""Optional production dashboard served from a Vite build (local-web dist/)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("agent_server.static_ui")


def resolve_ui_dist() -> Path | None:
    """Return a usable UI dist directory from env, or None when unset/invalid."""
    raw = (
        os.environ.get("SANDWALK_UI_DIST")
        or os.environ.get("FASTFOLD_UI_DIST")
        or ""
    ).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    try:
        path = path.resolve()
    except OSError:
        return None
    index = path / "index.html"
    if path.is_dir() and index.is_file():
        return path
    logger.warning("SANDWALK_UI_DIST set but invalid: %s", path)
    return None


def mount_static_ui(app: FastAPI, dist: Path) -> None:
    """Mount Vite production assets + SPA fallback (must run after /v1 routes)."""
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="ui-assets")

    @app.get("/")
    async def ui_index() -> FileResponse:
        return FileResponse(dist / "index.html")

    @app.get("/{full_path:path}", response_model=None)
    async def ui_spa(full_path: str) -> FileResponse | JSONResponse:
        # Never serve the dashboard for API URLs. A missing /v1/* route must
        # stay JSON so the UI does not JSON.parse("<!doctype html>…").
        if full_path == "v1" or full_path.startswith("v1/"):
            return JSONResponse(
                status_code=404,
                content={"detail": f"Not Found: /{full_path}"},
            )
        candidate = (dist / full_path).resolve()
        try:
            candidate.relative_to(dist.resolve())
        except ValueError:
            return FileResponse(dist / "index.html")
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")

    logger.info("Serving production dashboard from %s", dist)
