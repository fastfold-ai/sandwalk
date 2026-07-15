"""mcp.json export/import for custom (non-catalog) MCP servers.

Format: `{ "mcpServers": { name: config } }` (stdio command/args or remote url/headers).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.config import CONFIG_DIR
from agent_server.mcp_service import (
    clear_custom_headers,
    enrich_mcp_server,
    get_custom_headers,
    set_custom_headers,
)
from agent_server.store import AgentStore

MCP_JSON_PATH = CONFIG_DIR / "mcp.json"


def mcp_json_path() -> Path:
    return MCP_JSON_PATH


def _is_custom(server) -> bool:
    return not getattr(server, "catalog_id", None)


def server_to_cursor_entry(server, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Convert one sandwalk McpServer into an mcpServers entry."""
    entry: dict[str, Any] = {}
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
        if headers:
            entry["headers"] = dict(headers)
    if not server.enabled:
        entry["disabled"] = True
    if server.description:
        entry["description"] = server.description
    return entry


def cursor_entry_to_create_kwargs(name: str, raw: Any) -> tuple[dict[str, Any], dict[str, str] | None]:
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

    # Remote with no credentials stays off until the user authenticates —
    # ignore an explicit enabled:true so paste/import cannot turn them on early.
    if transport != "stdio" and not headers:
        enabled = False
    elif isinstance(enabled_field, bool):
        enabled = enabled_field
    elif disabled:
        enabled = False
    else:
        enabled = True

    # Accept host-only URLs from paste (mcp.example.com → https://…).
    if url_s and "://" not in url_s:
        url_s = f"https://{url_s}"

    description = raw.get("description")
    kwargs = {
        "name": name.strip(),
        "transport": transport,
        "command": command_s,
        "args": args,
        "url": url_s,
        "enabled": enabled,
        "catalog_id": None,
        "description": str(description).strip() if description else None,
    }
    return kwargs, headers


def export_mcp_json(store: AgentStore) -> dict[str, Any]:
    """Build mcp.json document from custom servers in the store."""
    servers: dict[str, Any] = {}
    for server in store.list_mcp_servers():
        if not _is_custom(server):
            continue
        headers = get_custom_headers(None, server.id)
        # Avoid colliding names; prefer first, suffix later duplicates.
        key = server.name.strip() or server.id
        base = key
        n = 2
        while key in servers:
            key = f"{base}-{n}"
            n += 1
        servers[key] = server_to_cursor_entry(server, headers=headers or None)
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
    """Replace custom MCP servers from an mcp.json document.

    Catalog-linked servers are left untouched. Returns the exported document
    after sync (and writes ~/.sandwalk/mcp.json).
    """
    servers_map = parse_mcp_json_document(document)

    existing = [s for s in store.list_mcp_servers() if _is_custom(s)]
    by_name = {s.name.strip().lower(): s for s in existing}
    seen_ids: set[str] = set()

    for name, raw in servers_map.items():
        kwargs, headers = cursor_entry_to_create_kwargs(str(name), raw)
        key = kwargs["name"].lower()
        current = by_name.get(key)
        if current is not None and current.transport == kwargs["transport"]:
            store.update_mcp_server(
                current.id,
                name=kwargs["name"],
                command=kwargs["command"],
                args=kwargs["args"],
                url=kwargs["url"],
                enabled=kwargs["enabled"],
                description=kwargs["description"],
            )
            set_custom_headers(current.id, headers)
            seen_ids.add(current.id)
            continue

        if current is not None:
            store.delete_mcp_server(current.id)
            clear_custom_headers(current.id)

        created = store.create_mcp_server(**kwargs)
        set_custom_headers(created.id, headers)
        seen_ids.add(created.id)

    for server in existing:
        if server.id not in seen_ids:
            store.delete_mcp_server(server.id)
            clear_custom_headers(server.id)

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


def get_or_export_mcp_json(store: AgentStore) -> dict[str, Any]:
    """Return current config: export from DB (authoritative) and mirror to disk."""
    exported = export_mcp_json(store)
    write_mcp_json_file(exported)
    return exported


def list_enriched_custom_servers(store: AgentStore) -> list:
    return [
        enrich_mcp_server(server)
        for server in store.list_mcp_servers()
        if _is_custom(server)
    ]
