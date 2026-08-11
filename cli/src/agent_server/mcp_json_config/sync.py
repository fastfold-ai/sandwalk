"""Reconcile the DB's MCP servers against a parsed mcp.json document."""

from __future__ import annotations

from typing import Any

from agent_server.mcp_json_config.catalog_removed import (
    clear_catalog_removed,
    get_removed_catalog_ids,
    set_removed_catalog_ids,
)
from agent_server.mcp_json_config.entry_convert import cursor_entry_to_create_kwargs
from agent_server.mcp_service import clear_custom_headers, set_custom_headers
from agent_server.store import AgentStore


def sync_servers_from_document(store: AgentStore, servers_map: dict[str, Any]) -> set[str]:
    """Create/update DB rows from the document; returns the set of surviving row ids."""
    existing = list(store.list_mcp_servers())
    by_catalog = {
        str(s.catalog_id).strip(): s for s in existing if getattr(s, "catalog_id", None)
    }
    by_name = {s.name.strip().lower(): s for s in existing if not s.catalog_id}
    seen_ids: set[str] = set()

    for name, raw in servers_map.items():
        kwargs, headers = cursor_entry_to_create_kwargs(str(name), raw)
        catalog_id = kwargs.get("catalog_id")
        current = None
        if catalog_id and catalog_id in by_catalog:
            current = by_catalog[catalog_id]
        elif not catalog_id:
            current = by_name.get(kwargs["name"].lower())

        if current is not None and current.transport == kwargs["transport"]:
            store.update_mcp_server(
                current.id,
                name=kwargs["name"],
                command=kwargs["command"],
                args=kwargs["args"],
                url=kwargs["url"],
                enabled=kwargs["enabled"],
                description=kwargs["description"],
                catalog_id=catalog_id,
            )
            if catalog_id:
                clear_custom_headers(current.id)
                clear_catalog_removed(catalog_id)
            else:
                set_custom_headers(current.id, headers)
            seen_ids.add(current.id)
            continue

        if current is not None:
            store.delete_mcp_server(current.id)
            clear_custom_headers(current.id)

        created = store.create_mcp_server(**kwargs)
        if catalog_id:
            clear_catalog_removed(catalog_id)
        else:
            set_custom_headers(created.id, headers)
        seen_ids.add(created.id)

    return seen_ids


def prune_rows_not_in_document(store: AgentStore, existing: list, seen_ids: set[str]) -> None:
    """Delete DB rows absent from the document and record removed catalog ids."""
    removed = get_removed_catalog_ids()
    for server in existing:
        if server.id in seen_ids:
            continue
        cid = getattr(server, "catalog_id", None)
        if cid:
            removed.add(str(cid).strip())
        store.delete_mcp_server(server.id)
        clear_custom_headers(server.id)
    set_removed_catalog_ids(removed)
