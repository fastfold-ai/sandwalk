"""Fork command syncs imported cloud chats into the Web UI store."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from agent.trajectory import Trajectory
from agent_server.store import AgentStore
from cli import app


def test_fork_command_imports_into_agent_store(tmp_path: Path, monkeypatch):
    cfg_dir = tmp_path / "cfg"
    sessions_dir = cfg_dir / "sessions"
    cfg_dir.mkdir(parents=True)
    sessions_dir.mkdir()

    monkeypatch.setattr("agent.config.CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(Trajectory, "sessions_dir", staticmethod(lambda: sessions_dir))

    share_id = "4af3fa102a5241ce9436f982508ba709"
    bootstrap = {
        "thread": {
            "id": "thread-cloud-1",
            "title": "Forked cloud chat",
            "metadata": {"inspect_base_model_key": "claude-sonnet"},
        }
    }
    history = {
        "messages": [
            {
                "role": "user",
                "content": "Hello from cloud",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "role": "assistant",
                "content": "Imported reply",
                "created_at": "2026-01-01T00:00:01Z",
            },
        ]
    }

    def fake_get_json(base_url, path, headers=None):
        if path.endswith("/history"):
            return history
        if path.endswith("/files"):
            return {"data": []}
        return bootstrap

    mock_cfg = MagicMock()
    mock_cfg.get.side_effect = lambda key, default=None: {
        "api.fastfold_cloud_key": "",
        "sandbox.output_dir": str(tmp_path / "outputs"),
    }.get(key, default)

    runner = CliRunner()
    # Patch the names bound into the fork modules (not the re-export on ``cli``).
    with (
        patch("cli.fork._agents_api_get_json", side_effect=fake_get_json),
        patch("cli.fork_import._agents_api_request_json", return_value={"fork_count": 3}),
        patch("agent.config.Config.load", return_value=mock_cfg),
    ):
        result = runner.invoke(
            app,
            ["fork", share_id, "--no-files"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert "Web UI sync" in result.output
    assert "imported" in result.output

    store = AgentStore(cfg_dir / "agent-server.db")
    sessions = store.list_sessions()
    assert len(sessions) == 1
    session = sessions[0]
    assert session.title == "Forked cloud chat"
    messages = store.list_messages(session.id)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "Hello from cloud"
    assert messages[1].content == "Imported reply"
