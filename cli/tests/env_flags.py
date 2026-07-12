"""Shared env toggles for optional integration and smoke tests."""

from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes"}


def env_flag(*names: str) -> bool:
    """Return True if any of the given env vars is truthy."""
    for name in names:
        if os.environ.get(name, "").strip().lower() in _TRUTHY:
            return True
    return False


def env_value(*names: str, default: str = "") -> str:
    """Return the first non-empty value among the given env vars."""
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default
