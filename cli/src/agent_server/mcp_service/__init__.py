"""MCP catalog connect, credential resolution, OAuth, and probe helpers.

This is a package so each concern (custom headers, health cache, probing,
OAuth discovery, and the ``McpService`` orchestration mixins) can live in its
own module. Import from ``agent_server.mcp_service`` as before — this module
re-exports the public API.

A handful of helpers (``probe_mcp_server``, ``_http_json``,
``_probe_resource_metadata_url``) are looked up by other modules in this
package *through this package's namespace* (``from agent_server import
mcp_service`` + attribute access) rather than imported by name, so tests can
``monkeypatch``/``patch`` them here and have every caller observe the
replacement — matching this module's behavior from before the split.
"""

from __future__ import annotations

# Exposed so `agent_server.mcp_service.urllib.request.urlopen` keeps working
# as a monkeypatch/patch target (submodules share the same `urllib` module
# object, so patching it here patches it everywhere).
import urllib.request

from agent_server.mcp_service.auth import (
    _cfg_secret,
    auth_method_in_use,
    credentials_configured,
    oauth_access_token_expired,
    oauth_reconnect_required,
    resolve_auth_headers,
)
from agent_server.mcp_service.core import McpService
from agent_server.mcp_service.custom_headers import (
    MCP_HTTP_USER_AGENT,
    clear_custom_headers,
    custom_headers_config_key,
    ensure_mcp_http_headers,
    get_custom_headers,
    set_custom_headers,
)
from agent_server.mcp_service.custom_server import (
    custom_oauth_token_key,
    custom_server_credentials_configured,
    custom_tool_count_id,
    enrich_mcp_server,
    resolve_custom_server_headers,
    run_headers_helper_command,
)
from agent_server.mcp_service.health_cache import (
    clear_health_cache,
    clear_tool_count,
    read_status_message,
    read_tool_count,
    save_status_message,
    save_tool_count,
)
from agent_server.mcp_service.oauth_discovery import discover_oauth, discover_oauth_for_url
from agent_server.mcp_service.oauth_http import (
    _http_json,
    _pkce_pair,
    _probe_resource_metadata_url,
    _resource_metadata_url_from_www_authenticate,
)
from agent_server.mcp_service.oauth_state import _oauth_lock, _oauth_states
from agent_server.mcp_service.probe import parse_sse_or_json, probe_mcp_server

__all__ = [
    "MCP_HTTP_USER_AGENT",
    "McpService",
    "auth_method_in_use",
    "clear_custom_headers",
    "clear_health_cache",
    "clear_tool_count",
    "credentials_configured",
    "custom_headers_config_key",
    "custom_oauth_token_key",
    "custom_server_credentials_configured",
    "custom_tool_count_id",
    "discover_oauth",
    "discover_oauth_for_url",
    "enrich_mcp_server",
    "ensure_mcp_http_headers",
    "get_custom_headers",
    "oauth_access_token_expired",
    "oauth_reconnect_required",
    "parse_sse_or_json",
    "probe_mcp_server",
    "read_status_message",
    "read_tool_count",
    "resolve_auth_headers",
    "resolve_custom_server_headers",
    "run_headers_helper_command",
    "save_status_message",
    "save_tool_count",
    "set_custom_headers",
]
