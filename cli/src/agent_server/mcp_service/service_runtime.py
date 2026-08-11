"""``McpService.resolve_runtime_servers`` — enabled MCPs for the agent runtime."""

from __future__ import annotations

from typing import Any

from agent.config import Config
from agent.mcp_catalog import get_catalog_entry
from agent_server.mcp_service.auth import resolve_auth_headers
from agent_server.mcp_service.custom_server import (
    custom_server_credentials_configured,
    resolve_custom_server_headers,
)


class RuntimeMixin:
    def resolve_runtime_servers(self) -> list[dict[str, Any]]:
        """Enabled MCP servers with auth headers injected for the agent runtime."""
        cfg = Config.load()
        out: list[dict[str, Any]] = []
        for server in self.store.list_mcp_servers(enabled_only=True):
            # Skip custom remotes that somehow stayed enabled without credentials.
            if not getattr(server, "catalog_id", None) and server.transport != "stdio":
                if not custom_server_credentials_configured(server, config=cfg):
                    continue
            payload = server.model_dump(mode="json")
            # Never leak header secrets into the agent context dump.
            payload.pop("header_names", None)
            payload.pop("headers_configured", None)
            catalog_id = getattr(server, "catalog_id", None)
            if catalog_id:
                entry = get_catalog_entry(catalog_id)
                if entry:
                    headers = resolve_auth_headers(entry, cfg)
                    if headers:
                        payload["headers"] = headers
            else:
                headers = resolve_custom_server_headers(server, config=cfg)
                if headers:
                    payload["headers"] = headers
            out.append(payload)
        return out
