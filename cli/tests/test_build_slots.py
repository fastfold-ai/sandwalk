"""Agent-build CPU throttle: bounded concurrency, results preserved, env override."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from agent.runner import build_slots


@pytest.fixture(autouse=True)
def _restore_slots():
    yield
    build_slots._reset_for_tests(build_slots.build_concurrency())


def test_run_cpu_bound_limits_concurrency_and_returns_results():
    build_slots._reset_for_tests(2)
    active = 0
    peak = 0
    lock = threading.Lock()

    def work(i: int) -> int:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return i * 10

    async def _run():
        return await asyncio.gather(*[build_slots.run_cpu_bound(work, i) for i in range(6)])

    results = asyncio.run(_run())
    assert results == [0, 10, 20, 30, 40, 50]
    assert peak == 2


def test_slots_are_shared_across_event_loops():
    """Each agent run has its own loop/thread; the throttle must still apply."""
    build_slots._reset_for_tests(1)
    active = 0
    peak = 0
    lock = threading.Lock()

    def work() -> None:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        with lock:
            active -= 1

    threads = [
        threading.Thread(target=lambda: asyncio.run(build_slots.run_cpu_bound(work)))
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert peak == 1


def test_exceptions_release_the_slot():
    build_slots._reset_for_tests(1)

    def boom() -> None:
        raise RuntimeError("compile failed")

    with pytest.raises(RuntimeError):
        asyncio.run(build_slots.run_cpu_bound(boom))
    # Slot is free again: a follow-up call completes promptly.
    assert asyncio.run(build_slots.run_cpu_bound(lambda: "ok")) == "ok"


def test_build_concurrency_env_override(monkeypatch):
    monkeypatch.setenv("SANDWALK_BUILD_CONCURRENCY", "4")
    assert build_slots.build_concurrency() == 4
    monkeypatch.setenv("SANDWALK_BUILD_CONCURRENCY", "0")
    assert build_slots.build_concurrency() == 1
    monkeypatch.setenv("SANDWALK_BUILD_CONCURRENCY", "nope")
    assert build_slots.build_concurrency() == build_slots.DEFAULT_BUILD_CONCURRENCY
