"""Catalog MCP credential resolution: API keys and OAuth tokens."""

from __future__ import annotations

import os
import time

from agent.config import Config
from agent.mcp_catalog import McpCatalogEntry
from agent_server.mcp_service.custom_headers import ensure_mcp_http_headers


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


def resolve_auth_headers(
    entry: McpCatalogEntry,
    config: Config | None = None,
) -> dict[str, str] | None:
    """Build HTTP headers for a catalog MCP from keys (/keys) or OAuth tokens."""
    cfg = config or Config.load()

    # API-key-only entries should never prefer a stale OAuth token.
    if entry.auth_mode != "api_key":
        access = _cfg_secret(cfg, f"mcp.{entry.id}_access_token", None)
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
