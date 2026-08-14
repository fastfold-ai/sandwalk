"""Tests for the async waiter added to EventNotifier."""

from __future__ import annotations

import asyncio
import threading
import time

from agent_server.store.event_notifier import EventNotifier


def test_async_wait_returns_immediately_when_generation_moved():
    """Fast path: if the seen generation is stale, return without parking."""

    async def _run() -> None:
        notifier = EventNotifier()
        notifier.notify("s1")  # bump to 1
        seen = 0
        current = await notifier.async_wait_for_change("s1", seen, timeout=5.0)
        assert current == 1

    asyncio.run(_run())


def test_async_wait_wakes_on_notify_from_another_thread():
    """Cross-thread notify wakes the async waiter via call_soon_threadsafe."""

    async def _run() -> None:
        notifier = EventNotifier()
        seen = notifier.generation("s1")

        def _publish_later() -> None:
            time.sleep(0.05)
            notifier.notify("s1")

        threading.Thread(target=_publish_later, daemon=True).start()
        start = time.monotonic()
        current = await notifier.async_wait_for_change("s1", seen, timeout=2.0)
        elapsed = time.monotonic() - start
        assert current > seen
        # Woke via notify, not the 2s timeout.
        assert elapsed < 1.0

    asyncio.run(_run())


def test_async_wait_times_out_without_notify():
    """No notify, no fast-path advance — returns after timeout."""

    async def _run() -> None:
        notifier = EventNotifier()
        seen = notifier.generation("s1")
        start = time.monotonic()
        current = await notifier.async_wait_for_change("s1", seen, timeout=0.1)
        elapsed = time.monotonic() - start
        assert current == seen
        assert elapsed >= 0.1

    asyncio.run(_run())


def test_async_wait_no_missed_wakeup_between_check_and_register():
    """Notify racing with waiter registration must not be missed.

    The waiter reads the generation, then registers itself. If a notify
    happens between those two steps, the re-check inside the lock has to
    catch it — otherwise the waiter parks forever.
    """

    async def _run() -> None:
        notifier = EventNotifier()
        seen = notifier.generation("s1")

        # Immediately notify BEFORE the waiter runs — the fast path
        # inside `async_wait_for_change` should short-circuit.
        notifier.notify("s1")
        current = await notifier.async_wait_for_change("s1", seen, timeout=1.0)
        assert current > seen

    asyncio.run(_run())


def test_async_waiter_cleaned_up_after_return():
    """The waiter set is empty after a normal return."""

    async def _run() -> None:
        notifier = EventNotifier()
        notifier.notify("s1")
        await notifier.async_wait_for_change("s1", 0, timeout=0.5)
        # After fast-path return, no waiter should be registered.
        assert notifier._async_waiters.get("s1", set()) == set()  # noqa: SLF001

    asyncio.run(_run())
