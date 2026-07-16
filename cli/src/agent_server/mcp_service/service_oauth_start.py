"""``McpService`` OAuth authorization-URL construction (catalog + custom remotes)."""

from __future__ import annotations

import secrets
import time
import urllib.parse
from typing import Any

from agent.config import Config
from agent.mcp_catalog import get_catalog_entry
from agent_server.mcp_service.custom_server import custom_oauth_token_key
from agent_server.mcp_service.oauth_discovery import discover_oauth, discover_oauth_for_url
from agent_server.mcp_service.oauth_http import _pkce_pair
from agent_server.mcp_service.oauth_state import _oauth_lock, _oauth_states


class OAuthStartMixin:
    def _begin_oauth_flow(
        self,
        *,
        meta: dict[str, Any],
        resource_url: str,
        label: str,
        client_id_key: str,
        client_secret_key: str,
        state_extra: dict[str, Any],
    ) -> dict[str, Any]:
        from agent_server import mcp_service as _mcp_service

        redirect_uri = f"{self.public_base_url.rstrip('/')}/v1/mcp-servers/oauth/callback"
        verifier, challenge = _pkce_pair()
        state = secrets.token_urlsafe(24)

        client_id: str | None = None
        client_secret: str | None = None
        cfg = Config.load()
        stored_client = str(cfg.get(client_id_key) or "").strip()
        stored_secret = str(cfg.get(client_secret_key) or "").strip() or None

        if stored_client:
            client_id = stored_client
            client_secret = stored_secret
        elif meta.get("registration_endpoint"):
            reg_body = {
                "client_name": "Sandwalk",
                "redirect_uris": [redirect_uri],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            }
            status, data = _mcp_service._http_json(
                str(meta["registration_endpoint"]),
                method="POST",
                body=reg_body,
            )
            if status >= 400 or not isinstance(data, dict) or not data.get("client_id"):
                raise ValueError(f"OAuth client registration failed: {data}")
            client_id = str(data["client_id"])
            client_secret = str(data["client_secret"]) if data.get("client_secret") else None
            cfg.set(client_id_key, client_id)
            if client_secret:
                cfg.set(client_secret_key, client_secret)
            cfg.save()
        else:
            raise ValueError(
                f"No OAuth registration endpoint for {label}. "
                "Use API key Connect if available."
            )

        scope = " ".join(str(s) for s in (meta.get("scopes") or [])[:6])
        resource = meta.get("resource") or resource_url
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": scope,
            "resource": resource,
        }
        authorize_url = (
            str(meta["authorization_endpoint"])
            + "?"
            + urllib.parse.urlencode(params)
        )
        with _oauth_lock:
            _oauth_states[state] = {
                **state_extra,
                "verifier": verifier,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
                "token_endpoint": meta["token_endpoint"],
                "resource": resource,
                "created_at": time.time(),
            }
        return {
            "authorizeUrl": authorize_url,
            "state": state,
            "redirectUri": redirect_uri,
            **{k: v for k, v in state_extra.items() if k in ("catalog_id", "server_id")},
        }

    def start_oauth(self, catalog_id: str) -> dict[str, Any]:
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)
        if entry.auth_mode == "api_key":
            raise ValueError(f"{entry.name} uses API key auth, not OAuth")

        meta = discover_oauth(entry)
        result = self._begin_oauth_flow(
            meta=meta,
            resource_url=entry.url,
            label=entry.name,
            client_id_key=f"mcp.{catalog_id}_client_id",
            client_secret_key=f"mcp.{catalog_id}_client_secret",
            state_extra={"catalog_id": catalog_id},
        )
        return {
            "authorizeUrl": result["authorizeUrl"],
            "state": result["state"],
            "redirectUri": result["redirectUri"],
            "catalogId": catalog_id,
        }

    def start_oauth_custom(self, server_id: str) -> dict[str, Any]:
        """Start URL-based OAuth for a custom (non-catalog) remote MCP server."""
        server = next(
            (s for s in self.store.list_mcp_servers() if s.id == server_id),
            None,
        )
        if server is None:
            raise KeyError(server_id)
        if getattr(server, "catalog_id", None):
            raise ValueError("Use catalog connect for featured MCP servers")
        if server.transport == "stdio" or not server.url:
            raise ValueError("OAuth is only available for remote MCP servers")

        meta = discover_oauth_for_url(server.url, label=server.name)
        result = self._begin_oauth_flow(
            meta=meta,
            resource_url=server.url,
            label=server.name,
            client_id_key=custom_oauth_token_key(server_id, "client_id"),
            client_secret_key=custom_oauth_token_key(server_id, "client_secret"),
            state_extra={"server_id": server_id, "mcp_url": server.url},
        )
        return {
            "authorizeUrl": result["authorizeUrl"],
            "state": result["state"],
            "redirectUri": result["redirectUri"],
            "serverId": server_id,
        }
