"""Load LangChain tools from enabled external MCP servers."""

from __future__ import annotations

from typing import Any


async def create_external_mcp_tools(servers: list[dict] | None) -> list[Any]:
    """Load tools from enabled stdio/SSE/streamable-HTTP MCP servers.

    Aligns with langchain-mcp-adapters / Deep Agents Code connection shape:
    stdio ``command``+``args``(+optional ``env``), remote ``url``+``headers``,
    transport aliases ``http`` / ``streamable-http`` → ``streamable_http``.
    """
    if not servers:
        return []
    from langchain_mcp_adapters.client import MultiServerMCPClient

    connections: dict[str, dict[str, Any]] = {}
    for server in servers:
        if not server.get("enabled", True):
            continue
        name = str(server.get("name") or server.get("id") or "").strip()
        raw_transport = str(
            server.get("transport") or server.get("type") or ""
        ).strip().lower().replace("-", "_")
        if raw_transport in {"http", "streamable_http", "streamablehttp"}:
            transport = "streamable_http"
        elif raw_transport in {"sse", "stdio"}:
            transport = raw_transport
        else:
            continue
        if not name:
            continue
        if transport == "stdio":
            command = str(server.get("command") or "").strip()
            if not command:
                continue
            connection: dict[str, Any] = {
                "transport": "stdio",
                "command": command,
                "args": [str(arg) for arg in server.get("args") or []],
            }
            env = server.get("env")
            if isinstance(env, dict) and env:
                connection["env"] = {str(k): str(v) for k, v in env.items()}
            connections[name] = connection
        else:
            url = str(server.get("url") or "").strip()
            if not url:
                continue
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
            connections[name] = connection
    if not connections:
        return []
    client = MultiServerMCPClient(connections)
    return list(await client.get_tools())
