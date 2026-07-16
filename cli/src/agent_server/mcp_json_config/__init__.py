"""mcp.json export/import for MCP servers (custom + seeded catalog).

Format: `{ "mcpServers": { name: config } }` (stdio command/args or remote url/headers).
Catalog seeds keep ``catalog_id`` in the DB; mcp.json stores ``_sandwalkCatalogId``.

Split package — re-exports the public surface previously defined in
``agent_server/mcp_json_config.py`` so existing imports keep working.

NOTE: ``CONFIG_DIR`` and ``mcp_json_path`` stay bound at this package-root
level (not in a submodule) because tests patch ``CONFIG_DIR`` via the flat
dotted path ``agent_server.mcp_json_config.CONFIG_DIR``, and every function
that resolves the mcp.json path (directly or by calling ``mcp_json_path``)
must live in this same module namespace for that patch to take effect.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.config import CONFIG_DIR, Config
from agent.mcp_catalog import get_catalog_entry
from agent_server.mcp_json_config.catalog_removed import (
    clear_catalog_removed,
    get_removed_catalog_ids,
    mark_catalog_removed,
    set_removed_catalog_ids,
)
from agent_server.mcp_json_config.catalog_seed import (
    list_enriched_custom_servers,
    prune_obsolete_catalog_servers,
    seed_catalog_defaults,
    suggested_catalog_ids,
)
from agent_server.mcp_json_config.entry_convert import (
    cursor_entry_to_create_kwargs,
    export_key,
    server_to_cursor_entry,
)
from agent_server.mcp_json_config.export import export_mcp_json, parse_mcp_json_document
from agent_server.mcp_json_config.sync import (
    prune_rows_not_in_document,
    sync_servers_from_document,
)
from agent_server.store import AgentStore

_REMOVED_CATALOG_IDS_KEY = "mcp.removed_catalog_ids"
_CATALOG_META_KEY = "_sandwalkCatalogId"


def mcp_json_path() -> Path:
    # Resolve at call time so tests can monkeypatch CONFIG_DIR.
    return CONFIG_DIR / "mcp.json"


def write_mcp_json_file(document: dict[str, Any]) -> Path:
    path = mcp_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def read_mcp_json_file() -> dict[str, Any] | None:
    path = mcp_json_path()
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        parse_mcp_json_document(parsed)
    except ValueError:
        return None
    return parsed


def apply_mcp_json(store: AgentStore, document: Any) -> dict[str, Any]:
    """Replace MCP servers from an mcp.json document (custom + catalog seeds).

    Catalog rows removed from the file are deleted and recorded in
    ``mcp.removed_catalog_ids``. Returns the exported document after sync.
    """
    servers_map = parse_mcp_json_document(document)
    existing = list(store.list_mcp_servers())
    seen_ids = sync_servers_from_document(store, servers_map)
    prune_rows_not_in_document(store, existing, seen_ids)

    exported = export_mcp_json(store)
    write_mcp_json_file(exported)
    return exported


def get_or_export_mcp_json(store: AgentStore) -> dict[str, Any]:
    """Seed catalog defaults, export from DB (authoritative), mirror to disk."""
    prune_obsolete_catalog_servers(store)
    seed_catalog_defaults(store)
    exported = export_mcp_json(store)
    write_mcp_json_file(exported)
    return exported


def install_catalog_server(store: AgentStore, catalog_id: str):
    """Re-add a catalog template (clears removed flag) and return the DB row."""
    entry = get_catalog_entry(catalog_id)
    if entry is None:
        raise KeyError(catalog_id)
    clear_catalog_removed(catalog_id)
    existing = next(
        (s for s in store.list_mcp_servers() if getattr(s, "catalog_id", None) == catalog_id),
        None,
    )
    if existing is not None:
        get_or_export_mcp_json(store)
        return existing
    server = store.create_mcp_server(
        name=entry.name,
        transport=entry.transport,
        command=None,
        args=[],
        url=entry.url,
        enabled=False,
        catalog_id=entry.id,
        description=entry.description,
    )
    get_or_export_mcp_json(store)
    return server


__all__ = [
    "mcp_json_path",
    "write_mcp_json_file",
    "read_mcp_json_file",
    "apply_mcp_json",
    "get_or_export_mcp_json",
    "install_catalog_server",
    "export_mcp_json",
    "parse_mcp_json_document",
    "server_to_cursor_entry",
    "cursor_entry_to_create_kwargs",
    "export_key",
    "get_removed_catalog_ids",
    "set_removed_catalog_ids",
    "mark_catalog_removed",
    "clear_catalog_removed",
    "prune_obsolete_catalog_servers",
    "seed_catalog_defaults",
    "list_enriched_custom_servers",
    "suggested_catalog_ids",
    "Config",
]
