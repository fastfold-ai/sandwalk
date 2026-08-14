"""Dedicated bench sidecar loop stays off the API event loop."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

from agent_server.bench_service.runtime import (
    bench_executor_workers,
    bench_loop,
    start_bench_runtime,
    stop_bench_runtime,
)
from agent_server.service import AgentService
from agent_server.store import AgentStore


def test_bench_runtime_start_stop():
    start_bench_runtime()
    try:
        loop = bench_loop()
        assert loop is not None
        assert loop.is_running()
        hit = threading.Event()
        loop.call_soon_threadsafe(hit.set)
        assert hit.wait(2)
        assert bench_executor_workers() >= 32
    finally:
        stop_bench_runtime()
    assert bench_loop() is None


def test_bench_session_runs_on_sidecar_loop(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    start_bench_runtime()
    sidecar = bench_loop()
    assert sidecar is not None
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(
        title="Bench cell",
        workspace_path=None,
        source="bench",
    )
    seen: dict[str, object] = {}

    async def _fake_execute_run(**_kwargs):
        seen["loop"] = asyncio.get_running_loop()
        return None

    monkeypatch.setattr(svc, "_execute_run", _fake_execute_run)
    try:
        started = svc.submit_message(session_id=session.id, content="hello")
        assert started.run_id
        for _ in range(200):
            if "loop" in seen:
                break
            time.sleep(0.01)
        assert seen.get("loop") is sidecar
    finally:
        stop_bench_runtime()
        store.close()
