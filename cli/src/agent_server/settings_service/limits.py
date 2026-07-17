"""Config coercion helpers and clamp ranges shared across runtime settings."""

from __future__ import annotations

from agent.config import Config

# LangGraph requires a finite recursion_limit; treat "unlimited" as a huge cap.
DEFAULT_RECURSION_LIMIT = 100_000
MIN_RECURSION_LIMIT = 25
MAX_RECURSION_LIMIT = 1_000_000
UNLIMITED_RECURSION_LIMIT = 1_000_000
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
        return DEFAULT_RECURSION_LIMIT
    text = str(raw).strip().lower()
    if text in {"0", "unlimited", "none", "inf", "infinite"}:
        return UNLIMITED_RECURSION_LIMIT
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
