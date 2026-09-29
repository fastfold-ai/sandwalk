"""Publish UI commands (e.g. open a split) to every connected dashboard.

The dashboard already reacts to ``ui.command`` events on the session event
bus — Capy's ``capy.open_split`` tool publishes them from inside the server
process. This route exposes the same channel over HTTP so scripts, the e2e
harness, and the CLI can drive the running UI (``scripts/dev-grid.mjs``).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.models.base import ApiModel
from agent_server.session_event_bus import session_event_bus

SUPPORTED_ACTIONS = frozenset({"open_split"})


class UiCommandRequest(ApiModel):
    action: str
    session_ids: list[str] | None = None
    # Optional rows × cols for ``open_split``; the UI builds the pane tree.
    layout: dict[str, int] | None = None


class UiCommandResponse(ApiModel):
    accepted: bool
    action: str


def build_ui_command_payload(request: UiCommandRequest) -> dict[str, Any]:
    action = (request.action or "").strip()
    if action not in SUPPORTED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported UI action: {action or '(empty)'}")
    payload: dict[str, Any] = {"action": action}
    if action == "open_split":
        ids = [str(sid).strip() for sid in (request.session_ids or []) if str(sid).strip()]
        if len(ids) < 2:
            raise HTTPException(status_code=400, detail="open_split needs at least two session ids.")
        payload["sessionIds"] = ids
        if request.layout:
            rows = int(request.layout.get("rows", 0) or 0)
            cols = int(request.layout.get("cols", 0) or 0)
            if rows < 1 or cols < 1:
                raise HTTPException(status_code=400, detail="layout needs rows >= 1 and cols >= 1.")
            payload["layout"] = {"rows": rows, "cols": cols}
    return payload


def register_ui_command_routes(app: FastAPI, deps: AppDeps) -> None:  # noqa: ARG001
    @app.post("/v1/ui/commands", response_model=UiCommandResponse, status_code=202)
    async def post_ui_command(request: UiCommandRequest) -> UiCommandResponse:
        payload = build_ui_command_payload(request)
        session_event_bus.publish("ui.command", payload)
        return UiCommandResponse(accepted=True, action=payload["action"])
