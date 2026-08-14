"""Chat HTTP/SSE stays fast while bench cells run at full in-process capacity.

This is the isolation contract: many concurrent bench sessions may emit
tokens and tool events, but Dashboard health, session-list, and a live chat
turn must stay on a short local path. Failures here mean bench I/O leaked
back onto the API/SQLite/event bus.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from agent_server.app import create_app
from agent_server.service.emit_events import make_event_emitter


BENCH_WORKERS = 12
HEALTH_P95_MS = 40.0
REVISION_P95_MS = 80.0
POST_MS = 400.0
FIRST_DELTA_MS = 500.0
BUSY_409_MS = 80.0
MIN_BENCH_STREAMS = BENCH_WORKERS * 40


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    if not ordered:
        return 0.0
    index = max(0, int(round((len(ordered) - 1) * 0.95)))
    return ordered[index]


def _timed_ms(fn) -> tuple[float, object]:
    started = time.perf_counter()
    result = fn()
    return (time.perf_counter() - started) * 1000, result


def test_chat_stays_fast_under_full_bench_capacity(tmp_path: Path):
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        store = app.state.store
        service = app.state.agent_service

        project = client.post("/v1/projects", json={"name": "Bench flood"}).json()
        project_id = project["id"]
        for index in range(24):
            service.create_session(
                title=f"bench-cell-{index}",
                workspace_path=None,
                project_id=project_id,
                source="bench",
            )
        listed_ms, listed = _timed_ms(
            lambda: client.get("/v1/sessions", params={"projectId": project_id})
        )
        assert listed.status_code == 200
        assert len(listed.json()["data"]) == 24
        assert listed_ms < REVISION_P95_MS

        stop = threading.Event()
        ready = threading.Barrier(BENCH_WORKERS + 1)
        stream_counts = [0] * BENCH_WORKERS

        def _flood(index: int) -> None:
            session = service.create_session(
                title=f"cell-{index}",
                workspace_path=None,
                source="bench",
            )
            store.set_session_status(session.id, "running")
            emit = make_event_emitter(store, session.id, f"run-{index}")
            ready.wait()
            n = 0
            while not stop.is_set():
                emit("stream", delta="x")
                n += 1
                if n % 8 == 0:
                    emit(
                        "tool_start",
                        name="read",
                        arguments={"path": "BENCH_PROMPT.md"},
                        tool_call_id=f"t{n}",
                    )
                    emit(
                        "tool_end",
                        name="read",
                        output="ok",
                        is_error=False,
                        duration_s=0.01,
                        tool_call_id=f"t{n}",
                    )
            stream_counts[index] = n

        workers = [
            threading.Thread(target=_flood, args=(i,), daemon=True)
            for i in range(BENCH_WORKERS)
        ]
        for thread in workers:
            thread.start()
        ready.wait(timeout=5)

        health_samples = []
        revision_samples = []
        for _ in range(24):
            ms, response = _timed_ms(lambda: client.get("/v1/health"))
            assert response.status_code == 200
            health_samples.append(ms)
            ms, response = _timed_ms(lambda: client.get("/v1/sessions/revision"))
            assert response.status_code == 200
            revision_samples.append(ms)

        created = client.post("/v1/sessions", json={"title": "Live chat"})
        assert created.status_code == 201
        chat_id = created.json()["id"]
        hold = threading.Event()

        async def _fake_execute_run(
            *,
            session_id: str,
            run_id: str,
            content: str,
            workspace_path: str | None,
        ) -> None:
            emit = make_event_emitter(store, session_id, run_id)
            emit("stream", delta="hello")
            for _ in range(7):
                emit("stream", delta="!")
            while not hold.is_set():
                import asyncio

                await asyncio.sleep(0.01)
            service._finish_run(session_id, run_id, "done", content)

        service._execute_run = _fake_execute_run

        post_ms, posted = _timed_ms(
            lambda: client.post(
                f"/v1/sessions/{chat_id}/messages",
                json={"content": "hi"},
            )
        )
        assert posted.status_code == 202, posted.text
        assert post_ms < POST_MS, f"chat POST {post_ms:.1f}ms"

        deadline = time.perf_counter() + 2
        first_delta_ms = None
        while time.perf_counter() < deadline:
            events = store.list_events(chat_id)
            if any(event.type == "assistant.delta" for event in events):
                first_delta_ms = (time.perf_counter() - (deadline - 2)) * 1000
                break
            time.sleep(0.01)
        assert first_delta_ms is not None, "chat tokens never landed"
        assert first_delta_ms < FIRST_DELTA_MS, f"first chat delta {first_delta_ms:.1f}ms"

        busy_ms, busy = _timed_ms(
            lambda: client.post(
                f"/v1/sessions/{chat_id}/messages",
                json={"content": "so?"},
            )
        )
        assert busy.status_code == 409, busy.text
        assert busy_ms < BUSY_409_MS, f"busy 409 {busy_ms:.1f}ms"

        hold.set()
        stop.set()
        for thread in workers:
            thread.join(timeout=3)

        streamed = sum(stream_counts)
        assert streamed >= MIN_BENCH_STREAMS, f"bench only emitted {streamed} streams"
        assert _p95(health_samples) < HEALTH_P95_MS, (
            f"health p95 {_p95(health_samples):.1f}ms samples={health_samples[-5:]}"
        )
        assert _p95(revision_samples) < REVISION_P95_MS, (
            f"revision p95 {_p95(revision_samples):.1f}ms"
        )
