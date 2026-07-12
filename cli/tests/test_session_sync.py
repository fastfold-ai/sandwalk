from datetime import UTC, datetime
from pathlib import Path

from agent.trajectory import Trajectory
from agent_server.session_sync import import_trajectory, sync_jsonl_sessions
from agent_server.store import AgentStore


def test_ensure_session_reuses_custom_id(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    first = store.ensure_session("abc12345", title="CLI chat")
    second = store.ensure_session("abc12345", title="CLI chat")
    assert first.id == "abc12345"
    assert second.id == first.id
    assert store.list_sessions()[0].title == "CLI chat"


def test_sync_imports_jsonl_sessions(tmp_path: Path, monkeypatch):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(Trajectory, "sessions_dir", staticmethod(lambda: sessions_dir))

    trajectory = Trajectory(session_id="deadbeef", title="Fold example")
    trajectory.add_turn("run a fold", "Submitted job abc")
    trajectory.add_turn("status?", "Still running")
    trajectory.save()

    store = AgentStore(tmp_path / "agent.db")
    result = sync_jsonl_sessions(store, sessions_dir=sessions_dir)
    assert result.scanned == 1
    assert result.imported == 1
    assert result.failed == 0

    session = store.get_session("deadbeef")
    assert session is not None
    assert session.title == "Fold example"
    messages = store.list_messages("deadbeef")
    assert [message.role for message in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[0].content == "run a fold"
    assert messages[1].content == "Submitted job abc"

    # Second sync should skip unchanged sessions.
    again = sync_jsonl_sessions(store, sessions_dir=sessions_dir)
    assert again.imported == 0
    assert again.skipped == 1

    # Force re-import.
    forced = sync_jsonl_sessions(store, sessions_dir=sessions_dir, force=True)
    assert forced.updated == 1
    assert len(store.list_messages("deadbeef")) == 4


def test_import_trajectory_preserves_timestamps(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    trajectory = Trajectory(session_id="cafebabe", title="Timed")
    trajectory.created_at = 1_700_000_000
    trajectory.updated_at = 1_700_000_100
    trajectory.add_turn("hello", "world")
    trajectory.turns[0].timestamp = 1_700_000_050

    assert import_trajectory(store, trajectory) == "imported"
    messages = store.list_messages("cafebabe")
    assert messages[0].created_at == datetime.fromtimestamp(1_700_000_050, tz=UTC)
    assert messages[1].created_at == datetime.fromtimestamp(1_700_000_051, tz=UTC)
