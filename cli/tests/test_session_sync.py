from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent.loop import AgentLoop
from agent.trajectory import Trajectory
from agent_server.session_sync import (
    export_store_to_trajectory,
    import_trajectory,
    sync_jsonl_sessions,
)
from agent_server.store import AgentStore


def test_ensure_session_reuses_custom_id(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    first = store.ensure_session("abc12345", title="CLI chat")
    second = store.ensure_session("abc12345", title="CLI chat")
    assert first.id == "abc12345"
    assert second.id == first.id
    assert store.list_sessions()[0].title == "CLI chat"


def test_ensure_session_does_not_clobber_real_title(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    store.ensure_session("title01", title="KRAS binder screen")
    store.ensure_session("title01", title="New research session")
    assert store.get_session("title01").title == "KRAS binder screen"


def test_ensure_session_upgrades_placeholder_title(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    store.ensure_session("title02", title="New research session")
    store.ensure_session("title02", title="Glioblastoma kinases")
    assert store.get_session("title02").title == "Glioblastoma kinases"


def test_ensure_workspace_preserves_session_title(tmp_path: Path, monkeypatch):
    from agent_server.service import AgentService, resolve_session_workspace

    store = AgentStore(tmp_path / "agent.db")
    store.ensure_session("ws01", title="Fold EGFR")
    monkeypatch.setenv("HOME", str(tmp_path))
    resolve_session_workspace("ws01", store=store, persist=True)
    AgentService(store).ensure_workspace("ws01")
    assert store.get_session("ws01").title == "Fold EGFR"


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


def test_import_trajectory_mark_recent_bumps_activity(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    trajectory = Trajectory(session_id="forked01", title="Old cloud chat")
    trajectory.created_at = 1_600_000_000
    trajectory.updated_at = 1_600_000_100
    trajectory.add_turn("hello", "from the past")
    trajectory.turns[0].timestamp = 1_600_000_050

    assert import_trajectory(store, trajectory, mark_recent=True) == "imported"
    session = store.get_session("forked01")
    assert session is not None
    assert session.last_message_at is not None
    # Activity stamps should be "now", not the historical turn time.
    assert session.last_message_at.year >= 2026
    assert session.updated_at.year >= 2026
    assert abs((session.updated_at - session.last_message_at).total_seconds()) < 2
    # Message history keeps original chronology.
    messages = store.list_messages("forked01")
    assert messages[0].created_at == datetime.fromtimestamp(1_600_000_050, tz=UTC)


def test_export_store_to_trajectory_pulls_ui_turns(tmp_path: Path, monkeypatch):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(Trajectory, "sessions_dir", staticmethod(lambda: sessions_dir))

    store = AgentStore(tmp_path / "agent.db")
    store.ensure_session("uiahead01", title="Cross surface")
    store.add_message(session_id="uiahead01", role="user", content="cli first")
    store.add_message(session_id="uiahead01", role="assistant", content="cli answer")
    store.add_message(session_id="uiahead01", role="user", content="ui continued")
    store.add_message(
        session_id="uiahead01",
        role="assistant",
        content='Tell me which of the above you want, or say "nothing" to finish.',
    )

    trajectory = Trajectory(session_id="uiahead01", title="Cross surface")
    trajectory.add_turn("cli first", "cli answer")
    trajectory.save()
    assert len(trajectory.turns) == 1

    assert export_store_to_trajectory(store, trajectory) == "updated"
    assert len(trajectory.turns) == 2
    assert trajectory.turns[-1].query == "ui continued"
    assert "nothing" in trajectory.turns[-1].answer

    # Idempotent when already in sync.
    assert export_store_to_trajectory(store, trajectory) == "skipped"


def test_resume_pulls_ui_history_into_cli(tmp_path: Path, monkeypatch):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(Trajectory, "sessions_dir", staticmethod(lambda: sessions_dir))

    store = AgentStore(tmp_path / "agent.db")
    store.ensure_session("resume01", title="Resume me")
    store.add_message(session_id="resume01", role="user", content="from cli")
    store.add_message(session_id="resume01", role="assistant", content="cli reply")
    store.add_message(session_id="resume01", role="user", content="from ui")
    store.add_message(
        session_id="resume01",
        role="assistant",
        content='Tell me which of the above you want, or say "nothing" to finish.',
    )

    # Stale JSONL with only the CLI turn.
    traj = Trajectory(session_id="resume01", title="Resume me")
    traj.add_turn("from cli", "cli reply")
    traj.save()

    session = MagicMock()
    session.current_model = "claude-sonnet-4-5-20250929"
    session.config.get.return_value = "anthropic"

    with patch("agent.loop.AgentRunner"):
        loop = AgentLoop.resume(session, "resume01", store=store)

    assert len(loop.trajectory.turns) == 2
    assert loop.trajectory.turns[-1].query == "from ui"
    assert "nothing" in loop.trajectory.turns[-1].answer


def test_sessions_revision_moves_when_list_changes(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    try:
        empty = store.sessions_revision()
        assert empty.startswith("0:")
        store.create_session(title="One", workspace_path=None)
        one = store.sessions_revision()
        assert one.startswith("1:")
        assert one != empty
        store.create_session(title="Two", workspace_path=None)
        two = store.sessions_revision()
        assert two.startswith("2:")
        assert two != one
    finally:
        store.close()
