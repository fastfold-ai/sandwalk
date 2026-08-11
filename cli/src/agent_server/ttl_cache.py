"""Tiny process-local TTL cache for hot list endpoints.

Used so dashboard remounts / Context / Overview do not re-scan SQLite or the
skills tree on every request. Call :func:`invalidate` from mutation paths.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

_lock = threading.Lock()
_entries: dict[str, tuple[float, Any]] = {}


def get(key: str) -> Any | None:
    with _lock:
        hit = _entries.get(key)
        if hit is None:
            return None
        expires, value = hit
        if time.monotonic() >= expires:
            _entries.pop(key, None)
            return None
        return value


def set(key: str, value: Any, *, ttl_s: float) -> None:
    if ttl_s <= 0:
        return
    with _lock:
        _entries[key] = (time.monotonic() + ttl_s, value)


def invalidate(prefix: str | None = None) -> None:
    with _lock:
        if not prefix:
            _entries.clear()
            return
        for key in [k for k in _entries if k == prefix or k.startswith(prefix)]:
            _entries.pop(key, None)


def cached(key: str, ttl_s: float, factory: Callable[[], T]) -> T:
    hit = get(key)
    if hit is not None:
        return hit  # type: ignore[no-any-return]
    value = factory()
    set(key, value, ttl_s=ttl_s)
    return value
