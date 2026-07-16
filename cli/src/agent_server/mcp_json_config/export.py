"""Build/validate the mcp.json document shape."""

from __future__ import annotations

from typing import Any

from agent_server.mcp_json_config.entry_convert import export_key, server_to_cursor_entry
from agent_server.mcp_service import get_custom_headers
from agent_server.store import AgentStore


def export_mcp_json(store: AgentStore) -> dict[str, Any]:
    """Build mcp.json document from all servers in the store."""
    servers: dict[str, Any] = {}
    for server in store.list_mcp_servers():
        headers = None
        if not getattr(server, "catalog_id", None):
            headers = get_custom_headers(None, server.id) or None
        key = export_key(server)
        base = key
        n = 2
        while key in servers:
            key = f"{base}-{n}"
            n += 1
        servers[key] = server_to_cursor_entry(server, headers=headers)
    return {"mcpServers": servers}


def parse_mcp_json_document(document: Any) -> dict[str, Any]:
    """Validate top-level shape; return the mcpServers map."""
    if not isinstance(document, dict):
        raise ValueError("mcp.json root must be an object.")
    servers = document.get("mcpServers")
    if servers is None:
        raise ValueError('mcp.json must include an "mcpServers" object.')
    if not isinstance(servers, dict):
        raise ValueError('"mcpServers" must be an object.')
    for name in servers:
        if not str(name).strip():
            raise ValueError("MCP server names must be non-empty.")
    return servers
