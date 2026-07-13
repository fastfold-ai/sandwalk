"""In-process pub/sub for per-session sandbox status (local server)."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

from agent_server.models import SessionSandboxStatus

logger = logging.getLogger(__name__)


def build_sandbox_event_payload(status: SessionSandboxStatus) -> dict[str, Any]:
    payload = status.model_dump(mode="json", by_alias=True)
    payload["type"] = "sandbox_status"
    payload["ready"] = status.status == "running"
    return payload


class SessionSandboxEventBus:
    """Fan-out sandbox status events to websocket subscribers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._guard = asyncio.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, status: SessionSandboxStatus) -> None:
        payload = build_sandbox_event_payload(status)
        session_id = status.session_id
        loop = self._loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return

        def _deliver() -> None:
            queues = list(self._subscribers.get(session_id, ()))
            for queue in queues:
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    try:
                        _ = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        queue.put_nowait(payload)
                    except asyncio.QueueFull:
                        logger.debug(
                            "Dropping sandbox event for session %s (subscriber backlog)",
                            session_id,
                        )

        try:
            running = loop.is_running()
        except Exception:  # noqa: BLE001
            running = False
        if running:
            loop.call_soon_threadsafe(_deliver)
        else:
            _deliver()

    async def subscribe(self, session_id: str) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        async with self._guard:
            self._subscribers[session_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._guard:
                self._subscribers[session_id].discard(queue)
                if not self._subscribers[session_id]:
                    self._subscribers.pop(session_id, None)


# Process-wide bus for the local agent server.
sandbox_event_bus = SessionSandboxEventBus()
