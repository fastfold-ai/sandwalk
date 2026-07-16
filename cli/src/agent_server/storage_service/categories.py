"""Storage category specs, Python-env sizing, and per-path breakdowns."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.config import Config
from agent_server.models import StorageCategory
from agent_server.storage_service.path_size import _path_size_bytes


@dataclass(frozen=True)
class _CategorySpec:
    id: str
    label: str
    color: str
    paths: tuple[Path, ...]
    children_from: Path | None = None


def _category_path_label(paths: tuple[Path, ...]) -> str | None:
    if not paths:
        return None
    if len(paths) == 1:
        return str(paths[0])
    return f"{paths[0]} (+{len(paths) - 1} more)"


def _path_children(spec: _CategorySpec) -> list[StorageCategory]:
    """Break multi-path categories into labeled children so Storage shows paths."""
    if len(spec.paths) <= 1:
        return []
    children: list[StorageCategory] = []
    for path in spec.paths:
        resolved = path.expanduser()
        label = resolved.name or str(resolved)
        children.append(
            StorageCategory(
                id=f"{spec.id}:{label}",
                label=label,
                color=spec.color,
                bytes=_path_size_bytes(resolved),
                path=str(resolved),
            )
        )
    return children


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
