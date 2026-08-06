"""``McpService.validate`` — live probe for a catalog entry or arbitrary server."""

from __future__ import annotations

from typing import Any

from agent.config import Config
from agent.mcp_catalog import get_catalog_entry, resolve_catalog_command
from agent_server.mcp_service.auth import (
    credentials_configured,
    oauth_reconnect_required,
    resolve_auth_headers,
)
from agent_server.mcp_service.custom_server import (
    custom_tool_count_id,
    resolve_custom_server_headers,
)
from agent_server.mcp_service.health_cache import (
    clear_tool_count,
    save_status_message,
    save_tool_count,
)


class ValidateMixin:
    def validate(self, catalog_id: str | None = None, server_id: str | None = None) -> dict[str, Any]:
        from agent_server import mcp_service as _mcp_service

        cfg = Config.load()
        if catalog_id:
            entry = get_catalog_entry(catalog_id)
            if entry is None:
                raise KeyError(catalog_id)
            if entry.transport == "stdio":
                if not credentials_configured(entry, cfg):
                    return {
                        "ok": False,
                        "toolCount": 0,
                        "message": (
                            "Launcher not installed — run sandwalk mcp install pymol "
                            "or in PyMOL: sandwalk-pymol setup"
                            if entry.id == "pymol"
                            else "stdio command not ready"
                        ),
                        "tools": [],
                        "toolDetails": [],
                    }
                command = resolve_catalog_command(entry)
                result = _mcp_service.probe_stdio_mcp_server(
                    command=command or "",
                    args=list(entry.args or []),
                ) or {
                    "ok": False,
                    "toolCount": 0,
                    "message": "stdio probe failed",
                    "tools": [],
                    "toolDetails": [],
                }
                if result.get("ok"):
                    save_tool_count(catalog_id, int(result.get("toolCount") or 0))
                else:
                    clear_tool_count(catalog_id)
                    save_status_message(
                        catalog_id, str(result.get("message") or "stdio probe failed")
                    )
                return result

            headers = resolve_auth_headers(entry, cfg)
            if not headers:
                return {
                    "ok": False,
                    "toolCount": 0,
                    "message": "Not configured — Connect with OAuth or API key first",
                    "tools": [],
                    "toolDetails": [],
                }
            reconnect = oauth_reconnect_required(entry, cfg)
            if reconnect:
                save_status_message(catalog_id, reconnect)
                clear_tool_count(catalog_id)
                return {
                    "ok": False,
                    "toolCount": 0,
                    "message": reconnect,
                    "tools": [],
                    "toolDetails": [],
                }
            result = _mcp_service.probe_mcp_server(
                url=entry.url or "", headers=headers
            )
            if result.get("ok"):
                save_tool_count(catalog_id, int(result.get("toolCount") or 0))
                save_status_message(catalog_id, None)
            else:
                clear_tool_count(catalog_id)
                save_status_message(
                    catalog_id, str(result.get("message") or "Connection failed")
                )
            return result

        if server_id:
            server = next(
                (s for s in self.store.list_mcp_servers() if s.id == server_id),
                None,
            )
            if server is None:
                raise KeyError(server_id)
            if server.transport == "stdio" or (server.command and not server.url):
                command = str(server.command or "").strip()
                if getattr(server, "catalog_id", None):
                    entry = get_catalog_entry(server.catalog_id)
                    if entry and entry.transport == "stdio":
                        command = resolve_catalog_command(entry) or command
                result = _mcp_service.probe_stdio_mcp_server(
                    command=command,
                    args=list(server.args or []),
                ) or {
                    "ok": False,
                    "toolCount": 0,
                    "message": "stdio probe failed",
                    "tools": [],
                    "toolDetails": [],
                }
                if not getattr(server, "catalog_id", None):
                    count_id = custom_tool_count_id(server_id)
                    if result.get("ok"):
                        save_tool_count(count_id, int(result.get("toolCount") or 0))
                    else:
                        clear_tool_count(count_id)
                return result

            headers: dict[str, str] | None = None
            if getattr(server, "catalog_id", None):
                entry = get_catalog_entry(server.catalog_id)
                if entry:
                    headers = resolve_auth_headers(entry, cfg)
            else:
                headers = resolve_custom_server_headers(server, config=cfg)
            if not server.url:
                return {
                    "ok": False,
                    "toolCount": 0,
                    "message": "stdio MCP probe not supported in doctor yet",
                    "tools": [],
                    "toolDetails": [],
                }
            result = _mcp_service.probe_mcp_server(url=server.url, headers=headers)
            if not getattr(server, "catalog_id", None):
                count_id = custom_tool_count_id(server_id)
                if result.get("ok"):
                    save_tool_count(count_id, int(result.get("toolCount") or 0))
                else:
                    clear_tool_count(count_id)
            return result

        raise ValueError("catalog_id or server_id required")
