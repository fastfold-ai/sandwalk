"""Measure on-disk usage under ~/.fastfold-cli for the Storage settings page."""

from __future__ import annotations

import logging
import shutil
import site
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path

from agent.config import CONFIG_DIR, Config
from agent_server.models import (
    StorageCategory,
    StorageLocation,
    StorageReport,
)

logger = logging.getLogger("storage_service")

# Cap package children so Storage stays responsive on huge envs.
_MAX_PACKAGE_CHILDREN = 400


@dataclass(frozen=True)
class _CategorySpec:
    id: str
    label: str
    color: str
    paths: tuple[Path, ...]
    children_from: Path | None = None


def _path_size_bytes(path: Path) -> int:
    """Return total bytes for a file or directory. Missing paths count as 0."""
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    # Prefer `du` — much faster than walking multi‑GB dataset trees.
    try:
        result = subprocess.run(
            ["du", "-sk", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            kib = int(result.stdout.split()[0])
            return max(0, kib * 1024)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass

    total = 0
    try:
        for child in path.rglob("*"):
            try:
                if child.is_file() and not child.is_symlink():
                    total += child.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


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
    root = resolve_python_env_root()
    if root is None:
        return None

    env_bytes = _path_size_bytes(root)
    packages = list_installed_packages()
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


def _category_specs(home: Path, cfg: Config) -> list[_CategorySpec]:
    data_base = Path(
        str(cfg.get("data.base", str(home / "data")) or home / "data")
    ).expanduser()
    return [
        _CategorySpec(
            id="artifacts",
            label="Artifacts",
            color="#3b82f6",
            paths=(home / "workspaces",),
        ),
        _CategorySpec(
            id="datasets",
            label="Datasets",
            color="#22c55e",
            paths=(data_base,),
            children_from=data_base,
        ),
        _CategorySpec(
            id="sessions",
            label="Sessions & chats",
            color="#f97316",
            paths=(
                home / "sessions",
                home / "agent-server.db",
                home / "history",
            ),
        ),
        _CategorySpec(
            id="skills",
            label="Skills",
            color="#a855f7",
            paths=(
                home / "skills",
                home / ".agents" / "skills",
                home / ".claude" / "skills",
            ),
        ),
        _CategorySpec(
            id="downloads",
            label="Downloads",
            color="#06b6d4",
            paths=(home / "downloads",),
        ),
        _CategorySpec(
            id="logs",
            label="Logs",
            color="#94a3b8",
            paths=(home / "logs",),
        ),
        _CategorySpec(
            id="cache",
            label="Cache",
            color="#eab308",
            paths=(home / "cache",),
        ),
    ]


class StorageService:
    def get_report(self, *, home: Path | None = None) -> StorageReport:
        cfg = Config.load()
        root = (home or CONFIG_DIR).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)

        claimed_names: set[str] = set()
        categories: list[StorageCategory] = []
        for spec in _category_specs(root, cfg):
            bytes_used = 0
            for path in spec.paths:
                resolved = path.expanduser()
                bytes_used += _path_size_bytes(resolved)
                try:
                    abs_path = resolved.resolve()
                except OSError:
                    abs_path = resolved
                if abs_path.parent == root or abs_path == root:
                    claimed_names.add(abs_path.name)
                elif root in abs_path.parents:
                    claimed_names.add(abs_path.relative_to(root).parts[0])

            children: list[StorageCategory] = []
            if spec.children_from and spec.children_from.is_dir():
                try:
                    entries = sorted(
                        [
                            child
                            for child in spec.children_from.iterdir()
                            if child.name not in {".DS_Store"}
                        ],
                        key=lambda p: p.name.lower(),
                    )
                except OSError:
                    entries = []
                for child in entries:
                    child_bytes = _path_size_bytes(child)
                    children.append(
                        StorageCategory(
                            id=f"{spec.id}:{child.name}",
                            label=child.name,
                            color=spec.color,
                            bytes=child_bytes,
                            path=str(child),
                        )
                    )

            categories.append(
                StorageCategory(
                    id=spec.id,
                    label=spec.label,
                    color=spec.color,
                    bytes=bytes_used,
                    path=str(spec.paths[0]) if len(spec.paths) == 1 else None,
                    children=children,
                )
            )

        # Agent sandbox interpreter (in-process run_python) — often outside
        # ~/.fastfold-cli (venv / uv tool / conda). Still shown in Disk usage.
        python_env = _python_env_category()
        if python_env is not None:
            categories.append(python_env)

        # Catch remaining top-level entries under the home root as "Other".
        other_bytes = 0
        try:
            for entry in root.iterdir():
                if entry.name in {".DS_Store", *claimed_names}:
                    continue
                other_bytes += _path_size_bytes(entry)
        except OSError:
            other_bytes = 0

        if other_bytes > 0:
            categories.append(
                StorageCategory(
                    id="other",
                    label="Other",
                    color="#71717a",
                    bytes=other_bytes,
                    path=str(root),
                )
            )

        # Location total stays scoped to ~/.fastfold-cli; bar total includes env.
        home_bytes = sum(
            item.bytes for item in categories if item.id != "python_env"
        )
        total_bytes = sum(item.bytes for item in categories)
        try:
            disk = shutil.disk_usage(root)
            available_bytes = int(disk.free)
        except OSError:
            available_bytes = 0

        return StorageReport(
            location=StorageLocation(
                path=str(root),
                label="default location",
                bytes=home_bytes,
            ),
            categories=categories,
            total_bytes=total_bytes,
            available_bytes=available_bytes,
            checked_at=datetime.now(timezone.utc).isoformat(),
        )
