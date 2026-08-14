"""WebSocket stream of sandbox status/events for a session."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from agent_server.app_deps import AppDeps
from agent_server.auth_settings import SESSION_COOKIE, key_matches, request_is_authenticated
from agent_server.observability import OBSERVABILITY
from agent_server.sandbox_events import sandbox_event_bus

_LOG = logging.getLogger(__name__)


def _is_open(websocket: WebSocket) -> bool:
    """Both sides still connected — safe to send."""
    return (
        websocket.client_state == WebSocketState.CONNECTED
        and websocket.application_state == WebSocketState.CONNECTED
    )


async def _safe_send_json(websocket: WebSocket, payload: dict[str, Any]) -> bool:
    """Send only if the socket is still open. Returns False if the peer left."""
    if not _is_open(websocket):
        return False
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError = starlette raises when send after close.
        return False


async def _safe_close(websocket: WebSocket, code: int = 1000) -> None:
    """Close only if not already closed. Never raise from cleanup."""
    if websocket.application_state == WebSocketState.DISCONNECTED:
        return
    try:
        await websocket.close(code=code)
    except (WebSocketDisconnect, RuntimeError):
        pass


async def _authenticate_websocket(deps: AppDeps, websocket: WebSocket) -> bool:
    if not deps.current_api_key():
        return True
    authorization = websocket.headers.get("authorization", "")
    scheme, _, candidate = authorization.partition(" ")
    query_token = websocket.query_params.get("token", "")
    cookie_token = ""
    try:
        cookie_token = websocket.cookies.get(SESSION_COOKIE, "") or ""
    except Exception:
        cookie_token = ""
    key = deps.current_api_key() or ""
    return request_is_authenticated(
        headers={
            "authorization": authorization,
            "x-api-key": websocket.headers.get("x-api-key", ""),
        },
        cookies={SESSION_COOKIE: cookie_token},
        api_key=key,
        secret_key=deps.current_secret(),
        query_token=query_token,
    ) or (
        scheme.lower() == "bearer"
        and bool(candidate)
        and key_matches(candidate, key)
    )


def register_session_sandbox_stream_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.websocket("/v1/sessions/{session_id}/sandbox/stream")
    async def stream_session_sandbox(
        websocket: WebSocket,
        session_id: str,
    ) -> None:
        from agent_server.session_sandbox_service import SessionSandboxService

        # Accept first so auth/session failures close cleanly (close-before-accept
        # surfaces as a browser 403 and triggers reconnect storms).
        await websocket.accept()
        OBSERVABILITY.ws_sandbox_opened()
        try:
            if not await _authenticate_websocket(deps, websocket):
                await _safe_close(websocket, code=4401)
                return
            try:
                session = await asyncio.to_thread(store.get_session, session_id)
            except Exception:
                OBSERVABILITY.ws_sandbox_error()
                _LOG.exception(
                    "sandbox_stream: session lookup failed for %s", session_id
                )
                await _safe_close(websocket, code=1011)
                return
            if session is None:
                await _safe_close(websocket, code=4404)
                return
            try:
                initial = await asyncio.to_thread(
                    SessionSandboxService(store).status, session_id
                )
            except Exception:
                OBSERVABILITY.ws_sandbox_error()
                _LOG.exception(
                    "sandbox_stream: initial status failed for %s", session_id
                )
                await _safe_close(websocket, code=1011)
                return
            # Client may already be gone (tab switched before this first send).
            # Bail cleanly — _safe_send_json handles both socket states.
            if not await _safe_send_json(
                websocket,
                {
                    **initial.model_dump(mode="json", by_alias=True),
                    "type": "sandbox_status",
                    "ready": initial.status == "running",
                },
            ):
                await _safe_close(websocket)
                return

            # Sentinel to signal both pump/watch tasks to stop without racing
            # on send_json/close. Whoever hits the closed socket first flips it.
            stop = asyncio.Event()

            async def _pump_events() -> None:
                # Own the subscribe generator's cleanup — if we get cancelled
                # the `async for` unwinds and sandbox_event_bus.subscribe
                # drops us from its listener set (prevents leaked subscriptions
                # on tab thrash).
                try:
                    async for event in sandbox_event_bus.subscribe(session_id):
                        if stop.is_set():
                            return
                        if not await _safe_send_json(websocket, event):
                            stop.set()
                            return
                except asyncio.CancelledError:
                    raise
                except Exception:
                    OBSERVABILITY.ws_sandbox_error()
                    _LOG.exception(
                        "sandbox_stream: pump crashed for %s", session_id
                    )
                    stop.set()

            async def _watch_client() -> None:
                # Any inbound frame (including disconnect) unblocks receive().
                try:
                    while True:
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            stop.set()
                            return
                except (WebSocketDisconnect, RuntimeError):
                    stop.set()

            pump = asyncio.create_task(
                _pump_events(), name=f"sandbox-pump-{session_id}"
            )
            watch = asyncio.create_task(
                _watch_client(), name=f"sandbox-watch-{session_id}"
            )
            try:
                await stop.wait()
            finally:
                # Cancel & drain both tasks. return_exceptions swallows the
                # CancelledError we raise on cancel.
                for task in (pump, watch):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(pump, watch, return_exceptions=True)
                await _safe_close(websocket)
        finally:
            OBSERVABILITY.ws_sandbox_closed()
