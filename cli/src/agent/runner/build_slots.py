"""Bound how many agent builds burn CPU at once.

Building a deep agent is CPU-bound Python (tool schema generation, graph
compile: ~0.25 s alone). Under the GIL, N concurrent builds don't finish any
sooner in aggregate — they just time-slice, so *every* run's build stretches
to roughly N× (measured: 0.25 s alone → 1.9–3.1 s with 4 runs) and the API
event loop, SSE streams and health checks starve in the meantime.

Funnelling builds through a small semaphore keeps total throughput the same
while letting the first runs start streaming immediately and the event loop
stay responsive. The semaphore is a *threading* primitive because each agent
run drives its own event loop in its own thread.
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Callable
from typing import Any, TypeVar

DEFAULT_BUILD_CONCURRENCY = 2
_ENV = "SANDWALK_BUILD_CONCURRENCY"

T = TypeVar("T")


def build_concurrency() -> int:
    raw = os.environ.get(_ENV, "").strip()
    try:
        value = int(raw) if raw else DEFAULT_BUILD_CONCURRENCY
    except ValueError:
        value = DEFAULT_BUILD_CONCURRENCY
    return max(1, value)


_slots = threading.BoundedSemaphore(build_concurrency())


async def run_cpu_bound(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run ``fn`` in a worker thread, holding one build slot while it executes.

    Waiting for a slot happens inside the worker (GIL released), never on the
    caller's event loop. Contextvars propagate like ``asyncio.to_thread``.
    """

    def _guarded() -> T:
        with _slots:
            return fn(*args, **kwargs)

    return await asyncio.to_thread(_guarded)


def _reset_for_tests(limit: int) -> None:
    global _slots
    _slots = threading.BoundedSemaphore(max(1, limit))
