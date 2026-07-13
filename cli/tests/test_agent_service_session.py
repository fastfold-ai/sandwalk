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
    assert svc.interrupt(session.id) is True
    running.cancel.assert_called_once()

    done_task = MagicMock()
    done_task.done.return_value = True
    svc._active_runs[session.id] = done_task
    assert asyncio.run(svc.delete_session(session.id)) is True
    assert store.get_session(session.id) is None


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


def test_auto_title_session_skips_non_placeholder(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = store.create_session(title="Concrete title", workspace_path=None)

    monkeypatch.setattr(
        "agent_server.title.generate_session_title",
        lambda *args, **kwargs: "Should not apply",
    )
    result = svc.auto_title_session(session.id)
    assert result.title == "Concrete title"


def test_auto_title_session_generates(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    session = store.create_session(title="New research session", workspace_path=None)
    store.add_message(session_id=session.id, role="user", content="Fold TP53")

    monkeypatch.setattr(
        "agent_server.title.generate_session_title",
        lambda *args, **kwargs: "Fold TP53 study",
    )
    result = svc.auto_title_session(session.id)
    assert result.title == "Fold TP53 study"
