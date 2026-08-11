"""Load LangChain tools from enabled external MCP servers.

Performance notes (simple, current-gen):
- Load servers **in parallel** with a short per-server timeout so one dead
  remote (Latch/Exa/…) cannot serialize agent startup or Context estimates.
- Keep a short **failure cooldown** so we stop re-probing known-down servers
  on every session/estimate.
- Cache successful discovery briefly — HTTP/streamable MCP is moving toward a
  **stateless** request/response core (MCP 2026-07-28), so reconnecting is
  cheap; we still avoid hammering healthy servers on every UI poll.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, TextIO

logger = logging.getLogger("runner")

_stdio_errlog_sink: TextIO | None = None
_stdio_errlog_installed = False

# Dead remotes are expected; keep walls short so the rest of the app stays snappy.
DEFAULT_HTTP_TIMEOUT_S = 5.0
DEFAULT_STDIO_TIMEOUT_S = 8.0
FAILURE_COOLDOWN_S = 60.0
SUCCESS_CACHE_TTL_S = 120.0

_cache_lock = threading.Lock()
_failure_until: dict[str, float] = {}
_success_cache: dict[str, tuple[float, list[Any], list[str]]] = {}


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


def _cache_key(name: str, connection: dict[str, Any]) -> str:
    transport = str(connection.get("transport") or "")
    if transport == "stdio":
        args = " ".join(str(a) for a in (connection.get("args") or []))
        return f"stdio:{name}:{connection.get('command')}:{args}"
    return f"{transport}:{name}:{connection.get('url')}"


def _default_timeout(connection: dict[str, Any]) -> float:
    if connection.get("transport") == "stdio":
        return DEFAULT_STDIO_TIMEOUT_S
    return DEFAULT_HTTP_TIMEOUT_S


def _mark_failure(key: str) -> None:
    with _cache_lock:
        _failure_until[key] = time.monotonic() + FAILURE_COOLDOWN_S
        _success_cache.pop(key, None)


def _mark_success(key: str, tools: list[Any], tool_names: list[str]) -> None:
    with _cache_lock:
        _failure_until.pop(key, None)
        _success_cache[key] = (
            time.monotonic() + SUCCESS_CACHE_TTL_S,
            list(tools),
            list(tool_names),
        )


def _cached_success(key: str) -> tuple[list[Any], list[str]] | None:
    with _cache_lock:
        hit = _success_cache.get(key)
        if hit is None:
            return None
        expires, tools, names = hit
        if time.monotonic() >= expires:
            _success_cache.pop(key, None)
            return None
        return list(tools), list(names)


def _in_failure_cooldown(key: str) -> bool:
    with _cache_lock:
        until = _failure_until.get(key)
        if until is None:
            return False
        if time.monotonic() >= until:
            _failure_until.pop(key, None)
            return False
        return True


def clear_mcp_tool_caches() -> None:
    """Test helper / manual reset after MCP settings change."""
    with _cache_lock:
        _failure_until.clear()
        _success_cache.clear()


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


def _index_keys_for_server(server: dict[str, Any], connection_name: str) -> list[str]:
    """Stable keys so mcp: chips can resolve loaded tool names."""
    keys: list[str] = []
    for field in ("catalog_id", "id", "name"):
        value = str(server.get(field) or "").strip()
        if value:
            keys.append(value)
            keys.append(value.lower().replace("_", "-").replace(" ", "-"))
    conn = str(connection_name or "").strip()
    if conn:
        keys.append(conn)
        keys.append(conn.lower().replace("_", "-").replace(" ", "-"))
    # Preserve order, drop dupes.
    out: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _tool_names(tools: list[Any]) -> list[str]:
    names: list[str] = []
    for tool in tools:
        tool_name = str(getattr(tool, "name", "") or "").strip()
        if tool_name and tool_name not in names:
            names.append(tool_name)
    return names


async def _load_server_entry(
    *,
    server: dict[str, Any],
    name: str,
    connection: dict[str, Any],
    timeout_s: float,
    use_cache: bool,
) -> tuple[str, list[Any], list[str]]:
    key = _cache_key(name, connection)
    if use_cache:
        cached = _cached_success(key)
        if cached is not None:
            return name, cached[0], cached[1]
        if _in_failure_cooldown(key):
            logger.debug("Skipping MCP %s (failure cooldown)", name)
            return name, [], []

    try:
        loaded = await asyncio.wait_for(
            _load_one_server(name, connection),
            timeout=timeout_s,
        )
    except TimeoutError:
        logger.warning(
            "Timed out loading MCP tools from %s after %.1fs",
            name,
            timeout_s,
        )
        if use_cache:
            _mark_failure(key)
        return name, [], []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unable to load MCP tools from %s: %s", name, exc)
        if use_cache:
            _mark_failure(key)
        return name, [], []

    names = _tool_names(loaded)
    if use_cache:
        _mark_success(key, loaded, names)
    return name, loaded, names


async def create_external_mcp_tools(
    servers: list[dict] | None,
    *,
    out_tools_by_server: dict[str, list[str]] | None = None,
    per_server_timeout_s: float | None = None,
    use_cache: bool = True,
) -> list[Any]:
    """Load tools from enabled stdio/SSE/streamable-HTTP MCP servers.

    Each server is loaded independently (and in parallel) so one failing remote
    (expired OAuth, unreachable host, …) does not drop healthy servers like
    local PyMOL, and does not add its full latency to every other server.

    When ``out_tools_by_server`` is provided, it is filled with tool name lists
    keyed by catalog id / server id / display name for mcp: mention steering.

    ``per_server_timeout_s`` overrides the default timeout (5s HTTP/SSE, 8s
    stdio). Context estimates pass a tighter value.
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

    planned: list[tuple[dict[str, Any], str, dict[str, Any], float]] = []
    for server in servers:
        entry = _connection_for_server(server)
        if entry is None:
            continue
        name, connection = entry
        timeout = (
            float(per_server_timeout_s)
            if per_server_timeout_s is not None and per_server_timeout_s > 0
            else _default_timeout(connection)
        )
        planned.append((server, name, connection, timeout))

    if not planned:
        return []

    results = await asyncio.gather(
        *[
            _load_server_entry(
                server=server,
                name=name,
                connection=connection,
                timeout_s=timeout,
                use_cache=use_cache,
            )
            for server, name, connection, timeout in planned
        ]
    )

    tools: list[Any] = []
    seen_names: set[str] = set()
    for (server, name, _connection, _timeout), (_n, loaded, server_tool_names) in zip(
        planned, results, strict=True
    ):
        for tool in loaded:
            tool_name = str(getattr(tool, "name", "") or "").strip()
            if not tool_name or tool_name in seen_names:
                continue
            seen_names.add(tool_name)
            tools.append(tool)
        if out_tools_by_server is not None and server_tool_names:
            for key in _index_keys_for_server(server, name):
                out_tools_by_server[key] = list(server_tool_names)
    return tools
