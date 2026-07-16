"""mcp.json export/import for MCP servers (custom + seeded catalog).

Format: `{ "mcpServers": { name: config } }` (stdio command/args or remote url/headers).
Catalog seeds keep ``catalog_id`` in the DB; mcp.json stores ``_sandwalkCatalogId``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.config import CONFIG_DIR, Config
from agent.mcp_catalog import MCP_CATALOG, get_catalog_entry
from agent_server.mcp_service import (
    clear_custom_headers,
    enrich_mcp_server,
    get_custom_headers,
    set_custom_headers,
)
from agent_server.store import AgentStore

_REMOVED_CATALOG_IDS_KEY = "mcp.removed_catalog_ids"
_CATALOG_META_KEY = "_sandwalkCatalogId"


def mcp_json_path() -> Path:
    # Resolve at call time so tests can monkeypatch CONFIG_DIR.
    return CONFIG_DIR / "mcp.json"


def get_removed_catalog_ids(config: Config | None = None) -> set[str]:
    cfg = config or Config.load()
    raw = cfg.get(_REMOVED_CATALOG_IDS_KEY)
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if str(item).strip()}


def set_removed_catalog_ids(ids: set[str], *, config: Config | None = None) -> None:
    cfg = config or Config.load()
    cleaned = sorted({str(item).strip() for item in ids if str(item).strip()})
    if cleaned:
        cfg.set(_REMOVED_CATALOG_IDS_KEY, cleaned)
    elif cfg.get(_REMOVED_CATALOG_IDS_KEY) is not None:
        cfg.unset(_REMOVED_CATALOG_IDS_KEY)
    cfg.save()


def mark_catalog_removed(catalog_id: str) -> None:
    cid = catalog_id.strip()
    if not cid:
        return
    removed = get_removed_catalog_ids()
    removed.add(cid)
    set_removed_catalog_ids(removed)


def clear_catalog_removed(catalog_id: str) -> None:
    cid = catalog_id.strip()
    if not cid:
        return
    removed = get_removed_catalog_ids()
    if cid not in removed:
        return
    removed.discard(cid)
    set_removed_catalog_ids(removed)


def server_to_cursor_entry(server, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Convert one sandwalk McpServer into an mcpServers entry."""
    entry: dict[str, Any] = {}
    catalog_id = getattr(server, "catalog_id", None)
    if server.transport == "stdio" or server.command:
        entry["command"] = server.command or ""
        if server.args:
            entry["args"] = list(server.args)
        entry["type"] = "stdio"
    else:
        entry["url"] = server.url or ""
        if server.transport == "sse":
            entry["type"] = "sse"
        else:
            entry["type"] = "http"
        # Catalog creds live in config.json / Integrations — never mirror into mcp.json.
        if headers and not catalog_id:
            entry["headers"] = dict(headers)
    if not server.enabled:
        entry["disabled"] = True
    if server.description:
        entry["description"] = server.description
    if catalog_id:
        entry[_CATALOG_META_KEY] = str(catalog_id)
    return entry


def cursor_entry_to_create_kwargs(
    name: str, raw: Any
) -> tuple[dict[str, Any], dict[str, str] | None]:
    """Parse one mcpServers entry into store.create_mcp_server kwargs + optional headers."""
    if not isinstance(raw, dict):
        raise ValueError(f'MCP "{name}" must be an object.')

    command = raw.get("command")
    url = raw.get("url")
    args_raw = raw.get("args") or []
    if not isinstance(args_raw, list):
        raise ValueError(f'MCP "{name}" args must be an array.')
    args = [str(item) for item in args_raw]

    type_hint = str(raw.get("type") or "").strip().lower()
    if command or type_hint == "stdio":
        if not str(command or "").strip():
            raise ValueError(f'MCP "{name}" stdio entry requires a command.')
        transport = "stdio"
        command_s = str(command).strip()
        url_s = None
    else:
        if not str(url or "").strip():
            raise ValueError(f'MCP "{name}" remote entry requires a url.')
        transport = "sse" if type_hint == "sse" else "streamable_http"
        command_s = None
        url_s = str(url).strip()

    disabled = bool(raw.get("disabled"))
    enabled_field = raw.get("enabled")

    headers: dict[str, str] | None = None
    headers_raw = raw.get("headers")
    if isinstance(headers_raw, dict):
        headers = {
            str(key).strip(): str(value)
            for key, value in headers_raw.items()
            if str(key).strip() and str(value)
        } or None

    meta_catalog = str(raw.get(_CATALOG_META_KEY) or "").strip() or None
    name_s = name.strip()
    catalog_id = meta_catalog
    if not catalog_id and get_catalog_entry(name_s):
        catalog_id = name_s
    entry = get_catalog_entry(catalog_id) if catalog_id else None
    if entry is not None:
        if not url_s and entry.url:
            url_s = entry.url
            transport = entry.transport
            command_s = None
        display_name = entry.name
    else:
        display_name = name_s

    # Remote with no credentials stays off until the user authenticates —
    # ignore an explicit enabled:true so paste/import cannot turn them on early.
    # Catalog remotes use Integrations/OAuth, not mcp.json headers.
    if transport != "stdio" and not headers and not catalog_id:
        enabled = False
    elif isinstance(enabled_field, bool):
        enabled = enabled_field
    elif disabled:
        enabled = False
    else:
        # Catalog seeds default off even if file omits disabled.
        enabled = False if catalog_id else True

    if url_s and "://" not in url_s:
        url_s = f"https://{url_s}"

    description = raw.get("description")
    if description is None and entry is not None:
        description = entry.description
    kwargs = {
        "name": display_name,
        "transport": transport,
        "command": command_s,
        "args": args,
        "url": url_s,
        "enabled": enabled,
        "catalog_id": catalog_id,
        "description": str(description).strip() if description else None,
    }
    return kwargs, headers


