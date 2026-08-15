"""Lightweight in-process counters for debugging concurrency pressure.

The event delivery layer (SSE + sandbox WebSocket) parks threads waiting on
SQLite polls / event queues. When many splits are open the default asyncio
thread pool can saturate silently — requests queue forever instead of erroring.

`/v1/debug/health` returns a snapshot so we can see stream churn, active
connections, and pool utilization while reproducing bugs. No external deps.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field


@dataclass
class ObservabilityState:
    _lock: threading.Lock = field(default_factory=threading.Lock)
    sse_streams_open: int = 0
    sse_streams_opened_total: int = 0
    sse_streams_closed_total: int = 0
    ws_sandbox_open: int = 0
    ws_sandbox_opened_total: int = 0
    ws_sandbox_closed_total: int = 0
    ws_sandbox_errors_total: int = 0

    def sse_opened(self) -> None:
        with self._lock:
            self.sse_streams_open += 1
            self.sse_streams_opened_total += 1

    def sse_closed(self) -> None:
        with self._lock:
            self.sse_streams_open = max(0, self.sse_streams_open - 1)
            self.sse_streams_closed_total += 1

    def ws_sandbox_opened(self) -> None:
        with self._lock:
            self.ws_sandbox_open += 1
            self.ws_sandbox_opened_total += 1

    def ws_sandbox_closed(self) -> None:
        with self._lock:
            self.ws_sandbox_open = max(0, self.ws_sandbox_open - 1)
            self.ws_sandbox_closed_total += 1

    def ws_sandbox_error(self) -> None:
        with self._lock:
            self.ws_sandbox_errors_total += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "sse_streams_open": self.sse_streams_open,
                "sse_streams_opened_total": self.sse_streams_opened_total,
                "sse_streams_closed_total": self.sse_streams_closed_total,
                "ws_sandbox_open": self.ws_sandbox_open,
                "ws_sandbox_opened_total": self.ws_sandbox_opened_total,
                "ws_sandbox_closed_total": self.ws_sandbox_closed_total,
                "ws_sandbox_errors_total": self.ws_sandbox_errors_total,
            }


OBSERVABILITY = ObservabilityState()


def thread_pool_snapshot() -> dict[str, int | None]:
    """Info about the asyncio default thread pool executor if reachable."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return {"max_workers": None, "active_threads": None, "queued": None}
    executor = getattr(loop, "_default_executor", None)
    if executor is None:
        return {"max_workers": None, "active_threads": None, "queued": None}
    max_workers = getattr(executor, "_max_workers", None)
    threads = getattr(executor, "_threads", None)
    work_queue = getattr(executor, "_work_queue", None)
    active = len(threads) if threads is not None else None
    try:
        queued = work_queue.qsize() if work_queue is not None else None
    except NotImplementedError:
        queued = None
    return {
        "max_workers": max_workers,
        "active_threads": active,
        "queued": queued,
    }
