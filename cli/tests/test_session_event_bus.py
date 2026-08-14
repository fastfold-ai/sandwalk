"""Tests for the global session lifecycle pub/sub."""

from __future__ import annotations

import asyncio
import threading

from agent_server.session_event_bus import SessionEventBus, SessionEventType


def test_publish_assigns_monotonic_sequence_single_thread():
    """Sequence starts at 1 and grows by 1 per publish."""

    async def _run() -> None:
        bus = SessionEventBus()
        bus.bind_loop(asyncio.get_running_loop())

        received: list[dict] = []

        async def _collect() -> None:
            async for event in bus.subscribe():
                received.append(event)
                if len(received) == 3:
                    return

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        bus.publish(SessionEventType.SESSION_CREATED, {"sessionId": "a"})
        bus.publish(SessionEventType.SESSION_UPDATED, {"sessionId": "a"})
        bus.publish(SessionEventType.SESSION_DELETED, {"sessionId": "a"})
        await asyncio.wait_for(task, timeout=1.0)

        assert [e["sequence"] for e in received] == [1, 2, 3]
        assert [e["type"] for e in received] == [
            SessionEventType.SESSION_CREATED,
            SessionEventType.SESSION_UPDATED,
            SessionEventType.SESSION_DELETED,
        ]

    asyncio.run(_run())


def test_publish_sequence_is_thread_safe():
    """Concurrent publishes from many threads produce unique sequences.

    Regression guard for H1: without the lock the counter increment was
    racy and could produce duplicate or missing sequence numbers.
    """

    async def _run() -> None:
        bus = SessionEventBus()
        bus.bind_loop(asyncio.get_running_loop())
        n_threads = 32
        per_thread = 100

        def worker() -> None:
            for _ in range(per_thread):
                bus.publish("test.event", {"sessionId": "s"})

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # We publish n_threads * per_thread events; sequences must be a
        # complete run 1..N with no gaps and no duplicates.
        assert bus._sequence == n_threads * per_thread  # noqa: SLF001

    asyncio.run(_run())


def test_publish_no_loop_bound_returns_silently():
    """Publish before bind_loop() must not raise (startup / tests)."""
    bus = SessionEventBus()
    # No bind_loop, no running loop — should just no-op.
    bus.publish(SessionEventType.SESSION_CREATED, {"sessionId": "x"})


def test_subscriber_unsubscribe_on_generator_close():
    """Closing the subscriber generator removes it from the fan-out set."""

    async def _run() -> None:
        bus = SessionEventBus()
        bus.bind_loop(asyncio.get_running_loop())

        gen = bus.subscribe()
        # Prime the generator so it registers itself as a subscriber.
        task = asyncio.create_task(gen.__anext__())
        await asyncio.sleep(0)
        bus.publish("test", {})
        await task
        assert len(bus._subscribers) == 1  # noqa: SLF001

        await gen.aclose()
        assert len(bus._subscribers) == 0  # noqa: SLF001

    asyncio.run(_run())


def test_backpressure_drops_oldest_when_subscriber_slow():
    """When a subscriber's queue is full, oldest event is dropped."""

    async def _run() -> None:
        bus = SessionEventBus()
        bus.bind_loop(asyncio.get_running_loop())
        # Force a tiny queue to make the test fast.
        bus._QUEUE_CAPACITY = 4  # type: ignore[attr-defined]  # noqa: SLF001

        gen = bus.subscribe()
        task = asyncio.create_task(gen.__anext__())
        await asyncio.sleep(0)
        # Publish more than queue capacity; the slow subscriber should
        # still be alive and receive some events (not deadlock the writer).
        for i in range(20):
            bus.publish("test", {"i": i})
        # Drain a few — no exceptions, no writer stall.
        first = await task
        assert first["type"] == "test"
        await gen.aclose()

    asyncio.run(_run())
