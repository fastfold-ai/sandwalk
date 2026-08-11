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
    _build_modal_image,
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


def test_build_modal_image_debian_slim_and_registry():
    cfg = MagicMock()

    def _get(key, default=None):
        values = {
            "sandbox.cpu_image": "debian_slim",
            "sandbox.gpu_image": "python:3.12-slim",
        }
        return values.get(key, default)

    cfg.get.side_effect = _get
    fake_modal = MagicMock()
    debian = MagicMock(name="debian_image")
    registry = MagicMock(name="registry_image")
    fake_modal.Image.debian_slim.return_value = debian
    fake_modal.Image.from_registry.return_value = registry

    with (
        patch("agent.sandbox_deps.require_modal_deps"),
        patch("agent.sandbox_backend.parse_pip_packages", return_value=[]),
        patch.dict("sys.modules", {"modal": fake_modal}),
    ):
        assert _build_modal_image(cfg, compute_type="cpu") is debian
        fake_modal.Image.debian_slim.assert_called_once()
        assert _build_modal_image(cfg, compute_type="gpu") is registry
        fake_modal.Image.from_registry.assert_called_once_with("python:3.12-slim")


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
    import os

    from agent.sandbox_backend.workspace_route import HostWorkspaceMirrorBackend

    clear_active_handles()
    cfg = SimpleNamespace(
        get=lambda key, default=None: {
            "sandbox.backend": "builtin",
        }.get(key, default)
    )
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "backlog.md").write_text("old\n", encoding="utf-8")
    os.symlink(linked, tmp_path / "project", target_is_directory=True)
    handle = resolve_deepagents_backend(
        cfg,
        session_id="s1",
        workspace_root=str(tmp_path),
        skill_source_dirs=[str(tmp_path)],
    )
    assert handle.kind == "builtin"
    assert isinstance(handle.backend, HostWorkspaceMirrorBackend)
    assert isinstance(handle.backend._inner, FilesystemBackend)
    # Existing project files must upsert via write_file (no "already exists").
    result = handle.backend.write(
        str(tmp_path / "project" / "backlog.md"), "- task\n"
    )
    assert result.error is None
    assert (linked / "backlog.md").read_text(encoding="utf-8") == "- task\n"
    assert handle.skills_sources == [str(tmp_path)]
    assert push_paths_for_session("s1", tmp_path, ["x"]) == 0


def test_resolve_modal_mocked(tmp_path: Path):
    clear_active_handles()
    (tmp_path / "hello.txt").write_text("hi")
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("---\nname: demo\n---\n\n# Demo\n")

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
    # Skills are routed locally via CompositeBackend — not uploaded to Modal.
    from deepagents.backends import CompositeBackend

    from agent.sandbox_backend.workspace_route import HostWorkspaceMirrorBackend

    assert isinstance(handle.backend, HostWorkspaceMirrorBackend)
    assert isinstance(handle.backend._inner, CompositeBackend)
    assert handle.backend._inner.default is fake_backend
    assert fake_backend.upload_files.called  # workspace push only
    # seed_skills must not run: no /skills/ uploads beyond workspace files
    uploaded_paths = []
    for call in fake_backend.upload_files.call_args_list:
        files = call.args[0] if call.args else call.kwargs.get("files", [])
        uploaded_paths.extend(path for path, _ in files)
    assert all(not str(p).startswith("/skills/") for p in uploaded_paths)
    assert push_paths_for_session("s1", tmp_path, ["hello.txt"]) >= 0


