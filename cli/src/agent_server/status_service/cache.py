"""Runtime cache directory helpers for the Status page."""

from __future__ import annotations

import shutil
from pathlib import Path

from agent_server.models import ServerCacheInfo
from agent_server.storage_service import _path_size_bytes


def cache_dir() -> Path:
    # Lazy self-lookup so tests that monkeypatch
    # `agent_server.status_service.CONFIG_DIR` are honored.
    from agent_server import status_service

    return status_service.CONFIG_DIR / "cache"


def _cache_info() -> ServerCacheInfo:
    path = cache_dir()
    file_count = 0
    if path.is_dir():
        try:
            for child in path.rglob("*"):
                try:
                    if child.is_file():
                        file_count += 1
                except OSError:
                    continue
        except OSError:
            pass
    return ServerCacheInfo(
        file_count=file_count,
        total_bytes=_path_size_bytes(path),
        path=str(path),
    )


def clear_cache() -> ServerCacheInfo:
    path = cache_dir()
    if path.is_dir():
        for child in path.iterdir():
            try:
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink(missing_ok=True)
            except OSError:
                continue
    path.mkdir(parents=True, exist_ok=True)
    return _cache_info()
