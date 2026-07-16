"""Config coercion helpers and clamp ranges shared across runtime settings."""

from __future__ import annotations

from agent.config import Config

DEFAULT_RECURSION_LIMIT = 120
MIN_RECURSION_LIMIT = 25
MAX_RECURSION_LIMIT = 2000
ONBOARDING_MAX_STEP = 6


def clamp_int(value: object, *, minimum: int, maximum: int, default: int) -> int:
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return default
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def recursion_limit_from_config(config: Config) -> int:
    raw = config.get("agent.recursion_limit")
    if raw is None or str(raw).strip() == "":
        max_turns = int(config.get("agent.max_sdk_turns", 30) or 30)
        return max(MIN_RECURSION_LIMIT, max_turns * 2 + 10)
    return clamp_int(
        raw,
        minimum=MIN_RECURSION_LIMIT,
        maximum=MAX_RECURSION_LIMIT,
        default=DEFAULT_RECURSION_LIMIT,
    )


def bool_from_config(config: Config, key: str, default: bool) -> bool:
    raw = config.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}
