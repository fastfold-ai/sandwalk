"""Additional AgentService session lifecycle tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_server.service import AgentService, SessionBusyError
from agent_server.store import AgentStore


def test_create_session_with_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    workspace = tmp_path / "project-ws"
    workspace.mkdir()

    session = svc.create_session(
        title="Lab session",
        workspace_path=str(workspace),
    )
    assert session.title == "Lab session"
    assert Path(session.workspace_path) == workspace.resolve()
    events = store.list_events(session.id)
    assert any(event.type == "session.created" for event in events)


def test_create_session_default_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(title="Auto ws", workspace_path=None)
    assert session.workspace_path
    assert Path(session.workspace_path).is_dir()


def test_create_session_rejects_missing_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    with pytest.raises(ValueError, match="does not exist"):
        svc.create_session(title="Bad", workspace_path=str(tmp_path / "nope"))


def test_update_session_emits_event(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(title="Old", workspace_path=None)
    updated = svc.update_session(
        session_id=session.id,
        title="New title",
        organize_label="pinned",
        update_organize_label=True,
    )
    assert updated.title == "New title"
    assert updated.organize_label == "pinned"
    assert any(
        event.type == "session.updated" for event in store.list_events(session.id)
    )


def test_interrupt_and_delete_session(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(title="Del", workspace_path=None)

    assert svc.interrupt(session.id) is False

    running = MagicMock()
    running.done.return_value = False
    running.cancel = MagicMock()
    svc._active_runs[session.id] = running
    store.set_session_status(session.id, "running")
    assert svc.interrupt(session.id) is True
    running.cancel.assert_called_once()
    assert store.get_session(session.id).status == "interrupted"

    done_task = MagicMock()
    done_task.done.return_value = True
    svc._active_runs[session.id] = done_task
    assert asyncio.run(svc.delete_session(session.id)) is True
    assert store.get_session(session.id) is None


def test_interrupt_clears_orphaned_running_session(tmp_path: Path, monkeypatch):
    """Stop must unstick sessions left running with no live worker task."""
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(title="Orphan", workspace_path=None)
    store.set_session_status(session.id, "running")

    assert session.id not in svc._active_runs
    assert svc.interrupt(session.id) is True
    updated = store.get_session(session.id)
    assert updated is not None
    assert updated.status == "interrupted"
    events = store.list_events(session.id)
    assert any(event.type == "run.interrupted" for event in events)


def test_submit_message_clear_run_and_shutdown(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(title="Run", workspace_path=None)

    async def _fake_execute_run(**_kwargs):
        return None

    monkeypatch.setattr(svc, "_execute_run", _fake_execute_run)

    async def _run_submit():
        started = svc.submit_message(session_id=session.id, content="hello")
        assert started.run_id
        assert session.id in svc._active_runs
        assert store.get_session(session.id).status == "running"
        await svc._active_runs[session.id]
        # Done-callback should clear the active run.
        await asyncio.sleep(0)
        assert session.id not in svc._active_runs

    asyncio.run(_run_submit())

    # Shutdown cancels any leftover tasks.
    leftover = MagicMock()
    leftover.done.return_value = False
    leftover.cancel = MagicMock()
    svc._active_runs[session.id] = leftover

    async def _gather(*_a, **_k):
        return []

    monkeypatch.setattr(asyncio, "gather", _gather)
    asyncio.run(svc.shutdown())
    leftover.cancel.assert_called()


def test_clear_run_handles_cancelled_and_errors(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(title="Clear", workspace_path=None)

    cancelled = MagicMock()
    cancelled.result.side_effect = asyncio.CancelledError()
    svc._active_runs[session.id] = cancelled
    svc._run_ids[session.id] = "run-x"
    svc._clear_run(session.id, cancelled)
    assert session.id not in svc._active_runs

    failed = MagicMock()
    failed.result.side_effect = RuntimeError("boom")
    svc._active_runs[session.id] = failed
    svc._run_ids[session.id] = "run-y"
    svc._clear_run(session.id, failed)
    assert session.id not in svc._active_runs


def test_submit_message_validations(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(title="Run", workspace_path=None)

    with pytest.raises(ValueError, match="empty"):
        svc.submit_message(session_id=session.id, content="   ")

    with pytest.raises(KeyError):
        svc.submit_message(session_id="missing", content="hi")


def test_submit_message_busy_guard(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(title="Busy", workspace_path=None)

    active = MagicMock()
    active.done.return_value = False
    svc._active_runs[session.id] = active
    with pytest.raises(SessionBusyError):
        svc.submit_message(session_id=session.id, content="hello")


def test_auto_title_session_skips_settled_user_title(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = store.create_session(title="Concrete title", workspace_path=None)
    assert session.title_source == "user"

    monkeypatch.setattr(
        "agent_server.title.generate_session_title",
        lambda *args, **kwargs: __import__(
            "agent_server.title", fromlist=["TitleResult"]
        ).TitleResult(title="Should not apply", final=True),
    )
    result = svc.auto_title_session(session.id)
    assert result.title == "Concrete title"
    assert result.title_source == "user"


def test_create_untitled_session_stays_pending_for_auto_title(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    # Desktop historically created chats with this placeholder title.
    session = store.create_session(title="Untitled session", workspace_path=None)
    assert session.title_source == "pending"

    store.add_message(session_id=session.id, role="user", content="Fold 4KW4")
    store.add_message(session_id=session.id, role="assistant", content="Folding.")
    store.add_message(session_id=session.id, role="user", content="Show pLDDT")
    store.add_message(session_id=session.id, role="assistant", content="High.")

    monkeypatch.setattr(
        "agent_server.title.generate_session_title",
        lambda *args, **kwargs: __import__(
            "agent_server.title", fromlist=["TitleResult"]
        ).TitleResult(title="Fold 4KW4", final=True),
    )
    result = svc.auto_title_session(session.id)
    assert result.title == "Fold 4KW4"
    assert result.title_source == "auto"


def test_auto_title_heals_placeholder_marked_as_user(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = store.create_session(title="Untitled session", workspace_path=None)
    # Simulate the pre-fix bug: placeholder stuck as a settled user title.
    stuck = store.update_session(
        session.id, title="Untitled session", title_source="user"
    )
    assert stuck is not None
    assert stuck.title_source == "user"

    store.add_message(session_id=session.id, role="user", content="Design a binder")
    store.add_message(session_id=session.id, role="assistant", content="Designing.")
    store.add_message(session_id=session.id, role="user", content="Rank designs")
    store.add_message(session_id=session.id, role="assistant", content="Ranked.")

    monkeypatch.setattr(
        "agent_server.title.generate_session_title",
        lambda *args, **kwargs: __import__(
            "agent_server.title", fromlist=["TitleResult"]
        ).TitleResult(title="Binder design", final=True),
    )
    result = svc.auto_title_session(session.id)
    assert result.title == "Binder design"
    assert result.title_source == "auto"


def test_auto_title_session_uses_interim_fallback_before_four_messages(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = store.create_session(title="New research session", workspace_path=None)
    assert session.title_source == "pending"
    store.add_message(session_id=session.id, role="user", content="Fold TP53")

    monkeypatch.setattr(
        "agent_server.title.generate_session_title",
        lambda *args, **kwargs: __import__(
            "agent_server.title", fromlist=["TitleResult"]
        ).TitleResult(title="Should not call yet", final=True),
    )
    result = svc.auto_title_session(session.id)
    assert result.title == "Fold TP53"
    assert result.title_source == "pending"


def test_auto_title_session_generates_after_four_messages(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = store.create_session(title="New research session", workspace_path=None)
    store.add_message(session_id=session.id, role="user", content="Fold TP53")
    store.add_message(session_id=session.id, role="assistant", content="Folding now.")
    store.add_message(session_id=session.id, role="user", content="Also check PAE")
    store.add_message(session_id=session.id, role="assistant", content="PAE looks good.")

    monkeypatch.setattr(
        "agent_server.title.generate_session_title",
        lambda *args, **kwargs: __import__(
            "agent_server.title", fromlist=["TitleResult"]
        ).TitleResult(title="Fold TP53 study", final=True),
    )
    result = svc.auto_title_session(session.id)
    assert result.title == "Fold TP53 study"
    assert result.title_source == "auto"


def test_manual_rename_marks_title_source_user(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = store.create_session(title="New research session", workspace_path=None)
    renamed = svc.update_session(
        session_id=session.id,
        title="My custom name",
        organize_label=None,
        update_organize_label=False,
    )
    assert renamed.title == "My custom name"
    assert renamed.title_source == "user"
    again = svc.auto_title_session(session.id, force=True)
    assert again.title == "My custom name"
    assert again.title_source == "user"


def test_compact_session_summarizes_older_turns(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(title="Compact me", workspace_path=None)
    for index in range(1, 4):
        store.add_message(
            session_id=session.id, role="user", content=f"query {index}"
        )
        store.add_message(
            session_id=session.id, role="assistant", content=f"answer {index}"
        )

    class _FakeLLM:
        def chat(self, **_kwargs):
            return MagicMock(content="Compressed findings about queries 1-2.")

    class _FakeSession:
        def __init__(self, **_kwargs):
            pass

        def get_llm(self):
            return _FakeLLM()

    monkeypatch.setattr("agent.config.Config.load", classmethod(lambda cls: MagicMock()))
    monkeypatch.setattr("agent.session.Session", _FakeSession)

    result = svc.compact_session(session.id)
    assert result.turns_before == 3
    assert result.turns_after == 2
    messages = store.list_messages(session.id)
    assert len(messages) == 4
    assert messages[0].content == "[session summary]"
    assert "Compressed findings" in messages[1].content
    assert messages[2].content == "query 3"
    assert messages[3].content == "answer 3"


def test_compact_session_rejects_short_history(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = svc.create_session(title="Short", workspace_path=None)
    store.add_message(session_id=session.id, role="user", content="q1")
    store.add_message(session_id=session.id, role="assistant", content="a1")
    with pytest.raises(ValueError, match="too short"):
        svc.compact_session(session.id)
