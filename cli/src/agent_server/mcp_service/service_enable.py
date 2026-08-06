"""``McpService`` disconnect and enable/disable toggling for catalog entries."""

from __future__ import annotations

from typing import Any

from agent.mcp_catalog import get_catalog_entry
from agent_server.mcp_service.auth import credentials_configured
from agent_server.mcp_service.health_cache import (
    clear_tool_count,
    save_status_message,
    save_tool_count,
)


class EnableMixin:
    def disconnect(self, catalog_id: str) -> dict[str, Any]:
        self.clear_credentials(catalog_id)
        server = next(
            (
                s
                for s in self.store.list_mcp_servers()
                if getattr(s, "catalog_id", None) == catalog_id
            ),
            None,
        )
        if server and server.enabled:
            self.store.update_mcp_server(server.id, enabled=False)
        return {"ok": True, "enabled": False, "configured": False}

    def set_enabled(self, catalog_id: str, enabled: bool) -> dict[str, Any]:
        """Enable/disable a catalog MCP. Enable requires credentials already saved."""
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)
        if enabled:
            if not credentials_configured(entry):
                if entry.transport == "stdio" or entry.auth_mode == "none":
                    raise ValueError(
                        f"{entry.name} launcher is not installed — "
                        "run: sandwalk mcp install pymol"
                        if entry.id == "pymol"
                        else f"{entry.name} is not ready — install the local MCP command first"
                    )
                raise ValueError(
                    f"{entry.name} is not configured — Connect with OAuth or API key first"
                )
            server = self.ensure_catalog_server(catalog_id, enabled=True)
            if not server.enabled:
                server = self.store.update_mcp_server(server.id, enabled=True) or server
            probe = self.validate(catalog_id=catalog_id)
            if probe.get("ok"):
                tool_count = int(probe.get("toolCount") or 0)
                save_tool_count(catalog_id, tool_count)
                return {
                    "ok": True,
                    "enabled": True,
                    "configured": True,
                    "serverId": server.id,
                    "catalogId": catalog_id,
                    "toolCount": tool_count,
                }
            clear_tool_count(catalog_id)
            save_status_message(
                catalog_id, str(probe.get("message") or "Connection failed")
            )
            return {
                "ok": False,
                "enabled": True,
                "configured": True,
                "serverId": server.id,
                "catalogId": catalog_id,
                "toolCount": None,
                "message": probe.get("message"),
            }
        server = next(
            (
                s
                for s in self.store.list_mcp_servers()
                if getattr(s, "catalog_id", None) == catalog_id
            ),
            None,
        )
        if server and server.enabled:
            server = self.store.update_mcp_server(server.id, enabled=False) or server
        return {
            "ok": True,
            "enabled": False,
            "configured": credentials_configured(entry),
            "serverId": server.id if server else None,
            "catalogId": catalog_id,
        }
