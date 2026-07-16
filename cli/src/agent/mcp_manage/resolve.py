"""Server/catalog resolution helpers shared by mcp management commands."""

from __future__ import annotations

from agent.mcp_catalog import get_catalog_entry
from agent_server.mcp_service import McpService
from agent_server.store import AgentStore


def _store() -> AgentStore:
    return AgentStore()


def _service(store: AgentStore | None = None) -> McpService:
    return McpService(store or _store())


def resolve_server_ref(ref: str, store: AgentStore | None = None):
    """Resolve catalog id, server UUID, or case-insensitive name."""
    agent_store = store or _store()
    key = (ref or "").strip()
    if not key:
        return None, None
    # Catalog id first
    entry = get_catalog_entry(key.lower())
    if entry:
        server = next(
            (
                s
                for s in agent_store.list_mcp_servers()
                if getattr(s, "catalog_id", None) == entry.id
            ),
            None,
        )
        return entry, server
    servers = agent_store.list_mcp_servers()
    for server in servers:
        if server.id == key or server.id.startswith(key):
            return (
                get_catalog_entry(server.catalog_id) if server.catalog_id else None,
                server,
            )
    lowered = key.lower()
    for server in servers:
        if server.name.lower() == lowered:
            return (
                get_catalog_entry(server.catalog_id) if server.catalog_id else None,
                server,
            )
    return None, None
