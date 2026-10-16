"""Environment report and allowlisted package install/uninstall.

Split package — re-exports the public surface previously defined in
``agent_server/environment_service.py`` so existing imports keep working.

NOTE: ``resolve_python_env_root``, ``list_installed_packages``,
``_path_size_bytes``, ``_find_uv``, and ``subprocess`` stay bound at this
package-root level (not in a submodule) because tests patch them via the
flat dotted path ``agent_server.environment_service.<name>``.
"""

from __future__ import annotations

import importlib
import logging
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from agent_server.environment_catalog import (
    is_core_package,
    is_manageable_package,
    normalize_package_name,
)
from agent_server.environment_service.mutate import build_mutation_result, resolve_canonical_display
from agent_server.environment_service.report import build_core, build_groups
from agent_server.environment_service.user_site import (
    activate_user_site,
    active_user_site,
    refresh_imports,
)
from agent_server.models import EnvironmentPackageMutationResult, EnvironmentReport
from agent_server.storage_service import (
    _path_size_bytes,
    list_installed_packages,
    resolve_python_env_root,
)

logger = logging.getLogger("environment_service")

_PIP_TIMEOUT_S = 900


class EnvironmentError(ValueError):
    """Raised for invalid package management requests."""


def _installed_map() -> dict[str, str]:
    return {
        normalize_package_name(name): version
        for name, version in list_installed_packages()
    }


_UV_FALLBACKS = (
    Path.home() / ".local" / "bin" / "uv",
    Path("/opt/homebrew/bin/uv"),
    Path("/usr/local/bin/uv"),
)


def _find_uv() -> str | None:
    found = shutil.which("uv")
    if found:
        return found
    # The Mac app launches with a minimal PATH; look where installers put uv.
    for candidate in _UV_FALLBACKS:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _pip_command(action: str, package: str, target: Path | None) -> list[str]:
    uv = _find_uv()
    if uv:
        cmd = [uv, "pip", action]
        if action == "uninstall":
            cmd.append("-y")
        cmd += ["--python", sys.executable]
        if target is not None:
            cmd += ["--target", str(target)]
            if action == "install":
                # Our own copy of CPython, flagged managed by uv's build tooling.
                cmd.append("--break-system-packages")
        cmd.append(package)
        return cmd
    cmd = [sys.executable, "-m", "pip", action]
    if action == "uninstall":
        cmd.append("-y")
    if target is not None and action == "install":
        cmd += ["--target", str(target), "--break-system-packages"]
    cmd.append(package)
    return cmd


def _run_pip(action: str, package: str) -> subprocess.CompletedProcess[str]:
    """Run install/uninstall against the interpreter, or its user site when sealed."""
    target = activate_user_site() if active_user_site() is not None else None
    cmd = _pip_command(action, package, target)
    env = None
    if target is not None and not _find_uv():
        # pip uninstall locates distributions through sys.path.
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(target), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)

    logger.info("Environment package %s: %s", action, " ".join(cmd))
    completed = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=_PIP_TIMEOUT_S,
        env=env,
    )
    refresh_imports()
    return completed


def _import_check(package: str) -> str | None:
    """Import the package's top-level module in this process.

    The built-in sandbox runs in this interpreter, so a successful import here
    is what the agent will see. Returns the module name, or None if nothing
    importable was found.
    """
    from importlib import metadata as importlib_metadata

    key = normalize_package_name(package)
    modules: list[str] = []
    try:
        for module, dists in importlib_metadata.packages_distributions().items():
            if any(normalize_package_name(d) == key for d in dists):
                modules.append(module)
    except Exception:  # noqa: BLE001 — best-effort
        modules = []
    if not modules:
        modules = [key.replace("-", "_")]
    for module in sorted(modules):
        if module.startswith("_"):
            continue
        try:
            importlib.import_module(module)
        except Exception:  # noqa: BLE001 — try the next top-level name
            continue
        return module
    return None


class EnvironmentService:
    def get_report(self) -> EnvironmentReport:
        root = resolve_python_env_root()
        installed = _installed_map()
        env_bytes = _path_size_bytes(root) if root else 0
        user_site = active_user_site()
        return EnvironmentReport(
            python_path=sys.executable,
            env_path=str(root) if root else None,
            env_bytes=env_bytes,
            user_site_path=str(user_site) if user_site else None,
            groups=build_groups(installed),
            core=build_core(installed),
            checked_at=datetime.now(UTC).isoformat(),
        )

    def install(
        self,
        name: str,
        *,
        allow_unlisted: bool = False,
    ) -> EnvironmentPackageMutationResult:
        return self._mutate("install", name, allow_unlisted=allow_unlisted)

    def uninstall(self, name: str) -> EnvironmentPackageMutationResult:
        # Allow removing any non-core package (including ones installed by name).
        return self._mutate("uninstall", name, allow_unlisted=True)

    def _mutate(
        self,
        action: str,
        name: str,
        *,
        allow_unlisted: bool = False,
    ) -> EnvironmentPackageMutationResult:
        raw = (name or "").strip()
        if not raw:
            raise EnvironmentError("Package name is required.")
        if is_core_package(raw):
            raise EnvironmentError(
                f"'{raw}' is a core FastFold dependency and cannot be changed here."
            )
        if action == "install" and not is_manageable_package(raw) and not allow_unlisted:
            raise EnvironmentError(
                f"'{raw}' is not in the skill/tool catalog. "
                "Confirm install as an unlisted package to continue."
            )
        if action == "uninstall" and not is_manageable_package(raw) and not allow_unlisted:
            raise EnvironmentError(
                f"'{raw}' is not a manageable skill/tool package."
            )

        canonical_display = resolve_canonical_display(raw)

        try:
            completed = _run_pip(action, canonical_display)
        except subprocess.TimeoutExpired as exc:
            raise EnvironmentError(
                f"Timed out while trying to {action} {canonical_display}."
            ) from exc
        except OSError as exc:
            raise EnvironmentError(str(exc)) from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise EnvironmentError(
                detail[:800]
                or f"Failed to {action} {canonical_display} (exit {completed.returncode})."
            )

        result = build_mutation_result(action, canonical_display, _installed_map())
        if action == "install" and result.installed:
            module = _import_check(canonical_display)
            result.import_module = module
            if module is None:
                result.message += " (installed, but no top-level module imported yet)"
        return result


__all__ = ["EnvironmentError", "EnvironmentService"]
