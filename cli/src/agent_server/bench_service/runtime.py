"""Dedicated asyncio loop + thread pool for bench agent runs.

Bench cells used to hop onto the uvicorn loop (``call_soon_threadsafe``) and
then occupy the process default executor for the entire LLM run via
``asyncio.to_thread``. Dashboard HTTP handlers share that executor, so the UI
felt stuck even while CPU and RAM sat idle.

This sidecar loop owns bench ``_execute_run`` tasks and a large I/O-bound
pool sized from local cores. Chat / API stay on uvicorn's own executor.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None
_executor: ThreadPoolExecutor | None = None
_thread: threading.Thread | None = None
_ready = threading.Event()
_stopping = threading.Event()


def api_executor_workers() -> int:
    """HTTP ``asyncio.to_thread`` pool — keep this off the bench workload."""
    cpus = os.cpu_count() or 4
    return max(16, min(32, cpus + 8))


def bench_executor_workers() -> int:
    """I/O-bound agent runs: oversubscribe so local hardware can fill LLM waits."""
    cpus = os.cpu_count() or 4
    return max(32, min(128, cpus * 8))


def bench_loop() -> asyncio.AbstractEventLoop | None:
    loop = _loop
    if loop is None or not loop.is_running():
        return None
    return loop


def is_bench_stopping() -> bool:
    return _stopping.is_set()


def start_bench_runtime() -> None:
    """Start the sidecar loop once per serve process."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive() and bench_loop() is not None:
            return
        _ready.clear()
        _stopping.clear()
        _thread = threading.Thread(
            target=_run_loop,
            name="sandwalk-bench-loop",
            daemon=True,
        )
        _thread.start()
    if not _ready.wait(5):
        raise RuntimeError("Bench runtime failed to start")
    deadline = time.monotonic() + 2
    while bench_loop() is None and time.monotonic() < deadline:
        time.sleep(0.01)


def stop_bench_runtime(*, timeout: float = 8.0) -> None:
    """Ask inflight suites to pause, then stop the sidecar loop."""
    global _loop, _executor, _thread
    _stopping.set()
    try:
        from agent_server.bench_service.queue_runner import request_bench_shutdown

        threads = request_bench_shutdown()
    except Exception:  # noqa: BLE001
        threads = []
    deadline = time.monotonic() + min(4.0, timeout)
    for thread in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        thread.join(timeout=remaining)

    loop = _loop
    thread = _thread
    if loop is None or not loop.is_running():
        if thread is not None:
            thread.join(timeout=timeout)
        _clear()
        return

    def _halt() -> None:
        tasks = [
            task
            for task in asyncio.all_tasks(loop)
            if task is not asyncio.current_task(loop)
        ]
        for task in tasks:
            task.cancel()

        async def _drain() -> None:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            loop.stop()

        loop.create_task(_drain())

    loop.call_soon_threadsafe(_halt)
    if thread is not None:
        thread.join(timeout=timeout)
    _clear()


def _clear() -> None:
    global _loop, _executor, _thread
    _loop = None
    _executor = None
    _thread = None
    _ready.clear()
    _stopping.clear()


def _run_loop() -> None:
    global _loop, _executor
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    executor = ThreadPoolExecutor(
        max_workers=bench_executor_workers(),
        thread_name_prefix="sandwalk-bench",
    )
    loop.set_default_executor(executor)
    _loop = loop
    _executor = executor

    def _mark_ready() -> None:
        _ready.set()

    loop.call_soon(_mark_ready)
    logger.info(
        "Bench runtime started (%s agent workers)",
        bench_executor_workers(),
    )
    try:
        loop.run_forever()
    finally:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception:  # noqa: BLE001
            logger.debug("Bench executor shutdown failed", exc_info=True)
        try:
            loop.close()
        except Exception:  # noqa: BLE001
            logger.debug("Bench loop close failed", exc_info=True)
        logger.info("Bench runtime stopped")
