"""Catalog MCP credential resolution: API keys and OAuth tokens."""

from __future__ import annotations

import logging
import os
import time

from agent.config import Config
from agent.mcp_catalog import McpCatalogEntry
from agent_server.mcp_service.custom_headers import ensure_mcp_http_headers

logger = logging.getLogger("mcp_service")


def _cfg_secret(config: Config, config_key: str | None, env_var: str | None) -> str | None:
    if env_var:
        env_value = str(os.environ.get(env_var) or "").strip()
        if env_value:
            return env_value
    if config_key:
        value = str(config.get(config_key) or "").strip()
        if value:
            return value
    return None


def mask_secret_preview(value: str | None) -> str | None:
    """Short preview for UI placeholders (same shape as Integrations)."""
    normalized = (value or "").strip()
    if not normalized:
        return None
    if len(normalized) <= 8:
        return "••••••••"
    return f"{normalized[:4]}…{normalized[-4:]}"


def api_key_masked_preview(
    entry: McpCatalogEntry,
    config: Config | None = None,
) -> str | None:
    """Masked API key when one is stored for this catalog entry."""
    if not entry.api_key_config_key:
        return None
    cfg = config or Config.load()
    return mask_secret_preview(
        _cfg_secret(cfg, entry.api_key_config_key, entry.api_key_env_var)
    )


def oauth_access_token_expired(
    entry: McpCatalogEntry,
    config: Config | None = None,
    *,
    skew_seconds: int = 60,
) -> bool:
    """Return True when a stored OAuth access token is past ``token_expires_at``."""
    cfg = config or Config.load()
    raw = cfg.get(f"mcp.{entry.id}_token_expires_at")
    if raw is None or str(raw).strip() == "":
        return False
    try:
        expires_at = float(raw)
    except (TypeError, ValueError):
        return False
    return time.time() >= (expires_at - max(0, skew_seconds))


def _store_oauth_token_response(
    cfg: Config,
    *,
    prefix: str,
    data: dict,
    token_endpoint: str | None = None,
    resource: str | None = None,
) -> str:
    """Persist access/refresh/expiry from a token endpoint JSON body."""
    access_token = str(data["access_token"])
    cfg.set(f"{prefix}_access_token", access_token)
    if data.get("refresh_token"):
        cfg.set(f"{prefix}_refresh_token", str(data["refresh_token"]))
    expires_in = data.get("expires_in")
    if expires_in:
        cfg.set(
            f"{prefix}_token_expires_at",
            str(int(time.time()) + int(expires_in)),
        )
    if token_endpoint:
        cfg.set(f"{prefix}_token_endpoint", str(token_endpoint))
    if resource:
        cfg.set(f"{prefix}_oauth_resource", str(resource))
    cfg.save()
    # A fresh token (refresh or reconnect) ends any refresh backoff.
    _REFRESH_BACKOFF_UNTIL.pop(prefix.removeprefix("mcp."), None)
    return access_token


def _refresh_oauth_access_token(
    *,
    prefix: str,
    refresh_token: str,
    client_id: str,
    client_secret: str | None,
    token_endpoint: str,
    resource: str,
    cfg: Config,
) -> str | None:
    """Exchange ``refresh_token`` at ``token_endpoint``. Returns new access or None."""
    from agent_server import mcp_service as _mcp_service

    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "resource": resource,
    }
    headers: dict[str, str] = {}
    if client_secret:
        import base64

        basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        headers["Authorization"] = f"Basic {basic}"
        form["client_secret"] = client_secret

    status, data = _mcp_service._http_json(
        token_endpoint,
        method="POST",
        form=form,
        headers=headers,
    )
    if status >= 400 or not isinstance(data, dict) or not data.get("access_token"):
        logger.warning(
            "OAuth refresh failed for %s: status=%s data=%s",
            prefix,
            status,
            data,
        )
        return None
    return _store_oauth_token_response(
        cfg,
        prefix=prefix,
        data=data,
        token_endpoint=token_endpoint,
        resource=resource,
    )


# Servers whose refresh just failed, with the time to try again. A dead grant
# (``invalid_grant``) stays dead until the user reconnects; without this every
# agent turn paid a ~0.5s blocking HTTPS round-trip for nothing.
_REFRESH_BACKOFF_UNTIL: dict[str, float] = {}
REFRESH_BACKOFF_SEC = 600.0


def clear_oauth_refresh_backoff(entry_id: str | None = None) -> None:
    """Forget refresh backoff (after a reconnect, or all when ``entry_id`` is None)."""
    if entry_id is None:
        _REFRESH_BACKOFF_UNTIL.clear()
    else:
        _REFRESH_BACKOFF_UNTIL.pop(entry_id, None)


def _refresh_backed_off(entry_id: str) -> bool:
    until = _REFRESH_BACKOFF_UNTIL.get(entry_id)
    if until is None:
        return False
    if time.monotonic() >= until:
        _REFRESH_BACKOFF_UNTIL.pop(entry_id, None)
        return False
    return True


