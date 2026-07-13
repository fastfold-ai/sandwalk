"""Unit tests for AgentService workspace helpers and title helpers."""

from __future__ import annotations

from pathlib import Path

from agent_server.service import (
    AgentService,
    default_workspace_path,
    prepare_workspace_dir,
    resolve_session_workspace,
)
from agent_server.store import AgentStore
from agent_server.title import (
    fallback_title_from_query,
    is_placeholder_title,
    sanitize_generated_title,
)


def test_default_and_prepare_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    path = default_workspace_path("abc12345")
    assert path.name == "abc12345"
    prepared = prepare_workspace_dir(path)
    assert prepared.is_dir()
    assert (prepared / "artifacts").is_dir()
    assert (prepared / "outputs").is_dir()
    assert (prepared / "uploads").is_dir()


def test_resolve_session_workspace_persists(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    workspace = resolve_session_workspace("sess99", store=store, persist=True)
    assert workspace.exists()
    session = store.get_session("sess99")
    assert session is not None
    assert Path(session.workspace_path) == workspace

    again = resolve_session_workspace("sess99", store=store, persist=True)
    assert again == workspace


def test_agent_service_ensure_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    store.ensure_session("svc01", title="Workspace")
    service = AgentService(store)
    session = service.ensure_workspace("svc01")
    assert session.workspace_path
    assert Path(session.workspace_path).is_dir()
    assert (Path(session.workspace_path) / "artifacts").is_dir()


def test_title_helpers():
    assert is_placeholder_title("New research session")
    assert is_placeholder_title("untitled")
    assert not is_placeholder_title("Fold TP53")
    assert sanitize_generated_title('"Hello World"') == "Hello World"
    assert fallback_title_from_query("  fold this protein  ") == "fold this protein"
    long = "x" * 100
    assert len(fallback_title_from_query(long)) <= 64
