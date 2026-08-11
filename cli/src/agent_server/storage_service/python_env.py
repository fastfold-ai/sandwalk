"""Sizing for the Python interpreter/env the agent sandbox runs in."""

from __future__ import annotations

import logging
import site
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path

from agent_server.models import StorageCategory

logger = logging.getLogger("storage_service")

# Cap package children so Storage stays responsive on huge envs.
_MAX_PACKAGE_CHILDREN = 400


def resolve_python_env_root(executable: Path | None = None) -> Path | None:
    """Return the venv/conda/uv-tool root for the agent sandbox interpreter.

    The built-in sandbox runs code in-process with ``sys.executable``, so this
    is the environment FastFold uses for ``run_python``.
    """
    exe = (executable or Path(sys.executable)).expanduser()
    try:
        exe = exe.resolve()
    except OSError:
        return None

    parent = exe.parent
    if parent.name in {"bin", "Scripts"}:
        root = parent.parent
        # Prefer roots that look like isolated environments.
        if (root / "pyvenv.cfg").exists() or (root / "conda-meta").exists():
            return root
        # uv tool installs and some custom prefixes still live under bin/.
        return root

    # System interpreter: fall back to primary site-packages when available.
    try:
        sites = [Path(p) for p in site.getsitepackages()]
    except (AttributeError, TypeError):
        sites = []
    for candidate in sites:
        if candidate.is_dir():
            return candidate
    try:
        user_site = site.getusersitepackages()
        if user_site:
            path = Path(user_site)
            if path.is_dir():
                return path
    except (AttributeError, TypeError, OSError):
        pass
    return None


def list_installed_packages() -> list[tuple[str, str]]:
    """Return sorted ``(name, version)`` for packages in the current interpreter."""
    packages: list[tuple[str, str]] = []
    seen: set[str] = set()
    try:
        distributions = list(importlib_metadata.distributions())
    except Exception as exc:  # noqa: BLE001 — best-effort inventory
        logger.warning("Unable to list installed packages: %s", exc)
        return []

    for dist in distributions:
        try:
            name = (
                dist.metadata["Name"]
                if dist.metadata is not None and "Name" in dist.metadata
                else dist.name
            )
            version = dist.version or ""
        except Exception:  # noqa: BLE001
            continue
        name = str(name or "").strip()
        version = str(version or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        packages.append((name, version))

    packages.sort(key=lambda item: item[0].lower())
    return packages


def _python_env_category() -> StorageCategory | None:
    # Lazy self-lookup so tests that monkeypatch/patch
    # `agent_server.storage_service.{resolve_python_env_root,list_installed_packages,
    # _path_size_bytes}` are honored even though this function lives in a
    # submodule of that package.
    from agent_server import storage_service

    root = storage_service.resolve_python_env_root()
    if root is None:
        return None

    env_bytes = storage_service._path_size_bytes(root)
    packages = storage_service.list_installed_packages()
    truncated = False
    if len(packages) > _MAX_PACKAGE_CHILDREN:
        packages = packages[:_MAX_PACKAGE_CHILDREN]
        truncated = True

    children: list[StorageCategory] = [
        StorageCategory(
            id=f"python_env:pkg:{name.lower()}",
            label=f"{name} {version}".strip() if version else name,
            color="#10b981",
            bytes=0,
            path=None,
        )
        for name, version in packages
    ]
    if truncated:
        children.append(
            StorageCategory(
                id="python_env:pkg:truncated",
                label=f"…and more (showing first {_MAX_PACKAGE_CHILDREN})",
                color="#10b981",
                bytes=0,
                path=None,
            )
        )

    label = "Python environment"
    if (root / "conda-meta").exists() or (root / "pyvenv.cfg").exists():
        label = f"Python environment ({root.name})"

    return StorageCategory(
        id="python_env",
        label=label,
        color="#10b981",
        bytes=env_bytes,
        path=str(root),
        children=children,
    )
