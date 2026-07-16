"""Convert between sandwalk McpServer rows and mcp.json ``mcpServers`` entries."""

from __future__ import annotations

from typing import Any

from agent.mcp_catalog import get_catalog_entry

CATALOG_META_KEY = "_sandwalkCatalogId"


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
        entry[CATALOG_META_KEY] = str(catalog_id)
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

    meta_catalog = str(raw.get(CATALOG_META_KEY) or "").strip() or None
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


def export_key(server) -> str:
    catalog_id = getattr(server, "catalog_id", None)
    if catalog_id:
        return str(catalog_id).strip()
    return server.name.strip() or server.id
