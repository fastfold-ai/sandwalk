"""In-process wake-up signal for session event streams.

The SSE route long-polls SQLite for new events. Without a signal it must
sleep between polls, which batches streamed tokens into chunky bursts.
``append_event`` bumps a per-session generation counter and wakes waiting
pollers so deltas reach the client within milliseconds.

Two waiter flavors coexist:

- **Sync** (``wait_for_change``): a ``threading.Condition``. Callers hold a
  thread while blocked. Retained for background code paths that don't own an
  event loop.
- **Async** (``async_wait_for_change``): per-waiter ``asyncio.Event``. The
  waiter parks in the event loop without pinning a thread — critical for SSE
  routes, where dozens of concurrent streams would otherwise saturate the
  default asyncio executor and stall unrelated ``asyncio.to_thread`` calls
  (list_messages, get_session, etc.).

Writers call the same ``notify()`` from any thread; it wakes both flavors.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass(eq=False)
class _AsyncWaiter:
    """Ties an ``asyncio.Event`` to the loop that created it.

    ``notify()`` may be called from any thread (writers hold ``_write_lock``
    on the SQLite side), so we can't touch the Event directly — we have to
    schedule ``event.set()`` on its owning loop with ``call_soon_threadsafe``.

    ``eq=False`` preserves identity-based hashing so instances can live in
    a ``set`` — the default dataclass ``__eq__`` is field-based, which
    marks the class unhashable and would crash ``self._async_waiters[
    session_id].add(waiter)``.
    """

    loop: asyncio.AbstractEventLoop
    event: asyncio.Event


class EventNotifier:
    """Per-session generation counter with both sync and async waiters."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._generations: dict[str, int] = defaultdict(int)
        self._async_waiters: dict[str, set[_AsyncWaiter]] = defaultdict(set)

    def generation(self, session_id: str) -> int:
        with self._cond:
            return self._generations[session_id]

    def notify(self, session_id: str) -> None:
        # Snapshot the async waiters under the lock, then release before
        # scheduling the wakeups so a slow loop can't block the writer.
        with self._cond:
            self._generations[session_id] += 1
            self._cond.notify_all()
            waiters = list(self._async_waiters.get(session_id, ()))
        for waiter in waiters:
            try:
                waiter.loop.call_soon_threadsafe(waiter.event.set)
            except RuntimeError:
                # Loop is closed — the SSE task already unwound; the waiter
                # will be removed on its next `async_wait_for_change` return.
                pass

    def wake_all(self) -> None:
        """Wake every active event stream (used during server shutdown)."""
        with self._cond:
            for session_id in self._generations:
                self._generations[session_id] += 1
            self._cond.notify_all()
            snapshot = [
                waiter
                for waiters in self._async_waiters.values()
                for waiter in waiters
            ]
        for waiter in snapshot:
            try:
                waiter.loop.call_soon_threadsafe(waiter.event.set)
            except RuntimeError:
                pass

    def wait_for_change(
        self, session_id: str, seen_generation: int, timeout: float
    ) -> int:
        """Block a thread until the session's generation advances.

        Returns the current generation (unchanged on timeout). Callers capture
        the generation *before* checking for events so an event appended in the
        gap wakes them immediately instead of waiting out the timeout.
        """
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._generations[session_id] == seen_generation:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._cond.wait(remaining)
            return self._generations[session_id]

    async def async_wait_for_change(
        self, session_id: str, seen_generation: int, timeout: float
    ) -> int:
        """Async equivalent of ``wait_for_change`` — does not pin a thread.

        Same fast-path semantics: if the generation already advanced, returns
        immediately without ever parking.
        """
        # Fast path: generation moved between the caller's capture and now.
        with self._cond:
            current = self._generations[session_id]
            if current != seen_generation:
                return current

        loop = asyncio.get_running_loop()
        waiter = _AsyncWaiter(loop=loop, event=asyncio.Event())
        with self._cond:
            # Re-check under the lock so a notify() that runs between the
            # fast-path check and the waiter registration isn't missed.
            current = self._generations[session_id]
            if current != seen_generation:
                return current
            self._async_waiters[session_id].add(waiter)
        try:
            try:
                await asyncio.wait_for(waiter.event.wait(), timeout=timeout)
            except TimeoutError:
                pass
            with self._cond:
                return self._generations[session_id]
        finally:
            with self._cond:
                self._async_waiters[session_id].discard(waiter)
                if not self._async_waiters[session_id]:
                    del self._async_waiters[session_id]


EVENT_NOTIFIER = EventNotifier()
