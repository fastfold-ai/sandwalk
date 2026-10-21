"""Seed/prune featured catalog templates and list custom/suggested servers."""

from __future__ import annotations

import sqlite3
import threading

from agent.mcp_catalog import MCP_CATALOG, catalog_create_kwargs
from agent_server.mcp_json_config.catalog_removed import get_removed_catalog_ids
from agent_server.mcp_service import enrich_mcp_server
from agent_server.store import AgentStore

_SEED_LOCK = threading.Lock()


def prune_obsolete_catalog_servers(store: AgentStore) -> int:
    """Delete DB rows whose catalog_id is no longer in MCP_CATALOG.

    Keeps custom servers (no catalog_id). Returns number deleted.
    """
    known = {entry.id for entry in MCP_CATALOG}
    deleted = 0
    for server in store.list_mcp_servers():
        catalog_id = getattr(server, "catalog_id", None)
        if not catalog_id:
            continue
        if str(catalog_id).strip() in known:
            continue
        if store.delete_mcp_server(server.id):
            deleted += 1
    return deleted


def seed_catalog_defaults(store: AgentStore) -> int:
    """Ensure non-removed featured catalog templates exist as DB rows (disabled).

    Non-featured catalog entries are opt-in via install / Suggested after remove.
    Returns the number of newly created servers.
    """
    with _SEED_LOCK:
        removed = get_removed_catalog_ids()
        by_catalog = {
            str(s.catalog_id).strip(): s
            for s in store.list_mcp_servers()
            if getattr(s, "catalog_id", None)
        }
        created = 0
        for entry in MCP_CATALOG:
            if not entry.featured:
                continue
            if entry.id in removed:
                continue
            if entry.id in by_catalog:
                continue
            try:
                store.create_mcp_server(**catalog_create_kwargs(entry, enabled=False))
                created += 1
            except sqlite3.IntegrityError:
                pass
        return created


def list_enriched_custom_servers(store: AgentStore) -> list:
    """Custom-only servers (no catalog_id) — kept for callers that need that slice."""
    return [
        enrich_mcp_server(server)
        for server in store.list_mcp_servers()
        if not getattr(server, "catalog_id", None)
    ]


def suggested_catalog_ids(store: AgentStore) -> list[str]:
    """Featured catalog templates not currently installed (typically user-removed)."""
    installed = {
        str(s.catalog_id).strip()
        for s in store.list_mcp_servers()
        if getattr(s, "catalog_id", None)
    }
    out: list[str] = []
    for entry in MCP_CATALOG:
        if not entry.featured:
            continue
        if entry.id not in installed:
            out.append(entry.id)
    return out
