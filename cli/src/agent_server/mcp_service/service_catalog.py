"""``McpService`` catalog listing and provisioning."""

from __future__ import annotations

from typing import Any

from agent.config import Config
from agent.mcp_catalog import MCP_CATALOG, get_catalog_entry
from agent_server.mcp_service.auth import (
    auth_method_in_use,
    credentials_configured,
    oauth_reconnect_required,
)
from agent_server.mcp_service.health_cache import read_status_message, read_tool_count


class CatalogMixin:
    def catalog_statuses(self) -> list[dict[str, Any]]:
        """Fast catalog list — uses cached health from connect/enable/doctor.

        Live probes belong in doctor / connect / enable, not on every dashboard load.
        """
        cfg = Config.load()
        servers = self.store.list_mcp_servers()
        by_catalog = {
            s.catalog_id: s for s in servers if getattr(s, "catalog_id", None)
        }
        out: list[dict[str, Any]] = []
        for entry in MCP_CATALOG:
            server = by_catalog.get(entry.id)
            configured = credentials_configured(entry, cfg)
            enabled = bool(server.enabled) if server else False
            tool_count = read_tool_count(entry.id, cfg)
            status_message = read_status_message(entry.id, cfg)
            connected = False

            if enabled:
                if not configured:
                    if entry.transport == "stdio" or entry.auth_mode == "none":
                        status_message = "Enabled but launcher not installed"
                    else:
                        status_message = "Enabled but not authenticated"
                    tool_count = None
                elif tool_count is not None and not status_message:
                    connected = True
                elif status_message:
                    connected = False
                else:
                    # Enabled + configured, but not probed yet.
                    status_message = None
            else:
                # Disabled cards should not show stale probe errors…
                status_message = None

            # …except expired OAuth that needs reconnect — keep that visible so
            # the list matches the detail-page probe message.
            if configured:
                reconnect = oauth_reconnect_required(entry, cfg)
                if reconnect:
                    status_message = reconnect
                    connected = False

            from agent.mcp_catalog import resolve_catalog_command

            out.append(
                {
                    "id": entry.id,
                    "name": entry.name,
                    "description": entry.description,
                    "url": entry.url,
                    "transport": entry.transport,
                    "auth_mode": entry.auth_mode,
                    "preferred_auth": entry.preferred_auth,
                    "api_key_env_var": entry.api_key_env_var,
                    "docs_url": entry.docs_url,
                    "setup_url": entry.setup_url,
                    "integration_key": entry.integration_key,
                    "featured": entry.featured,
                    "default_enabled": False,
                    "configured": configured,
                    "auth_method": auth_method_in_use(entry, cfg),
                    "enabled": enabled,
                    "server_id": server.id if server else None,
                    "connected": connected,
                    "tool_count": tool_count if enabled else None,
                    "status_message": status_message,
                    "command": resolve_catalog_command(entry)
                    if entry.transport == "stdio"
                    else None,
                    "args": list(entry.args or []) if entry.transport == "stdio" else [],
                }
            )
        return out

    def ensure_catalog_server(self, catalog_id: str, *, enabled: bool = False):
        from agent_server.mcp_json_config import (
            clear_catalog_removed,
            get_or_export_mcp_json,
        )

        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)
        # Connect / enable after delete should re-install the template.
        clear_catalog_removed(catalog_id)
        existing = next(
            (
                s
                for s in self.store.list_mcp_servers()
                if getattr(s, "catalog_id", None) == catalog_id
            ),
            None,
        )
        if existing:
            return existing
        from agent.mcp_catalog import catalog_create_kwargs

        server = self.store.create_mcp_server(
            **catalog_create_kwargs(entry, enabled=enabled)
        )
        get_or_export_mcp_json(self.store)
        return server
