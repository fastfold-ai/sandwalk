"""Ensure Modal host dependencies are available (auto-heal on first use)."""

from __future__ import annotations

import importlib
import logging
import shutil
import subprocess
import sys
from typing import Sequence

logger = logging.getLogger(__name__)

_MODAL_PIP_SPECS = (
    "langchain-modal>=0.0.1",
    "modal>=0.73",
)


def modal_deps_importable() -> tuple[bool, str]:
    try:
        importlib.import_module("langchain_modal")
        importlib.import_module("modal")
    except ImportError as exc:
        return False, str(exc)
    return True, "langchain-modal and modal importable"


def _install_commands(specs: Sequence[str]) -> list[list[str]]:
    """Prefer uv when available (Sandwalk venvs often omit pip)."""
    commands: list[list[str]] = []
    uv = shutil.which("uv")
    if uv:
        commands.append([uv, "pip", "install", *specs])
    commands.append(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            *specs,
        ]
    )
    return commands


def ensure_modal_deps(*, auto_install: bool = True) -> tuple[bool, str]:
    """Return whether Modal deps are importable; optionally install them.

    Used by sandbox probe / backend so selecting Modal does not require a
    manual ``pip install -e '.[modal]'`` step on a local Sandwalk venv.
    """
    ok, detail = modal_deps_importable()
    if ok:
        return True, detail
    if not auto_install:
        return False, (
            f"Install Modal extras: pip install -e '.[modal]' ({detail})"
        )

    logger.info("Modal deps missing (%s); auto-installing %s", detail, _MODAL_PIP_SPECS)
    errors: list[str] = []
    for cmd in _install_commands(_MODAL_PIP_SPECS):
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{' '.join(cmd)} → {exc}")
            continue
        if proc.returncode == 0:
            break
        stderr = (proc.stderr or proc.stdout or "").strip()
        snippet = stderr[-400:] if stderr else f"exit {proc.returncode}"
        errors.append(f"{' '.join(cmd)} → {snippet}")
    else:
        return False, "Auto-install Modal deps failed: " + " | ".join(errors)

    for name in ("langchain_modal", "modal"):
        sys.modules.pop(name, None)
    ok, detail = modal_deps_importable()
    if ok:
        return True, "Installed Modal deps and verified imports"
    return False, f"Installed Modal packages but import still fails ({detail})"


def require_modal_deps() -> None:
    """Raise ImportError with heal guidance if Modal deps cannot be loaded."""
    ok, detail = ensure_modal_deps(auto_install=True)
    if not ok:
        raise ImportError(detail)
