"""One SSE stream for sidebar lifecycle + N visible chat transcripts.

WKWebView / Chromium cap HTTP/1.1 at ~6 connections per host. Split view
used one EventSource per panel plus the global session bus and starved
Dashboard fetches. This route keeps that to a single connection.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, Query, Request
from fastapi.responses import StreamingResponse

from agent_server.app_deps import AppDeps
from agent_server.observability import OBSERVABILITY
from agent_server.routes.sse_util import sse_data
from agent_server.session_event_bus import session_event_bus
from agent_server.store.event_notifier import EVENT_NOTIFIER

MAX_MUX_SESSIONS = 16


def parse_session_ids(raw: str | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for part in str(raw or "").split(","):
        sid = part.strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
        if len(out) >= MAX_MUX_SESSIONS:
            break
    return out


def parse_after_cursors(raw: str | None) -> dict[str, int]:
    cursors: dict[str, int] = {}
    for part in str(raw or "").split(","):
        item = part.strip()
        if ":" not in item:
            continue
        sid, _, seq = item.partition(":")
        sid = sid.strip()
        if not sid or not seq.strip().isdigit():
            continue
        cursors[sid] = max(0, int(seq.strip()))
    return cursors


def register_events_mux_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get("/v1/events")
    async def stream_mux_events(
        request: Request,
        sessions: str | None = Query(default=None),
        after: str | None = Query(default=None),
    ) -> StreamingResponse:
        session_ids = parse_session_ids(sessions)
        cursors = parse_after_cursors(after)
        shutdown_event = request.app.state.shutdown_event

        async def event_source() -> AsyncIterator[str]:
            OBSERVABILITY.sse_opened()
            lifecycle_q = session_event_bus.subscribe_queue()
            gens = {sid: EVENT_NOTIFIER.generation(sid) for sid in session_ids}
            for sid in session_ids:
                cursors.setdefault(sid, 0)
            yield ": connected\n\n"
            held_lifecycle: dict | None = None
            try:
                while (
                    not shutdown_event.is_set()
                    and not await request.is_disconnected()
                ):
                    emitted = False
                    for sid in session_ids:
                        gens[sid] = EVENT_NOTIFIER.generation(sid)
                        events = await asyncio.to_thread(
                            store.list_events,
                            sid,
                            after_sequence=cursors.get(sid, 0),
                        )
                        for event in events:
                            cursors[sid] = event.sequence
                            data = json.dumps(
                                {
                                    "channel": "transcript",
                                    "sessionId": sid,
                                    "event": event.model_dump(
                                        mode="json", by_alias=True
                                    ),
                                },
                                separators=(",", ":"),
                            )
                            yield sse_data(
                                data, event_id=f"t:{sid}:{event.sequence}"
                            )
                            emitted = True
                    pending_life = [held_lifecycle] if held_lifecycle else []
                    held_lifecycle = None
                    while True:
                        if pending_life:
                            result = pending_life.pop()
                        else:
                            try:
                                result = lifecycle_q.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                        payload = json.dumps(
                            {"channel": "lifecycle", "event": result},
                            separators=(",", ":"),
                            default=str,
                        )
                        seq = result.get("sequence")
                        yield sse_data(
                            payload,
                            event_id=f"l:{seq}" if seq is not None else None,
                        )
                        emitted = True
                    if not emitted:
                        yield ": heartbeat\n\n"
                    life_task = asyncio.create_task(lifecycle_q.get())
                    wake_task = asyncio.create_task(
                        EVENT_NOTIFIER.async_wait_for_any(session_ids, gens, 1.0)
                    )
                    done, pending = await asyncio.wait(
                        {life_task, wake_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                    for task in pending:
                        with contextlib.suppress(
                            asyncio.CancelledError, Exception
                        ):
                            await task
                    if life_task in done and not life_task.cancelled():
                        try:
                            held_lifecycle = life_task.result()
                        except (asyncio.CancelledError, Exception):
                            held_lifecycle = None
                    if wake_task in done and not wake_task.cancelled():
                        try:
                            gens.update(wake_task.result() or {})
                        except Exception:
                            pass
            finally:
                session_event_bus.unsubscribe_queue(lifecycle_q)
                OBSERVABILITY.sse_closed()

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
