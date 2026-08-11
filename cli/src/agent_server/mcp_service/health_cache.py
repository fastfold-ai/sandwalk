"""Cached tool-count / status-message health info for MCP catalog entries."""

from __future__ import annotations

from agent.config import Config


def _tool_count_key(catalog_id: str) -> str:
    return f"mcp.{catalog_id}_tool_count"


def _status_message_key(catalog_id: str) -> str:
    return f"mcp.{catalog_id}_status_message"


def read_tool_count(catalog_id: str, config: Config | None = None) -> int | None:
    cfg = config or Config.load()
    raw = cfg.get(_tool_count_key(catalog_id))
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def save_tool_count(catalog_id: str, tool_count: int) -> None:
    cfg = Config.load()
    cfg.set(_tool_count_key(catalog_id), int(tool_count))
    if cfg.get(_status_message_key(catalog_id)) is not None:
        cfg.unset(_status_message_key(catalog_id))
    cfg.save()


def clear_tool_count(catalog_id: str, config: Config | None = None) -> None:
    cfg = config or Config.load()
    key = _tool_count_key(catalog_id)
    changed = False
    if cfg.get(key) is not None:
        cfg.unset(key)
        changed = True
    if changed:
        cfg.save()


def read_status_message(catalog_id: str, config: Config | None = None) -> str | None:
    cfg = config or Config.load()
    raw = cfg.get(_status_message_key(catalog_id))
    if raw is None or raw == "":
        return None
    return str(raw)


def save_status_message(catalog_id: str, message: str | None) -> None:
    cfg = Config.load()
    key = _status_message_key(catalog_id)
    if message:
        cfg.set(key, str(message)[:500])
    elif cfg.get(key) is not None:
        cfg.unset(key)
    cfg.save()


def clear_health_cache(catalog_id: str, config: Config | None = None) -> None:
    cfg = config or Config.load()
    changed = False
    for key in (_tool_count_key(catalog_id), _status_message_key(catalog_id)):
        if cfg.get(key) is not None:
            cfg.unset(key)
            changed = True
    if changed:
        cfg.save()
