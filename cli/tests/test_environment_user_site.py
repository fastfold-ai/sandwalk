"""Sealed runtimes (the Mac app bundle) install catalog packages to a user site."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_server.environment_service import EnvironmentService, _pip_command
from agent_server.environment_service import user_site as user_site_mod


def test_writable_venv_installs_in_place(monkeypatch, tmp_path):
    monkeypatch.delenv("SANDWALK_FORCE_USER_SITE", raising=False)
    stdlib = tmp_path / "stdlib"
    purelib = tmp_path / "site-packages"
    stdlib.mkdir()
    purelib.mkdir()
    with patch.object(
        user_site_mod.sysconfig,
        "get_paths",
        return_value={"stdlib": str(stdlib), "purelib": str(purelib)},
    ):
        assert user_site_mod.runtime_is_sealed() is False
        assert user_site_mod.active_user_site() is None


def test_externally_managed_marker_means_sealed(monkeypatch, tmp_path):
    monkeypatch.delenv("SANDWALK_FORCE_USER_SITE", raising=False)
    stdlib = tmp_path / "stdlib"
    stdlib.mkdir()
    (stdlib / "EXTERNALLY-MANAGED").write_text("[externally-managed]\n")
    with (
        patch.object(
            user_site_mod.sysconfig,
            "get_paths",
            return_value={"stdlib": str(stdlib), "purelib": str(tmp_path)},
        ),
        # The app runs the base interpreter, not a venv.
        patch.object(user_site_mod.sys, "prefix", "/app/runtime"),
        patch.object(user_site_mod.sys, "base_prefix", "/app/runtime"),
    ):
        assert user_site_mod.runtime_is_sealed() is True


def test_venv_on_managed_python_is_not_sealed(monkeypatch, tmp_path):
    """A dev .venv shares uv's stdlib marker but owns its site-packages."""
    monkeypatch.delenv("SANDWALK_FORCE_USER_SITE", raising=False)
    stdlib = tmp_path / "stdlib"
    purelib = tmp_path / "venv-site"
    stdlib.mkdir()
    purelib.mkdir()
    (stdlib / "EXTERNALLY-MANAGED").write_text("[externally-managed]\n")
    with (
        patch.object(
            user_site_mod.sysconfig,
            "get_paths",
            return_value={"stdlib": str(stdlib), "purelib": str(purelib)},
        ),
        patch.object(user_site_mod.sys, "prefix", "/proj/.venv"),
        patch.object(user_site_mod.sys, "base_prefix", "/opt/python"),
    ):
        assert user_site_mod.runtime_is_sealed() is False


def test_user_site_dir_lives_under_settings(monkeypatch, tmp_path):
    monkeypatch.delenv("SANDWALK_USER_SITE", raising=False)
    monkeypatch.setenv("SANDWALK_HOME", str(tmp_path))
    expected = tmp_path / "python-packages" / f"py{sys.version_info.major}.{sys.version_info.minor}"
    assert user_site_mod.user_site_dir() == expected


def test_activate_adds_user_site_to_sys_path(monkeypatch, tmp_path):
    target = tmp_path / "pkgs"
    monkeypatch.setenv("SANDWALK_FORCE_USER_SITE", "1")
    monkeypatch.setenv("SANDWALK_USER_SITE", str(target))
    before = list(sys.path)
    try:
        assert user_site_mod.activate_user_site() == target
        assert target.is_dir()
        assert str(target) in sys.path
        # Idempotent.
        user_site_mod.activate_user_site()
        assert sys.path.count(str(target)) == 1
    finally:
        sys.path[:] = before


def test_pip_command_targets_user_site():
    cmd = _pip_command("install", "rdkit", Path("/tmp/site"))
    # No uv on this box → pip path; with uv → uv path. Either must carry --target.
    assert "--target" in cmd
    assert cmd[cmd.index("--target") + 1] == "/tmp/site"
    assert "rdkit" in cmd
    if cmd[0].endswith("uv"):
        assert cmd[1:3] == ["pip", "install"]
        assert "--break-system-packages" in cmd


def test_pip_command_in_place_has_no_target():
    cmd = _pip_command("install", "rdkit", None)
    assert "--target" not in cmd
    assert "rdkit" in cmd


def test_install_on_sealed_runtime_uses_target_and_import_check(monkeypatch, tmp_path):
    target = tmp_path / "pkgs"
    monkeypatch.setenv("SANDWALK_FORCE_USER_SITE", "1")
    monkeypatch.setenv("SANDWALK_USER_SITE", str(target))
    completed = SimpleNamespace(returncode=0, stdout="ok", stderr="")
    before = list(sys.path)
    try:
        with (
            patch("agent_server.environment_service._find_uv", return_value="/usr/bin/uv"),
            patch(
                "agent_server.environment_service.subprocess.run",
                return_value=completed,
            ) as run,
            patch(
                "agent_server.environment_service.list_installed_packages",
                return_value=[("rdkit", "2024.1")],
            ),
            patch(
                "agent_server.environment_service._import_check",
                return_value="rdkit",
            ),
        ):
            result = EnvironmentService().install("rdkit")
    finally:
        sys.path[:] = before

    cmd = run.call_args.args[0]
    assert cmd[:3] == ["/usr/bin/uv", "pip", "install"]
    assert "--target" in cmd
    assert cmd[cmd.index("--target") + 1] == str(target)
    assert "--break-system-packages" in cmd
    assert result.ok is True
    assert result.import_module == "rdkit"


def test_report_exposes_user_site(monkeypatch, tmp_path):
    target = tmp_path / "pkgs"
    monkeypatch.setenv("SANDWALK_FORCE_USER_SITE", "1")
    monkeypatch.setenv("SANDWALK_USER_SITE", str(target))
    with (
        patch(
            "agent_server.environment_service.resolve_python_env_root",
            return_value=tmp_path,
        ),
        patch(
            "agent_server.environment_service.list_installed_packages",
            return_value=[],
        ),
        patch("agent_server.environment_service._path_size_bytes", return_value=0),
    ):
        report = EnvironmentService().get_report()
    assert report.user_site_path == str(target)
