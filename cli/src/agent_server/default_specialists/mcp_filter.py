"""Filter runtime MCP servers down to a specialist's allowed ids/catalogs."""

from __future__ import annotations

from typing import Any


def filter_mcp_servers_for_specialist(
    servers: list[dict[str, Any]],
    *,
    mcp_server_ids: list[str] | None,
    mcp_catalog_ids: list[str] | None,
) -> list[dict[str, Any]]:
    """Keep runtime MCP servers allowed by specialist server ids and/or catalog ids."""
    allowed_ids = {str(item).strip() for item in (mcp_server_ids or []) if str(item).strip()}
    allowed_catalogs = {
        str(item).strip() for item in (mcp_catalog_ids or []) if str(item).strip()
    }
    if not allowed_ids and not allowed_catalogs:
        return []
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for server in servers:
        server_id = str(server.get("id") or "").strip()
        catalog_id = str(server.get("catalog_id") or "").strip()
        if server_id and server_id in allowed_ids:
            pass
        elif catalog_id and catalog_id in allowed_catalogs:
            pass
        else:
            continue
        key = server_id or catalog_id
        if not key or key in seen:
            continue
        seen.add(key)
        matched.append(server)
    return matched
