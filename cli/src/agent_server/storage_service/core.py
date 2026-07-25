"""``StorageService.get_report`` — assembles categories into a Storage report.

Uses plain ``import shutil`` (not ``from x import y``) so tests that
monkeypatch ``agent_server.storage_service.shutil.disk_usage`` patch the
shared module object this call resolves through, matching this module's
behavior from before the split.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from agent.config import CONFIG_DIR, Config
from agent_server.models import StorageCategory, StorageLocation, StorageReport
from agent_server.storage_service.categories import (
    _category_path_label,
    _category_specs,
    _path_children,
)
from agent_server.storage_service.database import probe_agent_database
from agent_server.storage_service.path_size import _path_size_bytes


class StorageService:
    def get_report(self, *, home: Path | None = None) -> StorageReport:
        # Look up via the package namespace (not direct import) so
        # `agent_server.storage_service._python_env_category` monkeypatches apply.
        from agent_server import storage_service as _storage_service

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

            children: list[StorageCategory] = _path_children(spec)
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
                    path=_category_path_label(spec.paths),
                    children=children,
                )
            )

        # Agent sandbox interpreter (in-process run_python) — often outside
        # ~/.sandwalk (venv / uv tool / conda). Still shown in Disk usage.
        python_env = _storage_service._python_env_category()
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

        # Location total stays scoped to ~/.sandwalk; bar total includes
        # desktop Models (app-data) and the Python env when present.
        outside_home = {"python_env", "models"}
        home_bytes = sum(
            item.bytes for item in categories if item.id not in outside_home
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
            checked_at=datetime.now(UTC).isoformat(),
            database=probe_agent_database(root),
        )