def ensure_fresh_catalog_oauth_token(
    entry: McpCatalogEntry,
    config: Config | None = None,
) -> str | None:
    """Return a usable access token, refreshing when past ``token_expires_at``."""
    cfg = config or Config.load()
    prefix = f"mcp.{entry.id}"
    access = _cfg_secret(cfg, f"{prefix}_access_token", None)
    if not access:
        return None
    if not oauth_access_token_expired(entry, cfg):
        return access

    refresh = _cfg_secret(cfg, f"{prefix}_refresh_token", None)
    if not refresh:
        # Expired with no refresh — force reconnect rather than 401 loops.
        return None
    if _refresh_backed_off(entry.id):
        return None

    client_id = str(cfg.get(f"{prefix}_client_id") or "").strip()
    client_secret = str(cfg.get(f"{prefix}_client_secret") or "").strip() or None
    token_endpoint = str(cfg.get(f"{prefix}_token_endpoint") or "").strip()
    resource = str(cfg.get(f"{prefix}_oauth_resource") or entry.url or "").strip()

    if not token_endpoint or not client_id:
        try:
            from agent_server.mcp_service.oauth_discovery import discover_oauth

            meta = discover_oauth(entry)
            token_endpoint = str(meta["token_endpoint"])
            resource = str(meta.get("resource") or resource)
            if not client_id:
                # Cannot refresh without the registered client id from Connect.
                return None
            cfg.set(f"{prefix}_token_endpoint", token_endpoint)
            cfg.set(f"{prefix}_oauth_resource", resource)
            cfg.save()
        except Exception as exc:  # noqa: BLE001
            logger.warning("OAuth discovery for refresh failed (%s): %s", entry.id, exc)
            return None

    refreshed = _refresh_oauth_access_token(
        prefix=prefix,
        refresh_token=refresh,
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint=token_endpoint,
        resource=resource,
        cfg=cfg,
    )
    if refreshed:
        _REFRESH_BACKOFF_UNTIL.pop(entry.id, None)
        try:
            from agent_server.mcp_service.health_cache import save_status_message

            save_status_message(entry.id, None)
        except Exception:  # noqa: BLE001
            pass
        return refreshed

    _REFRESH_BACKOFF_UNTIL[entry.id] = time.monotonic() + REFRESH_BACKOFF_SEC
    # Do not keep presenting a known-expired access token as usable.
    try:
        from agent_server.mcp_service.health_cache import save_status_message

        save_status_message(
            entry.id,
            "OAuth access token expired and refresh failed. "
            "Click Reconnect to sign in again.",
        )
    except Exception:  # noqa: BLE001
        pass
    return None


def resolve_auth_headers(
    entry: McpCatalogEntry,
    config: Config | None = None,
) -> dict[str, str] | None:
    """Build HTTP headers for a catalog MCP from keys (/keys) or OAuth tokens."""
    cfg = config or Config.load()

    # API-key-only entries should never prefer a stale OAuth token.
    if entry.auth_mode != "api_key":
        access = ensure_fresh_catalog_oauth_token(entry, cfg)
        if access:
            return ensure_mcp_http_headers({"Authorization": f"Bearer {access}"})

    if entry.api_key_config_key and entry.api_key_header:
        api_key = _cfg_secret(cfg, entry.api_key_config_key, entry.api_key_env_var)
        if api_key:
            prefix = entry.api_key_header_prefix or ""
            return ensure_mcp_http_headers(
                {entry.api_key_header: f"{prefix}{api_key}"}
            )
    return None


def oauth_reconnect_required(
    entry: McpCatalogEntry,
    config: Config | None = None,
) -> str | None:
    """Human message when OAuth must be reconnected, else None."""
    cfg = config or Config.load()
    access = _cfg_secret(cfg, f"mcp.{entry.id}_access_token", None)
    if not access:
        return None
    refresh = _cfg_secret(cfg, f"mcp.{entry.id}_refresh_token", None)
    if oauth_access_token_expired(entry, cfg) and not refresh:
        return (
            "OAuth access token expired and no refresh token is stored. "
            "Disconnect and Connect again to re-authorize."
        )
    return None


def credentials_configured(entry: McpCatalogEntry, config: Config | None = None) -> bool:
    if entry.transport == "stdio" or entry.auth_mode == "none":
        if entry.id == "pymol":
            from agent.mcps.pymol_mcp import launcher_ready

            return launcher_ready()
        if entry.id == "raymol":
            from agent.mcps.raymol_mcp import launcher_ready

            return launcher_ready()
        return bool(entry.command or entry.id)
    return resolve_auth_headers(entry, config) is not None


def auth_method_in_use(entry: McpCatalogEntry, config: Config | None = None) -> str | None:
    if entry.transport == "stdio" or entry.auth_mode == "none":
        return "local" if credentials_configured(entry, config) else None
    cfg = config or Config.load()
    if _cfg_secret(cfg, f"mcp.{entry.id}_access_token", None):
        return "oauth"
    if entry.api_key_config_key and _cfg_secret(
        cfg, entry.api_key_config_key, entry.api_key_env_var
    ):
        return "api_key"
    return None
