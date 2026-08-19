"""In-process pub/sub for global session lifecycle events.

Distinct from ``sandbox_event_bus`` (per-session sandbox status) and from
``EVENT_NOTIFIER`` (per-session transcript event wakeups). This bus is a
single global stream: any change to a session's metadata or status
(create, update, delete, run start/finish, status transition) fans out to
every subscriber, regardless of which project the session belongs to.

Why it exists: the frontend needs one authoritative push channel for
session-level changes so it can maintain a coherent `sessions` cache
without polling. Previously the UI inferred status transitions by
diffing snapshots from a 2s poll, which produced false-positive
attention marks whenever two fetch sources (loadSessions +
loadForeignSessions) returned overlapping-but-stale views. The bus
replaces that inference with a real event.

Follows the same asyncio.Queue-per-subscriber pattern as
``sandbox_event_bus`` — simple, no thread-pool pressure, back-pressure
safe (drops oldest when a slow client falls behind rather than blocking
the writer).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


class SessionEventBus:
    """Fan-out global session-lifecycle events to any subscriber."""

    _QUEUE_CAPACITY = 128

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._guard = asyncio.Lock()
        self._sequence: int = 0
        self._sequence_lock = asyncio.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called at app startup so ``publish()`` from worker threads can
        schedule delivery onto the correct loop."""
        self._loop = loop

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Broadcast an event to every current subscriber.

        Callable from any thread. If invoked from a non-async context, the
        actual delivery is scheduled on the bound loop via
        ``call_soon_threadsafe``. Payloads should be small JSON-serializable
        dicts (session snapshots, status transitions, id references).
        """
        loop = self._loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No loop reachable yet (startup, tests) — drop silently.
                return

        # Sequence + timestamp assigned on the writer's clock so subscribers
        # can order events without a per-loop trip.
        self._sequence += 1
        event: dict[str, Any] = {
            "sequence": self._sequence,
            "type": event_type,
            "timestamp": time.time(),
            "payload": payload,
        }

        def _deliver() -> None:
            queues = list(self._subscribers)
            for queue in queues:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # Slow subscriber: drop oldest to make room. Preferable
                    # to blocking the writer or growing memory unbounded.
                    try:
                        _ = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        logger.debug(
                            "Dropping global session event %s (subscriber backlog)",
                            event_type,
                        )

        try:
            running = loop.is_running()
        except Exception:  # noqa: BLE001
            running = False
        if running:
            loop.call_soon_threadsafe(_deliver)
        else:
            _deliver()

    def subscribe_queue(self) -> asyncio.Queue[dict[str, Any]]:
        """Register a subscriber queue the caller drains itself."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self._QUEUE_CAPACITY
        )
        self._subscribers.add(queue)
        return queue

    def unsubscribe_queue(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        """Yield events until the caller stops iterating."""
        queue = self.subscribe_queue()
        try:
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe_queue(queue)


# Process-wide bus for the local agent server.
session_event_bus = SessionEventBus()


# Canonical event type names — mirrored on the frontend for type-safe
# switch statements. Keep in sync with `useGlobalSessionEvents.ts`.
class SessionEventType:
    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"
    SESSION_DELETED = "session.deleted"
    SESSION_STATUS_CHANGED = "session.status_changed"
    RUN_STARTED = "run.started"
    RUN_AWAITING_APPROVAL = "run.awaiting_approval"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_INTERRUPTED = "run.interrupted"
