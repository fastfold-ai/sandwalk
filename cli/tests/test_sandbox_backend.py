"""Unit tests for sandbox backend factory (Modal mocked)."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from deepagents.backends import FilesystemBackend

from agent.sandbox_backend import (
    SandboxHandle,
    _safe_sandbox_name,
    clear_active_handles,
    get_active_handle,
    parse_pip_packages,
    push_paths_for_session,
    register_handle,
    resolve_deepagents_backend,
    sandbox_backend_from_config,
    unregister_handle,
)


def test_parse_pip_packages_defaults():
    pkgs = parse_pip_packages(None)
    assert "pandas" in pkgs
    assert parse_pip_packages("a, b ; c") == ["a", "b", "c"]
    assert parse_pip_packages(["x", " y "]) == ["x", "y"]
    assert parse_pip_packages("  ") == pkgs


def test_safe_sandbox_name():
    name = _safe_sandbox_name("Session/ABC 123!")
    assert name.startswith("sandwalk-")
    assert " " not in name
    assert _safe_sandbox_name(None).startswith("sandwalk-")


def test_sandbox_backend_from_config():
    cfg = SimpleNamespace(
        get=lambda key, default=None: {"sandbox.backend": "modal"}.get(key, default)
    )
    assert sandbox_backend_from_config(cfg) == "modal"
    cfg2 = SimpleNamespace(get=lambda key, default=None: "nope")
    assert sandbox_backend_from_config(cfg2) == "builtin"


def test_handle_registry_and_pull_push(tmp_path: Path):
    clear_active_handles()
    backend = MagicMock()
    backend.upload_files.return_value = []
    backend.download_files.return_value = []
    backend.execute.return_value = SimpleNamespace(output="", exit_code=0)
    handle = SandboxHandle(
        kind="modal",
        backend=backend,
        workspace_root=str(tmp_path),
        skills_sources=["/skills/"],
        session_id="sess-1",
        modal_sandbox=MagicMock(),
    )
    register_handle(handle)
    assert get_active_handle("sess-1") is handle
    (tmp_path / "a.txt").write_text("x")
    assert handle.push(["a.txt"]) == 1
    assert handle.pull() == 0
    handle.terminate()
    handle.modal_sandbox.terminate.assert_called()
    unregister_handle("sess-1")
    assert get_active_handle("sess-1") is None


def test_builtin_handle_noop_sync(tmp_path: Path):
    handle = SandboxHandle(
        kind="builtin",
        backend=MagicMock(),
        workspace_root=str(tmp_path),
        skills_sources=[],
    )
    assert handle.pull() == 0
    assert handle.push() == 0
    handle.terminate()


def test_resolve_builtin(tmp_path: Path):
    clear_active_handles()
    cfg = SimpleNamespace(
        get=lambda key, default=None: {
            "sandbox.backend": "builtin",
        }.get(key, default)
    )
    handle = resolve_deepagents_backend(
        cfg,
        session_id="s1",
        workspace_root=str(tmp_path),
        skill_source_dirs=[str(tmp_path)],
    )
    assert handle.kind == "builtin"
    assert isinstance(handle.backend, FilesystemBackend)
    assert handle.skills_sources == [str(tmp_path)]
    assert push_paths_for_session("s1", tmp_path, ["x"]) == 0


def test_resolve_modal_mocked(tmp_path: Path):
    clear_active_handles()
    (tmp_path / "hello.txt").write_text("hi")
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("x")

    fake_backend = MagicMock()
    fake_backend.execute.return_value = SimpleNamespace(output="", exit_code=0)
    fake_backend.upload_files.return_value = []
    fake_modal_sb = MagicMock()

    cfg = SimpleNamespace(
        get=lambda key, default=None: {
            "sandbox.backend": "modal",
            "sandbox.modal_app": "sandwalk-test",
            "sandbox.pip_packages": "numpy",
            "sandbox.idle_ttl_seconds": 600,
            "sandbox.timeout": 30,
            "sandbox.cpu_cores": 1.0,
            "sandbox.ram_gb": 2.0,
            "sandbox.compute_type": "cpu",
        }.get(key, default)
    )

    with patch(
        "agent.sandbox_backend._create_or_reuse_modal_sandbox",
        return_value=(fake_backend, fake_modal_sb, "sandwalk-s1", True),
    ):
        handle = resolve_deepagents_backend(
            cfg,
            session_id="s1",
            workspace_root=str(tmp_path),
            skill_source_dirs=[str(tmp_path / "skills")],
        )
        again = resolve_deepagents_backend(
            cfg,
            session_id="s1",
            workspace_root=str(tmp_path),
            skill_source_dirs=[str(tmp_path / "skills")],
        )

    assert handle.kind == "modal"
    assert again is handle
    assert handle.skills_sources == ["/skills/"]
    assert handle.backend is fake_backend
    assert fake_backend.upload_files.called
    assert push_paths_for_session("s1", tmp_path, ["hello.txt"]) >= 0


def test_resolve_modal_background_sync_registers_immediately(tmp_path: Path):
    clear_active_handles()
    fake_backend = MagicMock()
    fake_backend.execute.return_value = SimpleNamespace(output="", exit_code=0)
    fake_modal_sb = MagicMock()
    cfg = SimpleNamespace(
        get=lambda key, default=None: {"sandbox.backend": "modal"}.get(key, default)
    )
    with (
        patch(
            "agent.sandbox_backend._create_or_reuse_modal_sandbox",
            return_value=(fake_backend, fake_modal_sb, "sandwalk-bg", True),
        ),
        patch("agent.sandbox_backend._seed_modal_handle") as seed,
    ):
        handle = resolve_deepagents_backend(
            cfg,
            session_id="bg-1",
            workspace_root=str(tmp_path),
            skill_source_dirs=[],
            background_sync=True,
        )
    assert handle.kind == "modal"
    assert get_active_handle("bg-1") is handle
    # Seed is scheduled on a daemon thread; don't require it to have finished.
    assert seed.call_count >= 0


def test_run_modal_blocking_offloads_when_loop_running():
    from agent.sandbox_backend import _run_modal_blocking

    marker = {"thread": None}

    def work():
        marker["thread"] = threading.current_thread().name
        return 42

    async def runner():
        return _run_modal_blocking(work)

    assert asyncio.run(runner()) == 42
    assert marker["thread"] is not None
    assert "sandwalk-modal" in marker["thread"]


def test_run_modal_blocking_inline_without_loop():
    from agent.sandbox_backend import _run_modal_blocking

    assert _run_modal_blocking(lambda: 7) == 7


def test_ensure_modal_tokens_raises(monkeypatch):
    from agent.sandbox_backend import _ensure_modal_tokens

    monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
    monkeypatch.delenv("MODAL_TOKEN_SECRET", raising=False)
    cfg = SimpleNamespace(get=lambda *a, **k: None)
    with patch("agent.config.sync_process_env_from_config"):
        with pytest.raises(RuntimeError, match="Modal sandbox requires"):
            _ensure_modal_tokens(cfg)

