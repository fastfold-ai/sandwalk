"""Creating a session on a not-yet-existing folder under ~/.sandwalk works."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_server.service import AgentService
from agent_server.store import AgentStore


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AgentService:
    import agent.config as cfg
    import agent_server.service.sessions_crud as crud

    config_dir = tmp_path / ".sandwalk"
    config_dir.mkdir()
    monkeypatch.setattr(cfg, "CONFIG_DIR", config_dir, raising=False)
    monkeypatch.setattr(crud, "_is_under_config_dir", lambda p: p == config_dir or config_dir in p.parents)
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    return AgentService(store)


def test_integration_folder_under_config_dir_is_created(service: AgentService, tmp_path: Path):
    target = tmp_path / ".sandwalk" / "vercel-integration"
    assert not target.exists()
    session = service.create_session(title="Vercel setup", workspace_path=str(target))
    assert target.is_dir()
    assert session.workspace_path == str(target.resolve())


def test_user_folder_outside_config_dir_must_exist(service: AgentService, tmp_path: Path):
    missing = tmp_path / "somewhere" / "else"
    with pytest.raises(ValueError, match="does not exist"):
        service.create_session(title="x", workspace_path=str(missing))
    assert not missing.exists()
