"""Bench event emission must not hit SQLite or the chat SSE bus per token."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from agent_server.service.emit_events import make_event_emitter
from agent_server.store import AgentStore
from agent_server.store.event_notifier import EVENT_NOTIFIER


def test_bench_stream_skips_get_session_after_seed():
    store = MagicMock()
    store.get_session.return_value = SimpleNamespace(status="running", source="bench")
    emit = make_event_emitter(store, "s", "r")
    store.get_session.reset_mock()
    emit("stream", delta="x")
    emit("activity", message="y")
    store.get_session.assert_not_called()
    store.append_event.assert_not_called()


def test_bench_stream_skips_sqlite_and_sse_notify(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        session = store.create_session(
            title="cell",
            workspace_path=None,
            source="bench",
        )
        store.set_session_status(session.id, "running")
        emit = make_event_emitter(store, session.id, "run-1")
        before = EVENT_NOTIFIER.generation(session.id)
        emit("stream", delta="hello")
        emit("stream", delta=" world")
        emit("activity", message="thinking")
        assert store.list_events(session.id) == []
        assert EVENT_NOTIFIER.generation(session.id) == before
        emit("tool_start", name="read", arguments={}, tool_call_id="t1")
        events = store.list_events(session.id)
        assert [event.type for event in events] == ["tool.started"]
        assert EVENT_NOTIFIER.generation(session.id) == before
    finally:
        store.close()