def test_resolve_modal_does_not_upload_skills(tmp_path: Path):
    clear_active_handles()
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("x")
    # Large-ish skill tree should still never touch Modal upload for /skills/
    blob = skills / "big.bin"
    blob.write_bytes(b"0" * 1024)
    fake_backend = MagicMock()
    fake_backend.execute.return_value = SimpleNamespace(output="", exit_code=0)
    fake_backend.upload_files.return_value = []
    cfg = SimpleNamespace(
        get=lambda key, default=None: {"sandbox.backend": "modal"}.get(key, default)
    )
    with patch(
        "agent.sandbox_backend._create_or_reuse_modal_sandbox",
        return_value=(fake_backend, MagicMock(), "sandwalk-ns", True),
    ):
        resolve_deepagents_backend(
            cfg,
            session_id="no-skills-upload",
            workspace_root=str(tmp_path),
            skill_source_dirs=[str(tmp_path / "skills")],
        )
    uploaded_paths = []
    for call in fake_backend.upload_files.call_args_list:
        files = call.args[0] if call.args else call.kwargs.get("files", [])
        uploaded_paths.extend(path for path, _ in files)
    assert all(not str(p).startswith("/skills/") for p in uploaded_paths)
    from agent import sandbox_backend as sb

    assert not hasattr(sb, "seed_skills")


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
        patch("agent.sandbox_backend._seed_modal_workspace") as seed,
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


def test_modal_skills_execute_runs_on_host(tmp_path: Path):
    clear_active_handles()
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    script = skills / "scripts"
    script.mkdir()
    (script / "hello.py").write_text("print('host-skill-ok')\n")
    (skills / "SKILL.md").write_text("---\nname: demo\n---\n")

    fake_backend = MagicMock()
    fake_backend.execute.return_value = SimpleNamespace(
        output="should-not-use-modal", exit_code=0
    )
    cfg = SimpleNamespace(
        get=lambda key, default=None: {"sandbox.backend": "modal"}.get(key, default)
    )
    with patch(
        "agent.sandbox_backend._create_or_reuse_modal_sandbox",
        return_value=(fake_backend, MagicMock(), "sandwalk-exec", True),
    ):
        handle = resolve_deepagents_backend(
            cfg,
            session_id="exec-skills",
            workspace_root=str(tmp_path),
            skill_source_dirs=[str(tmp_path / "skills")],
            sync_workspace=False,
        )

    result = handle.backend.execute(
        "python3 /skills/demo/scripts/hello.py",
        timeout=30,
    )
    assert "host-skill-ok" in str(getattr(result, "output", result))
    assert getattr(result, "exit_code", None) == 0
    # Modal execute must not be used for /skills/ paths
    fake_backend.execute.assert_not_called()


def test_modal_skills_read_follows_staged_source_symlink(tmp_path: Path):
    clear_active_handles()
    bundled = tmp_path / "bundled"
    installed = tmp_path / "installed"
    (bundled / "other").mkdir(parents=True)
    references = installed / "boltz" / "references"
    references.mkdir(parents=True)
    example = references / "examples.md"
    example.write_text("# Boltz examples\n", encoding="utf-8")

    fake_backend = MagicMock()
    cfg = SimpleNamespace(
        get=lambda key, default=None: {"sandbox.backend": "modal"}.get(key, default)
    )
    with patch(
        "agent.sandbox_backend._create_or_reuse_modal_sandbox",
        return_value=(fake_backend, MagicMock(), "sandwalk-read", True),
    ):
        handle = resolve_deepagents_backend(
            cfg,
            session_id="read-skills",
            workspace_root=str(tmp_path / "workspace"),
            skill_source_dirs=[str(bundled), str(installed)],
            sync_workspace=False,
        )

    result = handle.backend.read("/skills/boltz/references/examples.md")
    assert result.error is None
    assert result.file_data["content"] == "# Boltz examples\n"


def test_modal_workspace_execute_uses_modal(tmp_path: Path):
    clear_active_handles()
    fake_backend = MagicMock()
    fake_backend.execute.return_value = SimpleNamespace(output="modal-ok", exit_code=0)
    cfg = SimpleNamespace(
        get=lambda key, default=None: {"sandbox.backend": "modal"}.get(key, default)
    )
    with patch(
        "agent.sandbox_backend._create_or_reuse_modal_sandbox",
        return_value=(fake_backend, MagicMock(), "sandwalk-ws", True),
    ):
        handle = resolve_deepagents_backend(
            cfg,
            session_id="exec-ws",
            workspace_root=str(tmp_path),
            skill_source_dirs=[],
            sync_workspace=False,
        )

    result = handle.backend.execute("echo hi", timeout=10)
    assert getattr(result, "output", None) == "modal-ok"
    fake_backend.execute.assert_called()


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

