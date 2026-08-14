"""Session event history and SSE stream routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from agent_server.app_deps import AppDeps
from agent_server.models import EventList
from agent_server.observability import OBSERVABILITY
from agent_server.store.event_notifier import EVENT_NOTIFIER


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
            OBSERVABILITY.sse_opened()
            heartbeat_ticks = 0
            flush_after_batch = False
            shutdown_event = request.app.state.shutdown_event
            try:
                while (
                    not shutdown_event.is_set()
                    and not await request.is_disconnected()
                ):
                    # Capture the generation before querying so an event
                    # appended between the query and the wait wakes us instantly.
                    generation = EVENT_NOTIFIER.generation(session_id)
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
                            # No `event:` name — EventSource.onmessage only
                            # fires for unnamed frames; the JSON carries `type`.
                            yield f"id: {event.sequence}\ndata: {data}\n\n"
                        # WKWebView (Tauri) buffers small fetch-stream chunks
                        # until more bytes arrive, so trailing frames
                        # (assistant.message / run.completed) can sit
                        # undelivered for seconds. Pad each batch past the
                        # buffer threshold; browsers ignore comments.
                        yield ":" + (" " * 8192) + "\n\n"
                        flush_after_batch = True
                    else:
                        if flush_after_batch:
                            # Second write in a separate packet: WKWebView may
                            # hold the previous chunk until more network data.
                            flush_after_batch = False
                            yield ":" + (" " * 8192) + "\n\n"
                        heartbeat_ticks += 1
                        if heartbeat_ticks >= 15:
                            heartbeat_ticks = 0
                            yield ": heartbeat\n\n"
                        # Push-latency wake on new events; 1s timeout preserves
                        # the heartbeat cadence and disconnect detection.
                        # Async waiter: parks in the event loop without
                        # occupying a thread from the default executor — lets
                        # the pool serve list_messages / get_session while N
                        # SSE streams are open (splits, background tabs).
                        await EVENT_NOTIFIER.async_wait_for_change(
                            session_id,
                            generation,
                            1.0,
                        )
            finally:
                OBSERVABILITY.sse_closed()

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
