"""``McpService.complete_oauth`` — OAuth callback token exchange."""

from __future__ import annotations

import time
from typing import Any

from agent.config import Config
from agent.mcp_catalog import get_catalog_entry
from agent_server.mcp_service.custom_headers import ensure_mcp_http_headers
from agent_server.mcp_service.custom_server import custom_oauth_token_key, custom_tool_count_id
from agent_server.mcp_service.health_cache import (
    clear_tool_count,
    save_status_message,
    save_tool_count,
)
from agent_server.mcp_service.oauth_state import _oauth_lock, _oauth_states


class OAuthCompleteMixin:
    def complete_oauth(self, *, code: str, state: str) -> dict[str, Any]:
        from agent_server import mcp_service as _mcp_service

        with _oauth_lock:
            pending = _oauth_states.pop(state, None)
        if not pending:
            raise ValueError("Unknown or expired OAuth state")

        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": pending["redirect_uri"],
            "client_id": pending["client_id"],
            "code_verifier": pending["verifier"],
            "resource": pending["resource"],
        }
        headers: dict[str, str] = {}
        if pending.get("client_secret"):
            import base64

            basic = base64.b64encode(
                f"{pending['client_id']}:{pending['client_secret']}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {basic}"
            form["client_secret"] = pending["client_secret"]

        status, data = _mcp_service._http_json(
            str(pending["token_endpoint"]),
            method="POST",
            form=form,
            headers=headers,
        )
        if status >= 400 or not isinstance(data, dict) or not data.get("access_token"):
            raise ValueError(f"Token exchange failed: {data}")

        cfg = Config.load()
        access_token = str(data["access_token"])
        custom_server_id = pending.get("server_id")
        catalog_id = pending.get("catalog_id")

        if custom_server_id:
            server_id = str(custom_server_id)
            cfg.set(custom_oauth_token_key(server_id, "access_token"), access_token)
            if data.get("refresh_token"):
                cfg.set(
                    custom_oauth_token_key(server_id, "refresh_token"),
                    str(data["refresh_token"]),
                )
            expires_in = data.get("expires_in")
            if expires_in:
                cfg.set(
                    custom_oauth_token_key(server_id, "token_expires_at"),
                    str(int(time.time()) + int(expires_in)),
                )
            if pending.get("token_endpoint"):
                cfg.set(
                    custom_oauth_token_key(server_id, "token_endpoint"),
                    str(pending["token_endpoint"]),
                )
            if pending.get("resource"):
                cfg.set(
                    custom_oauth_token_key(server_id, "oauth_resource"),
                    str(pending["resource"]),
                )
            cfg.save()
            mcp_url = str(pending.get("mcp_url") or "")
            server = next(
                (s for s in self.store.list_mcp_servers() if s.id == server_id),
                None,
            )
            if server is None:
                raise KeyError(server_id)
            if not mcp_url:
                mcp_url = str(server.url or "")
            result = _mcp_service.probe_mcp_server(
                url=mcp_url,
                headers=ensure_mcp_http_headers(
                    {"Authorization": f"Bearer {access_token}"}
                ),
            )
            # Successful OAuth → turn the server on automatically.
            enabled = bool(result.get("ok"))
            self.store.update_mcp_server(server_id, enabled=enabled)
            count_id = custom_tool_count_id(server_id)
            if result.get("ok"):
                save_tool_count(count_id, int(result.get("toolCount") or 0))
            else:
                clear_tool_count(count_id)
            return {
                "ok": result["ok"],
                "serverId": server_id,
                "enabled": enabled,
                **result,
            }

        if not catalog_id:
            raise ValueError("OAuth state missing catalog_id or server_id")
        catalog_id = str(catalog_id)
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)

        cfg.set(f"mcp.{catalog_id}_access_token", access_token)
        if data.get("refresh_token"):
            cfg.set(f"mcp.{catalog_id}_refresh_token", str(data["refresh_token"]))
        expires_in = data.get("expires_in")
        if expires_in:
            cfg.set(
                f"mcp.{catalog_id}_token_expires_at",
                str(int(time.time()) + int(expires_in)),
            )
        # Persist AS endpoints so later refresh can run without rediscovery.
        if pending.get("token_endpoint"):
            cfg.set(f"mcp.{catalog_id}_token_endpoint", str(pending["token_endpoint"]))
        if pending.get("resource"):
            cfg.set(f"mcp.{catalog_id}_oauth_resource", str(pending["resource"]))
        cfg.save()

        result = _mcp_service.probe_mcp_server(
            url=entry.url,
            headers=ensure_mcp_http_headers(
                {"Authorization": f"Bearer {access_token}"}
            ),
        )
        # Successful OAuth → turn the catalog server on automatically.
        enabled = bool(result.get("ok"))
        server = self.ensure_catalog_server(catalog_id, enabled=enabled)
        if bool(server.enabled) != enabled:
            server = self.store.update_mcp_server(server.id, enabled=enabled) or server
        if result["ok"]:
            save_tool_count(catalog_id, int(result.get("toolCount") or 0))
        else:
            clear_tool_count(catalog_id)
            save_status_message(
                catalog_id, str(result.get("message") or "Connection failed")
            )

        return {
            "ok": result["ok"],
            "catalogId": catalog_id,
            "serverId": server.id,
            "enabled": bool(server.enabled),
            **result,
        }
