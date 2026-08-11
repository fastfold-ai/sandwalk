"""Environment report and allowlisted package install/uninstall.

Split package — re-exports the public surface previously defined in
``agent_server/environment_service.py`` so existing imports keep working.

NOTE: ``resolve_python_env_root``, ``list_installed_packages``,
``_path_size_bytes``, ``_find_uv``, and ``subprocess`` stay bound at this
package-root level (not in a submodule) because tests patch them via the
flat dotted path ``agent_server.environment_service.<name>``.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from datetime import UTC, datetime

from agent_server.environment_catalog import (
    is_core_package,
    is_manageable_package,
    normalize_package_name,
)
from agent_server.environment_service.mutate import build_mutation_result, resolve_canonical_display
from agent_server.environment_service.report import build_core, build_groups
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


def _find_uv() -> str | None:
    return shutil.which("uv")


def _run_pip(action: str, package: str) -> subprocess.CompletedProcess[str]:
    """Run install/uninstall against the current interpreter."""
    uv = _find_uv()
    if uv:
        if action == "install":
            cmd = [uv, "pip", "install", "--python", sys.executable, package]
        else:
            cmd = [
                uv,
                "pip",
                "uninstall",
                "-y",
                "--python",
                sys.executable,
                package,
            ]
    else:
        if action == "install":
            cmd = [sys.executable, "-m", "pip", "install", package]
        else:
            cmd = [sys.executable, "-m", "pip", "uninstall", "-y", package]

    logger.info("Environment package %s: %s", action, " ".join(cmd))
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=_PIP_TIMEOUT_S,
    )


class EnvironmentService:
    def get_report(self) -> EnvironmentReport:
        root = resolve_python_env_root()
        installed = _installed_map()
        env_bytes = _path_size_bytes(root) if root else 0
        return EnvironmentReport(
            python_path=sys.executable,
            env_path=str(root) if root else None,
            env_bytes=env_bytes,
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

        return build_mutation_result(action, canonical_display, _installed_map())


__all__ = ["EnvironmentError", "EnvironmentService"]
