"""Off-loop execution helper for Modal's blocking sync client."""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable
from typing import TypeVar

# Modal sync APIs must not run on a thread that already has an asyncio loop
# (LangGraph / FastAPI). Offload to this pool so Modal's client sees a plain
# sync context and we avoid AsyncUsageWarning + event-loop stalls.
_MODAL_IO_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="sandwalk-modal",
)
_T = TypeVar("_T")


def _run_modal_blocking(fn: Callable[[], _T]) -> _T:
    """Run Modal-blocking work off the asyncio event-loop thread when needed."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return fn()
    return _MODAL_IO_EXECUTOR.submit(fn).result()
