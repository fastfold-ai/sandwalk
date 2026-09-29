from __future__ import annotations

import asyncio
import gc
import warnings
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_server.app import create_app
from agent_server.routes.events_mux import (
    parse_after_cursors,
    parse_session_ids,
    wait_lifecycle_or_wake,
)


def test_parse_session_ids_dedupes_and_caps() -> None:
    ids = parse_session_ids(" a, a, b, ,c ")
    assert ids == ["a", "b", "c"]
    many = parse_session_ids(",".join(str(i) for i in range(100)))
    assert len(many) == 64
    # A 4x4 grid plus the registered active chat must all fit.
    grid = parse_session_ids(",".join(f"s{i}" for i in range(17)))
    assert len(grid) == 17


def test_parse_after_cursors() -> None:
    assert parse_after_cursors("s1:12,s2:0,bad,s3:x") == {"s1": 12, "s2": 0}


def test_health_advertises_event_mux(tmp_path: Path) -> None:
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        body = client.get("/v1/health").json()
        assert body["capabilities"]["eventMux"] is True


def test_wait_lifecycle_or_wake_cancels_children_when_caller_is_cancelled():
    """SSE client drops mid-wait: no pending Queue.get() task may survive."""

    async def _run():
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def never_wakes():
            await asyncio.sleep(3600)
            return None

        racer = asyncio.create_task(wait_lifecycle_or_wake(queue.get(), never_wakes()))
        await asyncio.sleep(0)  # let both children start
        before = {t for t in asyncio.all_tasks() if t is not racer}
        racer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await racer
        await asyncio.sleep(0)
        leftover = [
            t
            for t in asyncio.all_tasks()
            if t in before and not t.done() and t is not asyncio.current_task()
        ]
        return leftover

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # "Task was destroyed but it is pending" → fail
        leftover = asyncio.run(_run())
        gc.collect()
    assert leftover == []


def test_wait_lifecycle_or_wake_returns_winner_only():
    async def _lifecycle_wins():
        queue: asyncio.Queue[dict] = asyncio.Queue()
        queue.put_nowait({"type": "session.updated", "sequence": 7})

        async def slow():
            await asyncio.sleep(1)
            return {"s1": 2}

        return await wait_lifecycle_or_wake(queue.get(), slow())

    async def _wake_wins():
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def fast():
            return {"s1": 3}

        return await wait_lifecycle_or_wake(queue.get(), fast())

    assert asyncio.run(_lifecycle_wins()) == ({"type": "session.updated", "sequence": 7}, None)
    assert asyncio.run(_wake_wins()) == (None, {"s1": 3})


def test_mux_reads_only_sessions_whose_generation_moved(tmp_path: Path) -> None:
    """16 streaming panes must not turn every token into 16 DB reads."""
    import threading

    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        store = app.state.store
        ids = [
            store.create_session(title=f"s{i}", workspace_path=str(tmp_path / f"ws{i}")).id
            for i in range(3)
        ]
        reads: dict[str, int] = dict.fromkeys(ids, 0)
        real_list_events = store.list_events

        def counting_list_events(session_id, *args, **kwargs):
            reads[session_id] = reads.get(session_id, 0) + 1
            return real_list_events(session_id, *args, **kwargs)

        store.list_events = counting_list_events  # type: ignore[method-assign]

        hot = ids[0]
        n_events = 8
        stop = threading.Event()

        def writer():
            # Wait for the stream's first pass, then append only to `hot`.
            stop.wait(0.3)
            for i in range(n_events):
                store.append_event(
                    session_id=hot,
                    event_type="assistant.delta",
                    payload={"text": f"tok{i}"},
                )
                stop.wait(0.02)

        threading.Thread(target=writer, daemon=True).start()
        # TestClient hands over the streamed body only once the generator
        # ends, and it can't signal a client disconnect — so a timer ends the
        # stream via the app's shutdown flag well before the 5 s full sweep.
        shutdown = app.state.shutdown_event
        from agent_server.store.event_notifier import EVENT_NOTIFIER

        def _end_stream():
            shutdown.set()
            EVENT_NOTIFIER.wake_all()

        threading.Timer(1.5, _end_stream).start()
        with client.stream("GET", "/v1/events", params={"sessions": ",".join(ids)}) as resp:
            body = "".join(resp.iter_text())
        got = body.count('"channel":"transcript"')

    assert got == n_events
    # Hot session was re-read as its generation advanced (wakes may coalesce
    # a couple of appends, so allow fewer reads than events).
    assert reads[hot] >= 3, reads
    # Cold sessions: the initial pass only — a token elsewhere must not
    # trigger a read here (no 5 s sweep elapsed in-test).
    for sid in ids[1:]:
        assert reads[sid] == 1, reads
