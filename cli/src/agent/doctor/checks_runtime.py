"""Python runtime and sandbox backend readiness checks."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys

from agent.config import Config
from agent.doctor.models import DoctorCheck


def _tool_version(command: str, *args: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
            stdin=subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001
        return path
    text = (result.stdout or result.stderr or "").strip().splitlines()
    return text[0].strip() if text else path


def _check_python_runtime() -> DoctorCheck:
    version = platform.python_version()
    impl = platform.python_implementation()
    detail = f"{impl} {version} ({sys.executable})"
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 10):
        return DoctorCheck(
            name="python_runtime",
            status="error",
            detail=detail,
            category="runtime",
            fix="Use Python 3.10+",
        )
    if (major, minor) < (3, 11):
        return DoctorCheck(
            name="python_runtime",
            status="warn",
            detail=detail,
            category="runtime",
            fix="Python 3.11+ is recommended",
        )
    return DoctorCheck(
        name="python_runtime",
        status="ok",
        detail=detail,
        category="runtime",
    )


def _check_sandbox_backend(cfg: Config) -> DoctorCheck:
    backend = str(cfg.get("sandbox.backend") or "builtin").strip().lower()
    if backend == "builtin":
        return DoctorCheck(
            name="sandbox_backend",
            status="ok",
            detail="builtin (local FilesystemBackend)",
            category="runtime",
        )
    if backend != "modal":
        return DoctorCheck(
            name="sandbox_backend",
            status="warn",
            detail=f"Unknown sandbox.backend={backend!r}; expected builtin|modal",
            category="runtime",
            fix="sandwalk config set sandbox.backend builtin",
        )
    from agent.sandbox_deps import ensure_modal_deps
    from agent.sandbox_probe import modal_tokens_present

    present, detail = modal_tokens_present(cfg)
    if not present:
        return DoctorCheck(
            name="sandbox_backend",
            status="error",
            detail=f"modal selected but {detail}",
            category="runtime",
            fix="Set Modal tokens under Integrations → Modal",
        )
    deps_ok, deps_detail = ensure_modal_deps(auto_install=True)
    if not deps_ok:
        return DoctorCheck(
            name="sandbox_backend",
            status="error",
            detail=f"modal selected but deps unavailable: {deps_detail}",
            category="runtime",
            fix="pip install langchain-modal modal  (or pip install -e '.[modal]')",
        )
    return DoctorCheck(
        name="sandbox_backend",
        status="ok",
        detail=f"modal ({detail}; {deps_detail})",
        category="runtime",
    )
