"""WebSocket stream of sandbox status/events for a session."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, WebSocket

from agent_server.app_deps import AppDeps
from agent_server.auth_settings import SESSION_COOKIE, key_matches, request_is_authenticated
from agent_server.sandbox_events import sandbox_event_bus


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
        if not await _authenticate_websocket(deps, websocket):
            await websocket.close(code=4401)
            return
        try:
            session = await asyncio.to_thread(store.get_session, session_id)
        except Exception:
            await websocket.close(code=1011)
            return
        if session is None:
            await websocket.close(code=4404)
            return
        try:
            initial = await asyncio.to_thread(
                SessionSandboxService(store).status, session_id
            )
            await websocket.send_json(
                {
                    **initial.model_dump(mode="json", by_alias=True),
                    "type": "sandbox_status",
                    "ready": initial.status == "running",
                }
            )
        except Exception:
            await websocket.close(code=1011)
            return

        async def _pump_events() -> None:
            async for event in sandbox_event_bus.subscribe(session_id):
                await websocket.send_json(event)

        async def _watch_client() -> None:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    return

        pump = asyncio.create_task(_pump_events())
        watch = asyncio.create_task(_watch_client())
        try:
            done, pending = await asyncio.wait(
                {pump, watch},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                exc = task.exception()
                if exc is not None and not isinstance(exc, asyncio.CancelledError):
                    raise exc
        except Exception:
            pass
        finally:
            if not websocket.client_state.name == "DISCONNECTED":
                try:
                    await websocket.close()
                except Exception:
                    pass
