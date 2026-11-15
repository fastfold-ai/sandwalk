"""Track when this server last used a Modal sandbox.

Modal ends a sandbox after ``idle_timeout`` seconds with no running command,
no stdin write, and no open tunnel connection. It does not report how long a
sandbox has been idle, so the countdown the UI shows is our own estimate,
built from the commands this server sends.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager


class SandboxActivity:
    """Last command time and in-flight command count for one sandbox."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._in_flight = 0
        self.last_active_at = time.time()

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._in_flight > 0

    def touch(self) -> None:
        with self._lock:
            self.last_active_at = time.time()

    @contextmanager
    def track(self) -> Iterator[None]:
        """Mark a command as running for the duration of the block."""
        with self._lock:
            self._in_flight += 1
            self.last_active_at = time.time()
        try:
            yield
        finally:
            with self._lock:
                self._in_flight = max(0, self._in_flight - 1)
                self.last_active_at = time.time()
