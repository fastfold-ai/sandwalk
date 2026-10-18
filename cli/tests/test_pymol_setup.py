"""Managed PyMOL launcher setup without creating a real venv."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from agent.mcps.pymol_mcp import setup


def _completed(cmd, code=0, out="", err=""):
    return subprocess.CompletedProcess(cmd, code, out, err)


def test_find_host_python_and_link_launcher(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda name: None)
    monkeypatch.setattr(setup.sys, "executable", str(tmp_path / "missing-python"))
    monkeypatch.setattr(setup.os, "access", lambda path, mode: False)
    assert setup._find_host_python() is None
    monkeypatch.setattr(setup.os, "access", lambda path, mode: True)

    exe = tmp_path / "python3"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setattr(setup.shutil, "which", lambda name: str(exe) if name == "python3" else None)
    assert setup._find_host_python() == str(exe)

    home = tmp_path / "pymol-home"
    launcher = home / "bin" / "agentic-pymol"
    monkeypatch.setattr(setup, "pymol_mcp_home", lambda: home)
    monkeypatch.setattr(setup, "launcher_path", lambda: launcher)
    target = tmp_path / "venv-bin"
    target.write_text("bin")
    linked = setup._link_launcher(target)
    assert linked.is_symlink()

    def _no_symlink(self, dest):
        raise OSError("no symlink")

    monkeypatch.setattr(Path, "symlink_to", _no_symlink)
    again = setup._link_launcher(target)
    assert again.is_file()
    assert "exec" in again.read_text()


def test_verify_and_install_packages(tmp_path, monkeypatch):
    missing = tmp_path / "no-venv"
    assert "venv python missing" in (setup._verify_launcher(missing) or "")

    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").write_text("py")
    monkeypatch.setattr(setup, "_run", lambda cmd: _completed(cmd, 0))
    assert setup._verify_launcher(venv) is None
    monkeypatch.setattr(setup, "_run", lambda cmd: _completed(cmd, 1, "", "import failed"))
    assert "import failed" in (setup._verify_launcher(venv) or "")
    monkeypatch.setattr(setup, "_run", lambda cmd: _completed(cmd, 1, "", ""))
    assert "import check failed" in (setup._verify_launcher(venv) or "")

    package = tmp_path / "pkg"
    monkeypatch.setattr(setup, "_run", lambda cmd: _completed(cmd, 1, "pip no", ""))
    ok, detail = setup._install_packages(uv="uv", venv=venv, package=package)
    assert ok is False and "uv pip" in detail
    monkeypatch.setattr(setup, "_run", lambda cmd: _completed(cmd, 0))
    ok, detail = setup._install_packages(uv="uv", venv=venv, package=package)
    assert ok is True and detail == "uv"

    (venv / "bin" / "pip").write_text("pip")
    monkeypatch.setattr(setup, "_run", lambda cmd: _completed(cmd, 1, "", "pip no"))
    ok, detail = setup._install_packages(uv=None, venv=venv, package=package)
    assert ok is False and "pip install" in detail
    monkeypatch.setattr(setup, "_run", lambda cmd: _completed(cmd, 0))
    ok, detail = setup._install_packages(uv=None, venv=venv, package=package)
    assert ok is True and detail == "pip"


def test_ensure_launcher_branches(tmp_path, monkeypatch):
    package = tmp_path / "vendor"
    venv = tmp_path / "venv"
    home = tmp_path / "home"
    launcher = home / "bin" / "agentic-pymol"
    monkeypatch.setattr(setup, "vendor_package_path", lambda: package)
    monkeypatch.setattr(setup, "venv_path", lambda: venv)
    monkeypatch.setattr(setup, "pymol_mcp_home", lambda: home)
    monkeypatch.setattr(setup, "launcher_path", lambda: launcher)
    monkeypatch.setattr(setup, "launcher_ready", lambda: False)

    ok, message = setup.ensure_launcher()
    assert ok is False and "missing" in message.lower()

    package.mkdir()
    (package / "pyproject.toml").write_text("[project]\nname='x'\n")
    monkeypatch.setattr(setup, "launcher_ready", lambda: True)
    monkeypatch.setattr(setup, "_verify_launcher", lambda path: None)
    ok, message = setup.ensure_launcher()
    assert ok is True and "ready" in message.lower()

    monkeypatch.setattr(setup, "_verify_launcher", lambda path: "broken")
    monkeypatch.setattr(setup, "_find_host_python", lambda: None)
    ok, message = setup.ensure_launcher()
    assert ok is False and "host python" in message.lower()

    host = tmp_path / "python3"
    host.write_text("py")
    host.chmod(0o755)

    def _run(cmd):
        if cmd[:2] == ["uv", "venv"]:
            (venv / "bin").mkdir(parents=True, exist_ok=True)
            binary = venv / "bin" / "agentic-pymol"
            binary.write_text("bin")
            (venv / "bin" / "python").write_text("py")
            return _completed(cmd, 0)
        if cmd[:2] == ["uv", "pip"]:
            return _completed(cmd, 0)
        return _completed(cmd, 1, "", "nope")

    monkeypatch.setattr(setup, "_find_host_python", lambda: str(host))
    monkeypatch.setattr(setup.shutil, "which", lambda name: "uv" if name == "uv" else None)
    monkeypatch.setattr(setup, "_run", _run)
    monkeypatch.setattr(setup, "_verify_launcher", lambda path: None)
    ready = {"value": False}

    def _ready():
        return ready["value"]

    monkeypatch.setattr(setup, "launcher_ready", _ready)
    monkeypatch.setattr(setup, "_link_launcher", lambda binary: launcher)
    ok, message = setup.ensure_launcher(force=True)
    assert ok is False and "Failed to write" in message

    ready["value"] = True
    ok, message = setup.ensure_launcher(force=True)
    assert ok is True and "Reinstalled" in message

    def _uv_fails(cmd):
        if cmd[:2] == ["uv", "venv"]:
            return _completed(cmd, 1, "", "uv no")
        if "-m" in cmd and "venv" in cmd:
            return _completed(cmd, 1, "", "venv no")
        return _completed(cmd, 0)

    monkeypatch.setattr(setup, "launcher_ready", lambda: False)
    monkeypatch.setattr(setup, "_run", _uv_fails)
    if venv.exists():
        import shutil
        shutil.rmtree(venv)
    ok, message = setup.ensure_launcher()
    assert ok is False and "venv create failed" in message


def test_ensure_launcher_pip_and_missing_binary(tmp_path, monkeypatch):
    package = tmp_path / "vendor"
    package.mkdir()
    (package / "pyproject.toml").write_text("[project]\n")
    venv = tmp_path / "venv"
    home = tmp_path / "home"
    launcher = home / "bin" / "agentic-pymol"
    monkeypatch.setattr(setup, "vendor_package_path", lambda: package)
    monkeypatch.setattr(setup, "venv_path", lambda: venv)
    monkeypatch.setattr(setup, "pymol_mcp_home", lambda: home)
    monkeypatch.setattr(setup, "launcher_path", lambda: launcher)
    monkeypatch.setattr(setup, "launcher_ready", lambda: False)
    monkeypatch.setattr(setup, "_find_host_python", lambda: sys.executable)
    monkeypatch.setattr(setup.shutil, "which", lambda name: None)

    def _run(cmd):
        (venv / "bin").mkdir(parents=True, exist_ok=True)
        (venv / "bin" / "python").write_text("py")
        (venv / "bin" / "pip").write_text("pip")
        return _completed(cmd, 0)

    monkeypatch.setattr(setup, "_run", _run)
    ok, message = setup.ensure_launcher()
    assert ok is False and "Expected binary missing" in message

    binary = venv / "bin" / "agentic-pymol"
    binary.write_text("bin")
    monkeypatch.setattr(setup, "_verify_launcher", lambda path: "still broken")
    ok, message = setup.ensure_launcher()
    assert ok is False and "import check failed" in message


def test_doctor_checks(tmp_path, monkeypatch):
    package = tmp_path / "vendor"
    monkeypatch.setattr(setup, "vendor_package_path", lambda: package)
    monkeypatch.setattr(setup, "launcher_path", lambda: tmp_path / "missing-launcher")
    monkeypatch.setattr(setup, "launcher_ready", lambda: False)
    monkeypatch.setattr(setup, "token_ready", lambda: False)
    rows = setup.pymol_doctor_checks()
    statuses = {row["name"]: row["status"] for row in rows}
    assert statuses["pymol_vendor"] == "error"
    assert statuses["pymol_launcher"] == "error"
    assert statuses["pymol_token"] == "warn"

    package.mkdir()
    (package / "pyproject.toml").write_text("[project]\n")
    monkeypatch.setattr(setup, "launcher_ready", lambda: True)
    monkeypatch.setattr(setup, "_verify_launcher", lambda path: "broken import")
    monkeypatch.setattr(setup, "token_ready", lambda: True)
    rows = {row["name"]: row for row in setup.pymol_doctor_checks()}
    assert rows["pymol_launcher"]["status"] == "error"
    assert rows["pymol_token"]["status"] == "ok"

    monkeypatch.setattr(setup, "_verify_launcher", lambda path: None)
    rows = {row["name"]: row for row in setup.pymol_doctor_checks()}
    assert rows["pymol_launcher"]["status"] == "ok"
