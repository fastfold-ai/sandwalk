"""Small config-reading helpers shared by the markdown/mermaid renderer."""

from __future__ import annotations

from typing import Any


def _config_get(config: Any, key: str, default: Any) -> Any:
    if config is None or not hasattr(config, "get"):
        return default
    try:
        value = config.get(key, default)
    except Exception:
        return default
    return default if value is None else value


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
