"""Parallel MCP load + failure cooldown."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from agent.deepagents_runtime import mcp_tools


@pytest.fixture(autouse=True)
def _clear_caches():
    mcp_tools.clear_mcp_tool_caches()
    yield
    mcp_tools.clear_mcp_tool_caches()


def _server(name: str, url: str = "https://example.com/mcp") -> dict:
    return {
        "name": name,
        "enabled": True,
        "transport": "streamable_http",
        "url": url,
    }


class _Tool:
    def __init__(self, name: str):
        self.name = name


def test_loads_servers_in_parallel_with_timeout():
    started: list[float] = []

    async def slow_load(name: str, connection: dict):
        started.append(time.monotonic())
        await asyncio.sleep(0.35)
        return [_Tool(f"{name}_tool")]

    async def _run():
        with patch.object(mcp_tools, "_load_one_server", side_effect=slow_load):
            t0 = time.monotonic()
            tools = await mcp_tools.create_external_mcp_tools(
                [_server("a"), _server("b", "https://other.example/mcp")],
                per_server_timeout_s=1.0,
                use_cache=False,
            )
            return tools, time.monotonic() - t0

    tools, elapsed = asyncio.run(_run())
    assert {t.name for t in tools} == {"a_tool", "b_tool"}
    # Sequential would be ~0.7s; parallel should finish near one sleep.
    assert elapsed < 0.6
    assert len(started) == 2
    assert abs(started[0] - started[1]) < 0.15


def test_timeout_marks_failure_cooldown():
    async def hang(name: str, connection: dict):
        await asyncio.sleep(2.0)
        return []

    async def _fail():
        with patch.object(mcp_tools, "_load_one_server", side_effect=hang):
            return await mcp_tools.create_external_mcp_tools(
                [_server("latch")],
                per_server_timeout_s=0.05,
                use_cache=True,
            )

    assert asyncio.run(_fail()) == []

    async def _skip():
        with patch.object(
            mcp_tools, "_load_one_server", new_callable=AsyncMock
        ) as mock_load:
            again = await mcp_tools.create_external_mcp_tools(
                [_server("latch")],
                per_server_timeout_s=1.0,
                use_cache=True,
            )
            mock_load.assert_not_called()
            return again

    assert asyncio.run(_skip()) == []


def test_success_cache_skips_reload():
    loads = 0

    async def once(name: str, connection: dict):
        nonlocal loads
        loads += 1
        return [_Tool("ok")]

    async def _run():
        with patch.object(mcp_tools, "_load_one_server", side_effect=once):
            first = await mcp_tools.create_external_mcp_tools(
                [_server("ok")], per_server_timeout_s=1.0, use_cache=True
            )
            second = await mcp_tools.create_external_mcp_tools(
                [_server("ok")], per_server_timeout_s=1.0, use_cache=True
            )
            return first, second

    first, second = asyncio.run(_run())
    assert [t.name for t in first] == ["ok"]
    assert [t.name for t in second] == ["ok"]
    assert loads == 1


def test_concurrent_runs_share_one_load_per_server():
    """A grid fans out N runs at once; the server must be listed only once."""
    loads = 0

    async def slow(name: str, connection: dict):
        nonlocal loads
        loads += 1
        await asyncio.sleep(0.2)
        return [_Tool("shared")]

    def _one_run():
        # Each agent run drives its own loop in its own thread.
        return asyncio.run(
            mcp_tools.create_external_mcp_tools(
                [_server("shared")], per_server_timeout_s=2.0, use_cache=True
            )
        )

    import concurrent.futures

    with patch.object(mcp_tools, "_load_one_server", side_effect=slow):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _i: _one_run(), range(8)))

    assert loads == 1
    assert all([t.name for t in tools] == ["shared"] for tools in results)


def test_stale_entry_is_served_and_refreshed_in_background():
    loads = 0

    async def load(name: str, connection: dict):
        nonlocal loads
        loads += 1
        return [_Tool(f"v{loads}")]

    with patch.object(mcp_tools, "_load_one_server", side_effect=load):
        first = asyncio.run(
            mcp_tools.create_external_mcp_tools(
                [_server("s")], per_server_timeout_s=1.0, use_cache=True
            )
        )
        assert [t.name for t in first] == ["v1"]

        # Age the entry past the fresh TTL but inside the stale window.
        key = next(iter(mcp_tools._success_cache))
        stored_at, tools, names = mcp_tools._success_cache[key]
        mcp_tools._success_cache[key] = (
            stored_at - mcp_tools.SUCCESS_CACHE_TTL_S - 1,
            tools,
            names,
        )

        t0 = time.monotonic()
        second = asyncio.run(
            mcp_tools.create_external_mcp_tools(
                [_server("s")], per_server_timeout_s=1.0, use_cache=True
            )
        )
        # Stale list returned immediately, no blocking on the refresh.
        assert [t.name for t in second] == ["v1"]
        assert time.monotonic() - t0 < 0.5

        # Background refresh lands and the next caller sees the new list.
        deadline = time.monotonic() + 2.0
        while loads < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        for _ in range(50):
            hit = mcp_tools._cached_success(key)
            if hit is not None and hit[2] and [t.name for t in hit[0]] == ["v2"]:
                break
            time.sleep(0.02)
        third = asyncio.run(
            mcp_tools.create_external_mcp_tools(
                [_server("s")], per_server_timeout_s=1.0, use_cache=True
            )
        )
    assert loads == 2
    assert [t.name for t in third] == ["v2"]


def test_entries_older_than_stale_window_are_dropped():
    async def load(name: str, connection: dict):
        return [_Tool("x")]

    with patch.object(mcp_tools, "_load_one_server", side_effect=load):
        asyncio.run(
            mcp_tools.create_external_mcp_tools(
                [_server("old")], per_server_timeout_s=1.0, use_cache=True
            )
        )
        key = next(iter(mcp_tools._success_cache))
        stored_at, tools, names = mcp_tools._success_cache[key]
        mcp_tools._success_cache[key] = (
            stored_at - mcp_tools.STALE_CACHE_MAX_S - 1,
            tools,
            names,
        )
        assert mcp_tools._cached_success(key, allow_stale=True) is None
        assert key not in mcp_tools._success_cache
