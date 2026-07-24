"""In-process wake-up signal for session event streams.

The SSE route long-polls SQLite for new events. Without a signal it must
sleep between polls (previously a fixed 1s), which batches streamed tokens
into chunky bursts. ``append_event`` bumps a per-session generation counter
and wakes waiting pollers so deltas reach the client within milliseconds.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class EventNotifier:
    """Thread-safe per-session generation counter with blocking wait."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._generations: dict[str, int] = defaultdict(int)

    def generation(self, session_id: str) -> int:
        with self._cond:
            return self._generations[session_id]

    def notify(self, session_id: str) -> None:
        with self._cond:
            self._generations[session_id] += 1
            self._cond.notify_all()

    def wait_for_change(
        self, session_id: str, seen_generation: int, timeout: float
    ) -> int:
        """Block until the session's generation advances past ``seen_generation``.

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


EVENT_NOTIFIER = EventNotifier()
