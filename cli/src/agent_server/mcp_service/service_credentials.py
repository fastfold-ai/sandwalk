"""``McpService`` API-key credential save/clear/connect for catalog entries."""

from __future__ import annotations

import json
from typing import Any

from agent.config import Config
from agent.mcp_catalog import get_catalog_entry
from agent_server.mcp_service.health_cache import (
    _status_message_key,
    _tool_count_key,
    clear_tool_count,
    save_status_message,
    save_tool_count,
)


class CredentialsMixin:
    def save_api_key(self, catalog_id: str, api_key: str) -> None:
        entry = get_catalog_entry(catalog_id)
        if entry is None or not entry.api_key_config_key:
            raise ValueError(f"{catalog_id} does not support API key auth")
        key = api_key.strip()
        if not key:
            raise ValueError("API key is required")
        cfg = Config.load()
        # Drop stale OAuth tokens so the new API key is what runtime/doctor use.
        for oauth_key in (
            f"mcp.{catalog_id}_access_token",
            f"mcp.{catalog_id}_refresh_token",
            f"mcp.{catalog_id}_token_expires_at",
            f"mcp.{catalog_id}_client_id",
            f"mcp.{catalog_id}_client_secret",
        ):
            if cfg.get(oauth_key) is not None:
                cfg.unset(oauth_key)
        cfg.set(entry.api_key_config_key, key)
        cfg.save()

    def clear_credentials(self, catalog_id: str) -> None:
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)
        cfg = Config.load()
        keys = [
            f"mcp.{catalog_id}_access_token",
            f"mcp.{catalog_id}_refresh_token",
            f"mcp.{catalog_id}_token_expires_at",
            f"mcp.{catalog_id}_client_id",
            f"mcp.{catalog_id}_client_secret",
        ]
        if entry.api_key_config_key:
            keys.append(entry.api_key_config_key)
        keys.append(_tool_count_key(catalog_id))
        keys.append(_status_message_key(catalog_id))
        for key in keys:
            if cfg.get(key) is not None:
                cfg.unset(key)
        cfg.save()

    def connect_with_api_key(self, catalog_id: str, api_key: str) -> dict[str, Any]:
        from agent_server import mcp_service as _mcp_service

        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)
        if entry.auth_mode == "oauth":
            raise ValueError(f"{entry.name} requires OAuth browser connect")
        key = api_key.strip()
        if not key:
            raise ValueError("API key is required")
        if not entry.api_key_header:
            raise ValueError(f"{entry.name} has no API key header configured")

        # Persist the new key first so Reconnect always updates Integrations/keys.
        self.save_api_key(catalog_id, key)

        prefix = entry.api_key_header_prefix or ""
        header_candidates: list[dict[str, str]] = [
            {entry.api_key_header: f"{prefix}{key}"},
        ]
        # Neurosnap accepts Bearer or X-API-KEY; try the alternate if primary fails.
        if entry.id == "neurosnap":
            header_candidates.append({"X-API-KEY": key})
            header_candidates.append({"Authorization": f"Bearer {key}"})
        if entry.id == "paperclip":
            header_candidates.append({"X-API-Key": key})
            header_candidates.append({"x-api-key": key})

        result: dict[str, Any] | None = None
        seen: set[str] = set()
        for headers in header_candidates:
            sig = json.dumps(headers, sort_keys=True)
            if sig in seen:
                continue
            seen.add(sig)
            result = _mcp_service.probe_mcp_server(url=entry.url, headers=headers)
            if result.get("ok"):
                break
        assert result is not None

        # Connect authenticates only — never flip the enable toggle.
        # Users turn MCPs on/off via UI toggle or `mcp enable|disable`.
        server = self.ensure_catalog_server(catalog_id, enabled=False)
        if not result["ok"]:
            clear_tool_count(catalog_id)
            save_status_message(
                catalog_id, str(result.get("message") or "Connection failed")
            )
            return {
                "ok": False,
                "serverId": server.id,
                "enabled": bool(server.enabled),
                **result,
            }

        save_tool_count(catalog_id, int(result.get("toolCount") or 0))
        return {
            "ok": True,
            "serverId": server.id,
            "enabled": bool(server.enabled),
            **result,
        }
