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
