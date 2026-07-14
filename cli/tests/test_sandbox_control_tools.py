"""Tests for agent sandbox control tools."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from agent.sandbox_control_tools import (
    SANDBOX_CONTROL_TOOL_NAMES,
    create_sandbox_control_tools,
)
from agent_server.models import SessionSandboxStatus
from agent_server.store import AgentStore


def _run(coro):
    return asyncio.run(coro)


def test_create_sandbox_control_tools_names():
    tools = create_sandbox_control_tools("sess-1")
    assert tuple(t.name for t in tools) == SANDBOX_CONTROL_TOOL_NAMES


def test_sandbox_status_builtin(tmp_path: Path, monkeypatch):
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
    tools = {t.name: t for t in create_sandbox_control_tools(session.id, store=store)}
    text = _run(tools["sandbox_status"].ainvoke({}))
    assert "Built-in" in text
    assert session.id in text


def test_sandbox_start_switches_to_modal(tmp_path: Path, monkeypatch):
    store = AgentStore(tmp_path / "agent.db")
    session = store.create_session(title="t", workspace_path=str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)

    class _Settings:
        backend = "builtin"
        modal_configured = True
        compute_type = "cpu"
        gpu_class = "T4"
        cpu_cores = 2.0
        ram_gb = 8.0
        cpu_image = "debian_slim"

    monkeypatch.setattr(
        "agent_server.session_sandbox_service.SandboxSettingsService.get",
        staticmethod(lambda: _Settings()),
    )

    started = SessionSandboxStatus(
        session_id=session.id,
        backend="modal",
        session_backend="modal",
        global_backend="builtin",
        status="running",
        provider_sandbox_name="sbx-test",
        modal_configured=True,
        compute_type="cpu",
        gpu_class="T4",
        cpu_cores=2.0,
        ram_gb=8.0,
        cpu_image="debian_slim",
        detail=None,
    )
    start_mock = MagicMock(return_value=started)
    monkeypatch.setattr(
        "agent_server.session_sandbox_service.SessionSandboxService.start",
        start_mock,
    )

    tools = {t.name: t for t in create_sandbox_control_tools(session.id, store=store)}
    text = _run(tools["sandbox_start"].ainvoke({"enable_modal": True}))
    assert "running" in text.lower() or "Modal" in text
    start_mock.assert_called_once_with(session.id)
    updated = store.get_session(session.id)
    assert updated is not None
    assert updated.sandbox_backend == "modal"


def test_sandbox_stop(tmp_path: Path, monkeypatch):
    store = AgentStore(tmp_path / "agent.db")
    session = store.create_session(
        title="t",
        workspace_path=str(tmp_path / "ws"),
        sandbox_backend="modal",
    )
    stopped = SessionSandboxStatus(
        session_id=session.id,
        backend="modal",
        session_backend="modal",
        global_backend="builtin",
        status="stopped",
        provider_sandbox_name=None,
        modal_configured=True,
        compute_type="cpu",
        gpu_class="T4",
        cpu_cores=2.0,
        ram_gb=8.0,
        cpu_image="debian_slim",
        detail="Modal sandbox is not running for this chat.",
    )
    stop_mock = MagicMock(return_value=stopped)
    monkeypatch.setattr(
        "agent_server.session_sandbox_service.SessionSandboxService.stop",
        stop_mock,
    )
    tools = {t.name: t for t in create_sandbox_control_tools(session.id, store=store)}
    text = _run(tools["sandbox_stop"].ainvoke({}))
    assert "stop" in text.lower()
    stop_mock.assert_called_once_with(session.id)


def test_wait_until_seeded_builtin_immediate():
    from agent.sandbox_backend import SandboxHandle, wait_until_seeded

    handle = SandboxHandle(
        kind="builtin",
        backend=SimpleNamespace(),
        workspace_root="/tmp",
        skills_sources=[],
        seeded=False,
    )
    assert wait_until_seeded(handle, timeout=0.1) is True


def test_wait_until_seeded_modal_timeout():
    from agent.sandbox_backend import SandboxHandle, wait_until_seeded

    handle = SandboxHandle(
        kind="modal",
        backend=SimpleNamespace(),
        workspace_root="/tmp",
        skills_sources=[],
        seeded=False,
    )
    assert wait_until_seeded(handle, timeout=0.05, poll_interval=0.01) is False
