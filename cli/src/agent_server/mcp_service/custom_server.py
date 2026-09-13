"""Credential/header resolution for custom (non-catalog) remote MCP servers."""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from agent.config import Config
from agent_server.mcp_service.custom_headers import (
    ensure_mcp_http_headers,
    get_custom_headers,
)
from agent_server.mcp_service.health_cache import read_tool_count

logger = logging.getLogger("mcp_service")

_HEADERS_HELPER_TIMEOUT_S = 10


def custom_oauth_token_key(server_id: str, kind: str) -> str:
    """Config key for custom-server OAuth tokens (access / refresh / expires / client)."""
    return f"mcp.custom_{server_id}_{kind}"


def custom_server_credentials_configured(
    server: Any,
    *,
    config: Config | None = None,
) -> bool:
    """True when a custom remote MCP has headers, helper, or OAuth token."""
    helper = getattr(server, "headers_helper_command", None)
    if helper and str(helper).strip():
        return True
    cfg = config or Config.load()
    if get_custom_headers(cfg, server.id):
        return True
    access = str(cfg.get(custom_oauth_token_key(server.id, "access_token")) or "").strip()
    return bool(access)


def custom_tool_count_id(server_id: str) -> str:
    """Config namespace for custom (non-catalog) MCP tool-count cache."""
    return f"custom_{server_id}"


def enrich_mcp_server(server: Any, *, config: Config | None = None) -> Any:
    """Attach non-secret header metadata; force unauthenticated remotes off in the payload."""
    cfg = config or Config.load()
    headers = get_custom_headers(cfg, server.id)
    names = sorted(headers.keys())
    has_oauth = bool(
        str(cfg.get(custom_oauth_token_key(server.id, "access_token")) or "").strip()
    )
    if has_oauth and "Authorization" not in names:
        names = sorted([*names, "Authorization"])
    helper = getattr(server, "headers_helper_command", None)
    configured = bool(names) or bool(helper and str(helper).strip())
    tool_count: int | None = None
    if bool(getattr(server, "enabled", False)):
        catalog_id = getattr(server, "catalog_id", None)
        if catalog_id:
            tool_count = read_tool_count(str(catalog_id), cfg)
        else:
            tool_count = read_tool_count(custom_tool_count_id(server.id), cfg)
    updates: dict[str, Any] = {
        "header_names": names,
        "headers_configured": configured,
        "tool_count": tool_count,
    }
    # Catalog servers manage enable via catalog APIs; custom remotes stay off
    # until Connect / headers are present (even if the DB still says enabled).
    if (
        not getattr(server, "catalog_id", None)
        and getattr(server, "transport", None) != "stdio"
        and not configured
        and bool(getattr(server, "enabled", False))
    ):
        updates["enabled"] = False
        updates["tool_count"] = None
    return server.model_copy(update=updates)


def run_headers_helper_command(command: str) -> dict[str, str] | None:
    """Run a shell command that prints a JSON object of HTTP headers on stdout."""
    try:
        completed = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=_HEADERS_HELPER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        logger.warning("MCP headers helper timed out after %ss", _HEADERS_HELPER_TIMEOUT_S)
        return None
    except OSError as exc:
        logger.warning("MCP headers helper failed to start: %s", exc)
        return None

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        logger.warning(
            "MCP headers helper exited %s: %s",
            completed.returncode,
            stderr[:300] or "(no stderr)",
        )
        return None

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return None
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        logger.warning("MCP headers helper stdout was not valid JSON")
        return None
    if not isinstance(parsed, dict):
        logger.warning("MCP headers helper JSON must be an object")
        return None
    return {
        str(key).strip(): str(value)
        for key, value in parsed.items()
        if str(key).strip() and value is not None and str(value)
    }


def resolve_custom_server_headers(server: Any, *, config: Config | None = None) -> dict[str, str] | None:
    """Resolve auth headers for a custom (non-catalog) remote MCP server.

    Precedence: headers helper → OAuth access token → static custom headers.
    Always includes a Cloudflare-safe User-Agent when any auth header is present.
    """
    cfg = config or Config.load()
    helper = getattr(server, "headers_helper_command", None)
    if helper and str(helper).strip():
        dynamic = run_headers_helper_command(str(helper).strip())
        if dynamic:
            return ensure_mcp_http_headers(dynamic)
    access = _ensure_fresh_custom_oauth_token(server, cfg)
    if access:
        return ensure_mcp_http_headers({"Authorization": f"Bearer {access}"})
    static = get_custom_headers(cfg, server.id)
    return ensure_mcp_http_headers(static) if static else None


def _custom_oauth_expired(cfg: Config, server_id: str, *, skew_seconds: int = 60) -> bool:
    raw = cfg.get(custom_oauth_token_key(server_id, "token_expires_at"))
    if raw is None or str(raw).strip() == "":
        return False
    try:
        expires_at = float(raw)
    except (TypeError, ValueError):
        return False
    import time

    return time.time() >= (expires_at - max(0, skew_seconds))


def _ensure_fresh_custom_oauth_token(server: Any, cfg: Config) -> str | None:
    """Refresh custom-server OAuth access token when expired.

    Offline mode: skip the refresh (return existing access token if available).
    The token may be expired but we avoid spamming error logs.
    """
    from agent_server.mcp_service.auth import _refresh_oauth_access_token
    from agent_server.offline_mode import should_skip_mcp_oauth_refresh

    server_id = str(server.id)
    prefix = f"mcp.custom_{server_id}"
    access = str(cfg.get(custom_oauth_token_key(server_id, "access_token")) or "").strip()
    # Skip refresh when offline — return whatever we have (may be expired).
    if should_skip_mcp_oauth_refresh():
        return access or None
    if not access:
        return None
    if not _custom_oauth_expired(cfg, server_id):
        return access
    refresh = str(cfg.get(custom_oauth_token_key(server_id, "refresh_token")) or "").strip()
    if not refresh:
        return access
    client_id = str(cfg.get(custom_oauth_token_key(server_id, "client_id")) or "").strip()
    client_secret = (
        str(cfg.get(custom_oauth_token_key(server_id, "client_secret")) or "").strip()
        or None
    )
    token_endpoint = str(
        cfg.get(custom_oauth_token_key(server_id, "token_endpoint")) or ""
    ).strip()
    resource = str(
        cfg.get(custom_oauth_token_key(server_id, "oauth_resource"))
        or getattr(server, "url", None)
        or ""
    ).strip()
    if not token_endpoint or not client_id:
        return access
    refreshed = _refresh_oauth_access_token(
        prefix=prefix,
        refresh_token=refresh,
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint=token_endpoint,
        resource=resource,
        cfg=cfg,
    )
    return refreshed or None
