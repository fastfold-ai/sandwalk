"""Install/check the managed agentic-pymol launcher under ~/.sandwalk/pymol-mcp."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from agent.mcps.pymol_mcp.paths import (
    TOKEN_PATH,
    launcher_path,
    launcher_ready,
    pymol_mcp_home,
    token_ready,
    vendor_package_path,
    venv_path,
)


def _find_host_python() -> str | None:
    candidates = [
        shutil.which("python3"),
        shutil.which("python"),
        "/usr/bin/python3",
        "/usr/local/bin/python3",
        sys.executable,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _link_launcher(venv_bin: Path) -> Path:
    home = pymol_mcp_home()
    bin_dir = home / "bin"
    launcher = launcher_path()
    bin_dir.mkdir(parents=True, exist_ok=True)
    if launcher.exists() or launcher.is_symlink():
        launcher.unlink()
    try:
        launcher.symlink_to(venv_bin)
    except OSError:
        launcher.write_text(
            "#!/usr/bin/env bash\n" f'exec "{venv_bin}" "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(0o755)
    return launcher


def _verify_launcher(venv: Path) -> str | None:
    """Return an error message if agentic-pymol cannot import FastMCP."""
    py = venv / "bin" / "python"
    if not py.is_file():
        py = venv / "Scripts" / "python.exe"
    if not py.is_file():
        return f"venv python missing under {venv}"
    check = _run(
        [
            str(py),
            "-c",
            "from mcp.server.fastmcp import FastMCP; import agentic_pymol",
        ]
    )
    if check.returncode == 0:
        return None
    detail = (check.stderr or check.stdout or "").strip()
    return detail[:500] or "agentic-pymol import check failed"


def _install_packages(*, uv: str | None, venv: Path, package: Path) -> tuple[bool, str]:
    """Install the vendored local package (deps include mcp[cli]<2)."""
    if uv:
        install = _run([uv, "pip", "install", "--python", str(venv), str(package)])
        if install.returncode != 0:
            detail = (install.stderr or install.stdout or "").strip()
            return False, f"uv pip install failed: {detail[:400]}"
        return True, "uv"

    pip = venv / "bin" / "pip"
    if not pip.is_file():
        pip = venv / "Scripts" / "pip.exe"
    install = _run([str(pip), "install", "--upgrade", "pip", str(package)])
    if install.returncode != 0:
        detail = (install.stderr or install.stdout or "").strip()
        return False, f"pip install failed: {detail[:400]}"
    return True, "pip"


def ensure_launcher(*, force: bool = False) -> tuple[bool, str]:
    """Ensure ~/.sandwalk/pymol-mcp/bin/agentic-pymol exists.

    Returns (ok, message). Pass force=True to recreate the venv and reinstall.
    """
    launcher = launcher_path()
    venv = venv_path()
    package = vendor_package_path()
    if not (package / "pyproject.toml").is_file():
        return False, f"Vendored agentic-pymol package missing: {package}"

    if launcher_ready() and not force:
        verify = _verify_launcher(venv)
        if verify is None:
            return True, f"Launcher ready: {launcher}"
        # Broken install (e.g. mcp 2.x without FastMCP) — repair in place.
        force = True

    host_python = _find_host_python()
    if not host_python:
        return False, "No host python3 found to create the managed venv"

    home = pymol_mcp_home()
    home.mkdir(parents=True, exist_ok=True)
    if force and venv.exists():
        shutil.rmtree(venv, ignore_errors=True)

    uv = shutil.which("uv")
    installed_with_uv = False
    if uv:
        create = _run([uv, "venv", str(venv)])
        if create.returncode == 0:
            ok, detail = _install_packages(uv=uv, venv=venv, package=package)
            if not ok:
                return False, detail
            installed_with_uv = True
        else:
            uv = None

    if not installed_with_uv:
        if not venv.exists():
            create = _run([host_python, "-m", "venv", str(venv)])
            if create.returncode != 0:
                detail = (create.stderr or create.stdout or "").strip()
                return False, f"venv create failed: {detail[:400]}"
        ok, detail = _install_packages(uv=None, venv=venv, package=package)
        if not ok:
            return False, detail

    venv_bin = venv / "bin" / "agentic-pymol"
    if not venv_bin.is_file():
        venv_bin = venv / "Scripts" / "agentic-pymol.exe"
    if not venv_bin.is_file():
        return False, f"Expected binary missing after install: {venv_bin}"

    verify = _verify_launcher(venv)
    if verify is not None:
        return False, f"Launcher import check failed: {verify}"

    linked = _link_launcher(venv_bin)
    if not launcher_ready():
        return False, f"Failed to write launcher at {linked}"
    action = "Reinstalled" if force else "Installed"
    return True, f"{action} launcher: {linked}"


def pymol_doctor_checks() -> list[dict[str, str]]:
    """Return structured doctor rows for PyMOL MCP."""
    rows: list[dict[str, str]] = []
    launcher = launcher_path()
    package = vendor_package_path()
    if not (package / "pyproject.toml").is_file():
        rows.append(
            {
                "name": "pymol_vendor",
                "status": "error",
                "detail": f"Missing vendored package: {package}",
                "fix": "Reinstall sandwalk / restore cli/src/agent/mcps/pymol_mcp/vendor",
            }
        )
    if launcher_ready():
        verify = _verify_launcher(venv_path())
        if verify is None:
            rows.append(
                {
                    "name": "pymol_launcher",
                    "status": "ok",
                    "detail": f"Launcher: {launcher}",
                }
            )
        else:
            rows.append(
                {
                    "name": "pymol_launcher",
                    "status": "error",
                    "detail": f"Launcher broken: {verify[:200]}",
                    "fix": "Run: sandwalk mcp install pymol --force",
                }
            )
    else:
        rows.append(
            {
                "name": "pymol_launcher",
                "status": "error",
                "detail": f"Missing launcher: {launcher}",
                "fix": "Run: sandwalk mcp install pymol  (or in PyMOL: sandwalk-pymol setup)",
            }
        )
    if token_ready():
        rows.append(
            {
                "name": "pymol_token",
                "status": "ok",
                "detail": f"Token: {TOKEN_PATH}",
            }
        )
    else:
        rows.append(
            {
                "name": "pymol_token",
                "status": "warn",
                "detail": f"No token yet at {TOKEN_PATH}",
                "fix": "In PyMOL: open Sandwalk PyMOL MCP → Start Listening",
            }
        )
    return rows
