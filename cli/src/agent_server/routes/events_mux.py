"""One SSE stream for sidebar lifecycle + N visible chat transcripts.

WKWebView / Chromium cap HTTP/1.1 at ~6 connections per host. Split view
used one EventSource per panel plus the global session bus and starved
Dashboard fetches. This route keeps that to a single connection.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable

from fastapi import FastAPI, Query, Request
from fastapi.responses import StreamingResponse

from agent_server.app_deps import AppDeps
from agent_server.observability import OBSERVABILITY
from agent_server.routes.sse_util import sse_data
from agent_server.session_event_bus import session_event_bus
from agent_server.store.event_notifier import EVENT_NOTIFIER

# One SSE carries every visible pane's transcript. 16 silently dropped the
# 17th pane of a 4x4 grid (16 panes + the registered active chat) — its
# reply landed in the DB but never reached the UI. 64 covers an 8x8 grid
# plus extras; ids past the cap are logged, not swallowed.
MAX_MUX_SESSIONS = 64
# Sessions are normally re-read only when their notifier generation moves.
# This sweep re-reads everything on a slow cadence as a safety net for
# writers that append with ``notify=False``.
FULL_SWEEP_S = 5.0
_LOG = logging.getLogger("agent_server")


def parse_session_ids(raw: str | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for part in str(raw or "").split(","):
        sid = part.strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        if len(out) >= MAX_MUX_SESSIONS:
            _LOG.warning(
                "events mux: more than %d sessions requested; dropping %s…",
                MAX_MUX_SESSIONS,
                sid,
            )
            break
        out.append(sid)
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


async def wait_lifecycle_or_wake(
    lifecycle_get: Awaitable[dict],
    wake: Awaitable[dict | None],
) -> tuple[dict | None, dict | None]:
    """Race a lifecycle-queue read against the transcript notifier.

    Returns ``(lifecycle_event, generations)``; whichever side did not win is
    None. Both child tasks are always cancelled and awaited — including when
    the caller itself is cancelled because the SSE client went away. Without
    that, every disconnect left a pending ``Queue.get()`` task behind
    ("Task was destroyed but it is pending!" once per dropped stream).
    """
    life_task = asyncio.ensure_future(lifecycle_get)
    wake_task = asyncio.ensure_future(wake)
    try:
        done, _pending = await asyncio.wait(
            {life_task, wake_task}, return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        for task in (life_task, wake_task):
            if not task.done():
                task.cancel()
        for task in (life_task, wake_task):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
    lifecycle_event: dict | None = None
    generations: dict | None = None
    if life_task in done and not life_task.cancelled():
        with contextlib.suppress(Exception):
            lifecycle_event = life_task.result()
    if wake_task in done and not wake_task.cancelled():
        with contextlib.suppress(Exception):
            generations = wake_task.result() or {}
    return lifecycle_event, generations


def register_events_mux_routes(app: FastAPI, deps: AppDeps) -> None:
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
            # Per-session (generation, monotonic time) of our last DB read.
            # A token on one pane used to trigger a list_events query for
            # every pane on the stream (16 panes streaming = 256 queries per
            # round); now only sessions whose generation moved are read.
            last_read: dict[str, tuple[int, float]] = {}
            try:
                while (
                    not shutdown_event.is_set()
                    and not await request.is_disconnected()
                ):
                    emitted = False
                    now = time.monotonic()
                    for sid in session_ids:
                        gen = EVENT_NOTIFIER.generation(sid)
                        gens[sid] = gen
                        prev = last_read.get(sid)
                        if (
                            prev is not None
                            and prev[0] == gen
                            and now - prev[1] < FULL_SWEEP_S
                        ):
                            continue
                        last_read[sid] = (gen, now)
                        owner = deps.store_for_session(sid)
                        events = await asyncio.to_thread(
                            owner.list_events,
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
                    lifecycle_hit, wake_hit = await wait_lifecycle_or_wake(
                        lifecycle_q.get(),
                        EVENT_NOTIFIER.async_wait_for_any(session_ids, gens, 1.0),
                    )
                    if lifecycle_hit is not None:
                        held_lifecycle = lifecycle_hit
                    if wake_hit:
                        gens.update(wake_hit)
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
