"""``McpService.connect_custom_api_key`` — Bearer auth for custom remote MCPs."""

from __future__ import annotations

from typing import Any

from agent.config import Config
from agent_server.mcp_service.custom_headers import ensure_mcp_http_headers, set_custom_headers
from agent_server.mcp_service.custom_server import custom_oauth_token_key, custom_tool_count_id
from agent_server.mcp_service.health_cache import clear_tool_count, save_tool_count


class CustomAuthMixin:
    def connect_custom_api_key(self, server_id: str, api_key: str) -> dict[str, Any]:
        """Store Bearer auth for a custom remote MCP — does not enable the toggle."""
        from agent_server import mcp_service as _mcp_service

        server = next(
            (s for s in self.store.list_mcp_servers() if s.id == server_id),
            None,
        )
        if server is None:
            raise KeyError(server_id)
        if getattr(server, "catalog_id", None):
            raise ValueError("Use catalog connect for featured MCP servers")
        if server.transport == "stdio" or not server.url:
            raise ValueError("API key connect is only for remote MCP servers")
        key = api_key.strip()
        if not key:
            raise ValueError("API key is required")
        value = key if key.lower().startswith("bearer ") else f"Bearer {key}"
        # Drop stale OAuth so the new key wins at runtime.
        cfg = Config.load()
        for kind in ("access_token", "refresh_token", "token_expires_at"):
            oauth_key = custom_oauth_token_key(server_id, kind)
            if cfg.get(oauth_key) is not None:
                cfg.unset(oauth_key)
        cfg.save()
        set_custom_headers(server_id, {"Authorization": value}, config=cfg)
        # Authenticate only — leave enabled off (Cursor-style for API key).
        if server.enabled:
            server = self.store.update_mcp_server(server_id, enabled=False) or server
        result = _mcp_service.probe_mcp_server(
            url=server.url,
            headers=ensure_mcp_http_headers({"Authorization": value}),
        )
        count_id = custom_tool_count_id(server_id)
        if result.get("ok"):
            save_tool_count(count_id, int(result.get("toolCount") or 0))
        else:
            clear_tool_count(count_id)
        return {
            "ok": bool(result.get("ok")),
            "serverId": server_id,
            "enabled": False,
            "toolCount": result.get("toolCount"),
            "message": result.get("message") or (
                f"Connected · {result.get('toolCount') or 0} tools"
                if result.get("ok")
                else "Connection failed"
            ),
            "tools": list(result.get("tools") or []),
        }
