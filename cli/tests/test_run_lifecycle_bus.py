from pathlib import Path
from unittest.mock import MagicMock

from agent_server.store import AgentStore


def test_run_completed_publishes_global_bus(tmp_path: Path, monkeypatch):
    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "agent_server.session_event_bus.session_event_bus.publish",
        lambda event_type, payload: seen.append((event_type, payload)),
    )
    store = AgentStore(tmp_path / "agent.db")
    session = store.create_session(
        title="From Slack",
        workspace_path=None,
        source="slack",
    )
    store.append_event(
        session_id=session.id,
        run_id="run-1",
        event_type="run.completed",
        payload={"messageId": "m1"},
    )
    types = [item[0] for item in seen]
    assert "run.completed" in types
    payload = next(item[1] for item in seen if item[0] == "run.completed")
    assert payload["sessionId"] == session.id
    assert payload["session"]["id"] == session.id


def test_bench_run_completed_stays_off_global_bus(tmp_path: Path, monkeypatch):
    publish = MagicMock()
    monkeypatch.setattr(
        "agent_server.session_event_bus.session_event_bus.publish",
        publish,
    )
    store = AgentStore(tmp_path / "agent.db")
    session = store.create_session(
        title="cell",
        workspace_path=None,
        source="bench",
    )
    store.append_event(
        session_id=session.id,
        event_type="run.completed",
        payload={},
    )
    publish.assert_not_called()
