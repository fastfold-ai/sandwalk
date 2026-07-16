"""Session event history and SSE stream routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from agent_server.app_deps import AppDeps
from agent_server.models import EventList


def register_session_event_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get("/v1/sessions/{session_id}/events/history", response_model=EventList)
    async def list_event_history(session_id: str) -> EventList:
        """One-shot replay of persisted session events (for export / debugging)."""
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        events = await asyncio.to_thread(store.list_events, session_id, after_sequence=0)
        return EventList(data=events)

    @app.get("/v1/sessions/{session_id}/events")
    async def stream_events(
        request: Request,
        session_id: str,
        after_sequence: int = Query(default=0, ge=0),
    ) -> StreamingResponse:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")

        header_sequence = request.headers.get("last-event-id", "").strip()
        cursor = after_sequence
        if header_sequence.isdigit():
            cursor = max(cursor, int(header_sequence))

        async def event_source() -> AsyncIterator[str]:
            nonlocal cursor
            heartbeat_ticks = 0
            while not await request.is_disconnected():
                events = await asyncio.to_thread(
                    store.list_events,
                    session_id,
                    after_sequence=cursor,
                )
                if events:
                    heartbeat_ticks = 0
                    for event in events:
                        cursor = event.sequence
                        data = json.dumps(
                            event.model_dump(mode="json", by_alias=True),
                            separators=(",", ":"),
                        )
                        yield f"id: {event.sequence}\nevent: {event.type}\ndata: {data}\n\n"
                else:
                    heartbeat_ticks += 1
                    if heartbeat_ticks >= 15:
                        heartbeat_ticks = 0
                        yield ": heartbeat\n\n"
                    await asyncio.sleep(1)

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
