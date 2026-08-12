"""Process-local TTL cache for hot list endpoints."""

from __future__ import annotations

import time

from agent_server import ttl_cache


def test_ttl_cache_hit_and_expire():
    ttl_cache.invalidate()
    calls = {"n": 0}

    def factory() -> str:
        calls["n"] += 1
        return "ok"

    assert ttl_cache.cached("k", 0.2, factory) == "ok"
    assert ttl_cache.cached("k", 0.2, factory) == "ok"
    assert calls["n"] == 1
    time.sleep(0.25)
    assert ttl_cache.cached("k", 0.2, factory) == "ok"
    assert calls["n"] == 2


def test_ttl_cache_invalidate_prefix():
    ttl_cache.invalidate()
    ttl_cache.set("skills:list", [1], ttl_s=60)
    ttl_cache.set("mcp:servers", [2], ttl_s=60)
    ttl_cache.invalidate("skills:")
    assert ttl_cache.get("skills:list") is None
    assert ttl_cache.get("mcp:servers") == [2]
