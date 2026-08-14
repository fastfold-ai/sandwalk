"""Global session lifecycle SSE stream.

Replaces the frontend's 2-second `loadSessions` poll + snapshot-diff for
status changes. Any subscriber gets every session's create/update/delete +
run lifecycle events on a single stream, so the UI can maintain a coherent
`sessions` cache without inferring transitions.

Emits events published to `session_event_bus`; see that module for the
authoritative event catalog and payload shape.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from agent_server.app_deps import AppDeps
from agent_server.session_event_bus import session_event_bus


def register_session_events_global_routes(app: FastAPI, deps: AppDeps) -> None:  # noqa: ARG001
    @app.get("/v1/session-events")
    async def stream_session_events(request: Request) -> StreamingResponse:
        shutdown_event = request.app.state.shutdown_event

        async def event_source() -> AsyncIterator[str]:
            # Subscribe first, then emit a hello frame so the client knows
            # the connection is live (also flushes any proxy buffering).
            subscription = session_event_bus.subscribe()
            yield ": connected\n\n"
            try:
                async for event in subscription:
                    if shutdown_event.is_set():
                        break
                    if await request.is_disconnected():
                        break
                    payload = json.dumps(event, separators=(",", ":"), default=str)
                    yield f"id: {event['sequence']}\ndata: {payload}\n\n"
                    # Same WKWebView (Tauri) buffer flush trick as the
                    # per-session SSE — trailing small frames can sit in
                    # the fetch stream until more bytes arrive.
                    yield ":" + (" " * 8192) + "\n\n"
            except asyncio.CancelledError:
                raise
            finally:
                # `subscribe()` cleanup runs on generator close via GC;
                # nothing else to do here.
                pass

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
