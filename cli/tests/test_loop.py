"""Tests for AgentLoop session resume behavior."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.loop import AgentLoop  # type: ignore[import-untyped]
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