def _export_key(server) -> str:
    catalog_id = getattr(server, "catalog_id", None)
    if catalog_id:
        return str(catalog_id).strip()
    return server.name.strip() or server.id


def export_mcp_json(store: AgentStore) -> dict[str, Any]:
    """Build mcp.json document from all servers in the store."""
    servers: dict[str, Any] = {}
    for server in store.list_mcp_servers():
        headers = None
        if not getattr(server, "catalog_id", None):
            headers = get_custom_headers(None, server.id) or None
        key = _export_key(server)
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


def apply_mcp_json(store: AgentStore, document: Any) -> dict[str, Any]:
    """Replace MCP servers from an mcp.json document (custom + catalog seeds).

    Catalog rows removed from the file are deleted and recorded in
    ``mcp.removed_catalog_ids``. Returns the exported document after sync.
    """
    servers_map = parse_mcp_json_document(document)

    existing = list(store.list_mcp_servers())
    by_catalog = {
        str(s.catalog_id).strip(): s
        for s in existing
        if getattr(s, "catalog_id", None)
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

    exported = export_mcp_json(store)
    write_mcp_json_file(exported)
    return exported


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


def seed_catalog_defaults(store: AgentStore) -> int:
    """Ensure non-removed catalog templates exist as DB rows (disabled).

    Returns the number of newly created servers.
    """
    removed = get_removed_catalog_ids()
    by_catalog = {
        str(s.catalog_id).strip(): s
        for s in store.list_mcp_servers()
        if getattr(s, "catalog_id", None)
    }
    created = 0
    for entry in MCP_CATALOG:
        if entry.id in removed:
            continue
        if entry.id in by_catalog:
            continue
        store.create_mcp_server(
            name=entry.name,
            transport=entry.transport,
            command=None,
            args=[],
            url=entry.url,
            enabled=False,
            catalog_id=entry.id,
            description=entry.description,
        )
        created += 1
    return created


def install_catalog_server(store: AgentStore, catalog_id: str):
    """Re-add a catalog template (clears removed flag) and return the DB row."""
    entry = get_catalog_entry(catalog_id)
    if entry is None:
        raise KeyError(catalog_id)
    clear_catalog_removed(catalog_id)
    existing = next(
        (
            s
            for s in store.list_mcp_servers()
            if getattr(s, "catalog_id", None) == catalog_id
        ),
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


def get_or_export_mcp_json(store: AgentStore) -> dict[str, Any]:
    """Seed catalog defaults, export from DB (authoritative), mirror to disk."""
    seed_catalog_defaults(store)
    exported = export_mcp_json(store)
    write_mcp_json_file(exported)
    return exported


def list_enriched_custom_servers(store: AgentStore) -> list:
    """Custom-only servers (no catalog_id) — kept for callers that need that slice."""
    return [
        enrich_mcp_server(server)
        for server in store.list_mcp_servers()
        if not getattr(server, "catalog_id", None)
    ]


def suggested_catalog_ids(store: AgentStore) -> list[str]:
    """Catalog templates not currently installed (typically user-removed)."""
    installed = {
        str(s.catalog_id).strip()
        for s in store.list_mcp_servers()
        if getattr(s, "catalog_id", None)
    }
    out: list[str] = []
    for entry in MCP_CATALOG:
        if entry.id not in installed:
            out.append(entry.id)
    return out
