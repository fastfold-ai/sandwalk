"""Tests for per-session sandbox backend overrides."""

from __future__ import annotations

from pathlib import Path

from agent_server.session_sandbox_service import (
    SessionSandboxService,
    effective_session_sandbox_backend,
)
from agent_server.store import AgentStore


class _Cfg:
    def __init__(self, backend: str = "builtin") -> None:
        self._backend = backend

    def get(self, key, default=None):
        if key == "sandbox.backend":
            return self._backend
        return default


def test_effective_session_sandbox_backend_override():
    assert effective_session_sandbox_backend("modal", config=_Cfg("builtin")) == "modal"
    assert effective_session_sandbox_backend("builtin", config=_Cfg("modal")) == "builtin"
    assert effective_session_sandbox_backend(None, config=_Cfg("modal")) == "modal"
    assert effective_session_sandbox_backend(None, config=_Cfg("builtin")) == "builtin"


def test_store_persists_session_sandbox_backend(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    session = store.create_session(title="t", workspace_path=None, sandbox_backend="modal")
    assert session.sandbox_backend == "modal"
    updated = store.update_session(
        session.id,
        sandbox_backend="builtin",
        update_sandbox_backend=True,
    )
    assert updated is not None
    assert updated.sandbox_backend == "builtin"
    cleared = store.update_session(
        session.id,
        sandbox_backend=None,
        update_sandbox_backend=True,
    )
    assert cleared is not None
    assert cleared.sandbox_backend is None


def test_session_sandbox_status_builtin(tmp_path: Path, monkeypatch):
    store = AgentStore(tmp_path / "agent.db")
    session = store.create_session(title="t", workspace_path=str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)

    class _Settings:
        backend = "builtin"
        modal_configured = False
        compute_type = "cpu"
        gpu_class = "T4"
        cpu_cores = 2.0
        ram_gb = 8.0
        cpu_image = "debian_slim"

    monkeypatch.setattr(
        "agent_server.session_sandbox_service.SandboxSettingsService.get",
        staticmethod(lambda: _Settings()),
    )
    status = SessionSandboxService(store).status(session.id)
    assert status.backend == "builtin"
    assert status.status == "ready"
