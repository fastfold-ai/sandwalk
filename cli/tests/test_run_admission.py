"""The agent-run gate: slot cap, memory floor, queue messages, timeouts."""

from __future__ import annotations

import threading
import time

import pytest

from agent_server.run_admission import (
    DEFAULT_MIN_FREE_MB,
    RunAdmission,
    available_memory_mb,
    default_max_runs,
    total_memory_mb,
)


def test_defaults_scale_with_cores(monkeypatch):
    monkeypatch.delenv("SANDWALK_MAX_CONCURRENT_RUNS", raising=False)
    gate = RunAdmission(memory_probe=lambda: None)
    assert gate.max_runs() == default_max_runs()
    assert 4 <= gate.max_runs() <= 16
    assert gate.min_free_mb() == DEFAULT_MIN_FREE_MB


def test_env_overrides_win(monkeypatch):
    monkeypatch.setenv("SANDWALK_MAX_CONCURRENT_RUNS", "3")
    monkeypatch.setenv("SANDWALK_MIN_FREE_MEMORY_MB", "512")
    gate = RunAdmission(max_runs=10, min_free_mb=9000, memory_probe=lambda: None)
    assert gate.max_runs() == 3
    assert gate.min_free_mb() == 512


def test_slot_cap_queues_the_extra_run(monkeypatch):
    monkeypatch.delenv("SANDWALK_MAX_CONCURRENT_RUNS", raising=False)
    gate = RunAdmission(max_runs=2, min_free_mb=0, memory_probe=lambda: None)
    gate.acquire()
    gate.acquire()
    messages: list[str] = []
    started = threading.Event()
    entered = threading.Event()

    def third():
        started.set()
        gate.acquire(on_wait=messages.append, timeout_s=5)
        entered.set()

    thread = threading.Thread(target=third)
    thread.start()
    started.wait(1)
    time.sleep(0.2)
    assert not entered.is_set()
    assert gate.snapshot().queued == 1
    assert messages and "2 of 2 running" in messages[0]
    gate.release()
    assert entered.wait(2)
    snap = gate.snapshot()
    assert snap.running == 2
    assert snap.queued == 0
    gate.release()
    gate.release()
    thread.join(1)


def test_memory_floor_blocks_until_memory_returns(monkeypatch):
    monkeypatch.delenv("SANDWALK_MIN_FREE_MEMORY_MB", raising=False)
    free = {"mb": 1000}
    gate = RunAdmission(max_runs=8, min_free_mb=2048, memory_probe=lambda: free["mb"])
    messages: list[str] = []
    entered = threading.Event()

    def run():
        gate.acquire(on_wait=messages.append, timeout_s=5)
        entered.set()

    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.2)
    assert not entered.is_set()
    assert messages and "Waiting for memory" in messages[0]
    free["mb"] = 8000
    assert entered.wait(2)
    gate.release()
    thread.join(1)


def test_queue_timeout_raises_a_clear_error(monkeypatch):
    monkeypatch.delenv("SANDWALK_MAX_CONCURRENT_RUNS", raising=False)
    gate = RunAdmission(max_runs=1, min_free_mb=0, memory_probe=lambda: None)
    gate.acquire()
    with pytest.raises(TimeoutError, match="Max concurrent runs"):
        gate.acquire(timeout_s=0.3)
    assert gate.snapshot().queued == 0
    gate.release()


def test_configure_wakes_waiters(monkeypatch):
    monkeypatch.delenv("SANDWALK_MAX_CONCURRENT_RUNS", raising=False)
    gate = RunAdmission(max_runs=1, min_free_mb=0, memory_probe=lambda: None)
    gate.acquire()
    entered = threading.Event()
    thread = threading.Thread(target=lambda: (gate.acquire(timeout_s=5), entered.set()))
    thread.start()
    time.sleep(0.1)
    gate.configure(max_runs=2, min_free_mb=0)
    assert entered.wait(2)
    gate.release()
    gate.release()
    thread.join(1)


def test_memory_probes_return_plausible_numbers():
    available = available_memory_mb()
    total = total_memory_mb()
    if available is not None:
        assert available > 0
    if total is not None:
        assert total > 1024
    if available is not None and total is not None:
        assert available <= total
