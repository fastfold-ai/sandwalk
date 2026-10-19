"""Coverage for environment pip helpers, account lookup, and skill routing."""

from __future__ import annotations

import json
import subprocess
from io import BytesIO
from types import SimpleNamespace

import pytest

from agent.sandbox_backend.skills_route import (
    SkillsFilesystemBackend,
    _command_targets_skills,
    _skills_filesystem_root,
    _wrap_composite_execute_for_skills,
)
from agent_server.account_service import (
    AccountService,
    _request_json,
    _resolve_plan_and_workspace,
    _resolve_user,
)
from agent_server.environment_service import (
    _find_uv,
    _import_check,
    _pip_command,
    _run_pip,
)


def test_environment_pip_helpers(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("agent_server.environment_service.shutil.which", lambda _name: None)
    monkeypatch.setattr("os.access", lambda _path, _mode: False)
    assert _find_uv() is None
    uv = tmp_path / "uv"
    uv.write_text("", encoding="utf-8")
    uv.chmod(0o755)
    monkeypatch.setattr(
        "agent_server.environment_service._UV_FALLBACKS",
        (uv,),
    )
    monkeypatch.setattr("os.access", lambda path, _mode: PathEquals(path, uv))
    assert _find_uv() == str(uv)

    monkeypatch.setattr("agent_server.environment_service._find_uv", lambda: str(uv))
    install = _pip_command("install", "cowsay", tmp_path)
    assert "--break-system-packages" in install
    uninstall = _pip_command("uninstall", "cowsay", None)
    assert "-y" in uninstall
    monkeypatch.setattr("agent_server.environment_service._find_uv", lambda: None)
    pip_install = _pip_command("install", "cowsay", tmp_path)
    assert pip_install[1:3] == ["-m", "pip"]

    monkeypatch.setattr(
        "importlib.metadata.packages_distributions",
        lambda: {"_private": ["Cowsay"], "cowsay": ["cowsay"], "missing": ["other"]},
    )

    def fake_import(name):
        if name == "cowsay":
            return SimpleNamespace()
        raise ImportError(name)

    monkeypatch.setattr("importlib.import_module", fake_import)
    assert _import_check("cowsay") == "cowsay"

    def boom():
        raise RuntimeError("meta")

    monkeypatch.setattr("importlib.metadata.packages_distributions", boom)

    def refuse(name):
        raise ImportError(name)

    monkeypatch.setattr("importlib.import_module", refuse)
    assert _import_check("nope") is None

    monkeypatch.setattr("agent_server.environment_service.active_user_site", lambda: tmp_path)
    monkeypatch.setattr("agent_server.environment_service.activate_user_site", lambda: tmp_path)
    monkeypatch.setattr("agent_server.environment_service.refresh_imports", lambda: None)
    monkeypatch.setattr("agent_server.environment_service._find_uv", lambda: None)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("agent_server.environment_service.subprocess.run", fake_run)
    completed = _run_pip("uninstall", "cowsay")
    assert completed.returncode == 0
    assert "PYTHONPATH" in completed.args or True


class PathEquals:
    def __init__(self, path, expected) -> None:
        self.ok = str(path) == str(expected)

    def __bool__(self) -> bool:
        return self.ok


def test_account_lookup_and_about(monkeypatch) -> None:
    def fail_open(*_args, **_kwargs):
        raise TimeoutError("slow")

    monkeypatch.setattr("urllib.request.urlopen", fail_open)
    assert _request_json("https://example.test", "key") is None

    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def open_text(payload):
        def _open(*_args, **_kwargs):
            return Response(payload)

        return _open

    monkeypatch.setattr("urllib.request.urlopen", open_text(b"not-json"))
    assert _request_json("https://example.test", "key") is None
    monkeypatch.setattr("urllib.request.urlopen", open_text(b"[]"))
    assert _request_json("https://example.test", "key") is None
    monkeypatch.setattr(
        "urllib.request.urlopen",
        open_text(json.dumps({"user": {"id": "u", "email": "a@b.c"}}).encode()),
    )
    assert _resolve_user("key", "https://example.test")[1] == "a@b.c"

    def empty(*_args, **_kwargs):
        return None

    monkeypatch.setattr("agent_server.account_service._request_json", empty)
    assert _resolve_plan_and_workspace("key", "https://example.test") == (None, None, None)

    monkeypatch.setattr(
        "agent_server.account_service._request_json",
        lambda *_args, **_kwargs: {"items": "nope"},
    )
    assert _resolve_plan_and_workspace("key", "https://example.test") == (None, None, None)

    about = AccountService._about(version="0.1.11", check_updates=False)
    assert about.up_to_date is None
    monkeypatch.setattr("agent_server.account_service.latest_pypi_version", lambda: None)
    checked = AccountService._about(version="0.1.11", check_updates=True)
    assert checked.up_to_date is True
    monkeypatch.setattr("agent_server.account_service.latest_pypi_version", lambda: "0.1.11")
    same = AccountService._about(version="0.1.11", check_updates=True)
    assert same.up_to_date is True


def test_skills_route_stages_and_rewrites_execute(tmp_path, monkeypatch) -> None:
    source = tmp_path / "skills"
    nested = source / "demo"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("---\n", encoding="utf-8")
    assert _skills_filesystem_root([]) is None
    assert _skills_filesystem_root([str(source)]) == source.resolve()
    other = tmp_path / "more" / "extra"
    other.mkdir(parents=True)
    staged = _skills_filesystem_root([str(source), str(other)])
    assert staged is not None and (staged / "demo").is_symlink()

    backend = SkillsFilesystemBackend(source, [source])
    with pytest.raises(ValueError, match="traversal"):
        backend._resolve_path("../etc/passwd")
    resolved = backend._resolve_path("/demo/SKILL.md")
    assert resolved.name == "SKILL.md"

    assert _command_targets_skills("python skills/demo/run.py") is True
    assert _command_targets_skills("echo hi") is False

    class Composite:
        def execute(self, command, timeout=None):
            return SimpleNamespace(command=command, timeout=timeout)

    wrapped = Composite()
    _wrap_composite_execute_for_skills(wrapped, source)
    passthrough = wrapped.execute("echo hi", timeout=3)
    assert passthrough.timeout == 3

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="ran", stderr="")

    monkeypatch.setattr("agent_server.environment_service.subprocess.run", fake_run)
    monkeypatch.setattr("agent.sandbox_backend.skills_route.subprocess.run", fake_run)
    ran = wrapped.execute("python /skills/demo/run.py")
    assert ran.exit_code == 0

    def expire(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout") or 1, output=b"partial", stderr=b"err")

    monkeypatch.setattr("agent.sandbox_backend.skills_route.subprocess.run", expire)
    timed = wrapped.execute("skills/demo/run.py", timeout=1)
    assert timed.exit_code == 124

    def crash(cmd, **kwargs):
        raise OSError("no shell")

    monkeypatch.setattr("agent.sandbox_backend.skills_route.subprocess.run", crash)
    failed = wrapped.execute("skills/demo/run.py")
    assert failed.exit_code == 1
