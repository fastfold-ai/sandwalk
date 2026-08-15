"""Per-session event wakes must not thrash other SSE waiters."""

from __future__ import annotations

import asyncio
import threading
import time

from agent_server.store.event_notifier import EventNotifier


def test_notify_wakes_matching_session():
    n = EventNotifier()
    seen = n.generation("s")
    hit = threading.Event()

    def wait() -> None:
        n.wait_for_change("s", seen, 2)
        hit.set()

    thread = threading.Thread(target=wait)
    thread.start()
    time.sleep(0.02)
    n.notify("s")
    assert hit.wait(1)
    thread.join(1)
    assert n.generation("s") == seen + 1


def test_notify_does_not_advance_other_session():
    n = EventNotifier()
    seen_b = n.generation("b")
    n.notify("a")
    n.notify("a")
    assert n.generation("b") == seen_b
    assert n.generation("a") == 2


def test_wake_all_advances_every_session():
    n = EventNotifier()
    n.notify("a")
    n.generation("b")
    n.wake_all()
    assert n.generation("a") == 2
    assert n.generation("b") == 1


def test_async_wait_for_change_wakes_matching_session():
    n = EventNotifier()
    seen = n.generation("s")

    async def _run() -> int:
        task = asyncio.create_task(n.async_wait_for_change("s", seen, 2))
        await asyncio.sleep(0.02)
        n.notify("s")
        return await task

    assert asyncio.run(_run()) == seen + 1
