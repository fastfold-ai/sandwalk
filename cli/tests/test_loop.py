"""Tests for AgentLoop session resume behavior."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.loop import AgentLoop  # type: ignore[import-untyped]
from agent_server.service import resolve_session_workspace
from agent_server.store import AgentStore


def _mock_session():
    session = MagicMock()
    session.current_model = "claude-sonnet-4-5-20250929"
    session.config.get.return_value = "anthropic"
    return session


def test_resume_resolves_id_to_session_path(tmp_path: Path):
    session = _mock_session()
    fake_path = Path("/tmp/abc12345.jsonl")
    fake_traj = MagicMock()
    fake_traj.session_id = "abc12345"
    fake_traj.title = "Test"
    fake_traj.turns = []
    store = AgentStore(tmp_path / "agent.db")

    with patch("agent.loop.Trajectory.resolve_session_path", return_value=fake_path) as mock_resolve, patch(
        "agent.loop.Trajectory.load", return_value=fake_traj
    ) as mock_load, patch("agent.loop.import_trajectory", return_value="skipped"):
        AgentLoop.resume(session, " abc12345 ", store=store)

    mock_resolve.assert_called_once_with("abc12345")
    mock_load.assert_called_once_with(fake_path)


def test_resume_empty_id_raises_not_found(tmp_path: Path):
    session = _mock_session()
    store = AgentStore(tmp_path / "agent.db")
    with pytest.raises(FileNotFoundError):
        AgentLoop.resume(session, "   ", store=store)


def test_resolve_session_workspace_creates_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "agent_server.service.CONFIG_DIR", tmp_path / "cfg"
    )
    store = AgentStore(tmp_path / "agent.db")
    workspace = resolve_session_workspace("sess001", store=store, persist=True)
    assert workspace.exists()
    assert (workspace / "artifacts").is_dir()
    assert (workspace / "outputs").is_dir()
    session = store.get_session("sess001")
    assert session is not None
    assert Path(session.workspace_path) == workspace


def test_agent_loop_injects_workspace_into_run_context(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "agent_server.service.CONFIG_DIR", tmp_path / "cfg"
    )
    session = _mock_session()
    store = AgentStore(tmp_path / "agent.db")
    loop = AgentLoop(session, store=store, session_id="cliws01")

    captured = {}

    def fake_run(query, context, progress_callback=None):
        captured["context"] = dict(context or {})
        if progress_callback:
            progress_callback(
                "tool_start",
                name="shell.run",
                arguments={"command": "pwd"},
                tool_call_id="tool-1",
            )
            progress_callback(
                "tool_end",
                name="shell.run",
                output="ok",
                is_error=False,
                duration_s=0.1,
                tool_call_id="tool-1",
            )
        result = MagicMock()
        result.summary = "ok"
        result.plan = None
        result.raw_results = None
        return result

    loop._runner.run = fake_run  # type: ignore[method-assign]
    loop.run("download all", {})

    ws = captured["context"].get("workspace_path")
    assert ws
    assert Path(ws).is_dir()
    assert (Path(ws) / "artifacts").is_dir()
    assert "cliws01" in ws

    events = store.list_events("cliws01")
    types = [event.type for event in events]
    assert "run.started" in types
    assert "tool.started" in types
    assert "tool.completed" in types
    assert "assistant.message" in types
    assert "run.completed" in types
    messages = store.list_messages("cliws01")
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


def test_agent_loop_skips_title_llm_on_error_result(tmp_path: Path, monkeypatch):
    """Rate-limit / provider errors must not call the title model (can hang)."""
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    session = _mock_session()
    store = AgentStore(tmp_path / "agent.db")
    loop = AgentLoop(session, store=store, session_id="errtitle1")
    loop.headless = False
    called = {"title": 0}

    def fake_run(query, context, progress_callback=None):
        if progress_callback:
            progress_callback("turn_complete")
        result = MagicMock()
        result.summary = "Agent SDK error: Rate limited: upstream"
        result.plan = None
        result.raw_results = {"error": "Rate limited: upstream"}
        return result

    def boom_title(*_a, **_k):
        called["title"] += 1
        raise AssertionError("title LLM should be skipped on error results")

    loop._runner.run = fake_run  # type: ignore[method-assign]
    loop._generate_title = boom_title  # type: ignore[method-assign]
    out = loop.run("hi", {})
    assert called["title"] == 0
    assert out.raw_results["error"]
    assert loop.trajectory.title  # fallback title still set
