"""Load LangChain tools from enabled external MCP servers."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, TextIO

logger = logging.getLogger("runner")

_stdio_errlog_sink: TextIO | None = None
_stdio_errlog_installed = False


def _connection_for_server(server: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Build a MultiServerMCPClient connection entry, or None if unusable."""
    if not server.get("enabled", True):
        return None
    name = str(server.get("name") or server.get("id") or "").strip()
    raw_transport = (
        str(server.get("transport") or server.get("type") or "")
        .strip()
        .lower()
        .replace("-", "_")
    )
    if raw_transport in {"http", "streamable_http", "streamablehttp"}:
        transport = "streamable_http"
    elif raw_transport in {"sse", "stdio"}:
        transport = raw_transport
    else:
        return None
    if not name:
        return None
    if transport == "stdio":
        command = str(server.get("command") or "").strip()
        if not command:
            return None
        connection: dict[str, Any] = {
            "transport": "stdio",
            "command": command,
            "args": [str(arg) for arg in server.get("args") or []],
        }
        env = server.get("env")
        if isinstance(env, dict) and env:
            connection["env"] = {str(k): str(v) for k, v in env.items()}
        return name, connection

    url = str(server.get("url") or "").strip()
    if not url:
        return None
    connection = {
        "transport": transport,
        "url": url,
    }
    headers = server.get("headers")
    merged: dict[str, str] = {}
    if isinstance(headers, dict) and headers:
        merged = {str(key): str(value) for key, value in headers.items()}
    # Cloudflare blocks Python default UAs (e.g. Better Stack Error 1010).
    if not any(k.lower() == "user-agent" for k in merged):
        merged["User-Agent"] = (
            "Sandwalk/0.1 (MCP; +https://github.com/fastfold-ai/sandwalk)"
        )
    connection["headers"] = merged
    return name, connection


def ensure_quiet_stdio_mcp_errlog() -> None:
    """Route all MCP stdio child stderr away from the TTY for this process.

    LangChain opens a **new** stdio session per tool call, and
    ``mcp.client.stdio.stdio_client`` defaults ``errlog=sys.stderr``. Child
    INFO (Rich FastMCP / PyMOL client) therefore paints over the interactive
    TUI. ``patch_stdout`` cannot catch another process's fd writes — patch the
    adapter once and leave it installed for the process lifetime.
    """
    global _stdio_errlog_sink, _stdio_errlog_installed
    if _stdio_errlog_installed:
        return

    import langchain_mcp_adapters.sessions as sessions
    from mcp.client.stdio import stdio_client as real_stdio_client

    sink: TextIO = open(os.devnull, "w")
    original = sessions.stdio_client

    @asynccontextmanager
    async def quiet_stdio(server, errlog: TextIO | None = None):
        async with real_stdio_client(server, errlog=errlog or sink) as streams:
            yield streams

    sessions.stdio_client = quiet_stdio
    _stdio_errlog_sink = sink
    _stdio_errlog_installed = True
    _ = original  # replaced for process lifetime; kept for clarity


async def _load_one_server(name: str, connection: dict[str, Any]) -> list[Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    if connection.get("transport") == "stdio":
        ensure_quiet_stdio_mcp_errlog()
    client = MultiServerMCPClient({name: connection})
    return list(await client.get_tools())


async def create_external_mcp_tools(servers: list[dict] | None) -> list[Any]:
    """Load tools from enabled stdio/SSE/streamable-HTTP MCP servers.

    Each server is loaded independently so one failing remote (expired OAuth,
    unreachable host, …) does not drop healthy servers like local PyMOL.
    """
    if not servers:
        return []

    # Install before any tool object is returned — invocations re-open stdio.
    if any(
        (entry := _connection_for_server(server)) is not None
        and entry[1].get("transport") == "stdio"
        for server in servers
    ):
        ensure_quiet_stdio_mcp_errlog()

    tools: list[Any] = []
    seen_names: set[str] = set()
    for server in servers:
        entry = _connection_for_server(server)
        if entry is None:
            continue
        name, connection = entry
        try:
            loaded = await _load_one_server(name, connection)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Unable to load MCP tools from %s: %s",
                name,
                exc,
            )
            continue
        for tool in loaded:
            tool_name = str(getattr(tool, "name", "") or "").strip()
            if not tool_name or tool_name in seen_names:
                continue
            seen_names.add(tool_name)
            tools.append(tool)
    return tools
