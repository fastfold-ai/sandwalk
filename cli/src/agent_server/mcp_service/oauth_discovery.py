"""OAuth protected-resource + authorization-server discovery (RFC 9728 / 8414).

``_http_json``/``_probe_resource_metadata_url`` are looked up on the
``agent_server.mcp_service`` package (rather than imported by name) so tests —
and callers — can monkeypatch them at the package level and have this module
observe the replacement, matching the module's pre-split behavior.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from agent.mcp_catalog import McpCatalogEntry


def discover_oauth_for_url(
    url: str,
    *,
    label: str = "mcp",
    catalog_id: str | None = None,
) -> dict[str, Any]:
    """Fetch OAuth protected-resource + authorization-server metadata for a URL."""
    from agent_server import mcp_service as _mcp_service

    parsed = urllib.parse.urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [
        f"{origin}/.well-known/oauth-protected-resource",
        f"{origin}/.well-known/oauth-protected-resource/mcp",
        url.rstrip("/") + "/.well-known/oauth-protected-resource",
    ]
    # Known overrides from smoke tests / catalog quirks
    if catalog_id == "latch":
        candidates.insert(0, "https://mcp.latch.bio/.well-known/oauth-protected-resource/mcp")
    if catalog_id == "linear":
        candidates.insert(0, "https://mcp.linear.app/.well-known/oauth-protected-resource/mcp")
    if catalog_id == "paperclip":
        candidates.insert(0, "https://paperclip.gxl.ai/.well-known/oauth-protected-resource")

    # MCP clients MUST prefer WWW-Authenticate resource_metadata when present.
    challenged = _mcp_service._probe_resource_metadata_url(url)
    if challenged:
        candidates.insert(0, challenged)

    resource_meta: dict[str, Any] | None = None
    for candidate in candidates:
        status, data = _mcp_service._http_json(candidate)
        if status == 200 and isinstance(data, dict) and data.get("authorization_servers"):
            resource_meta = data
            break
    if not resource_meta:
        raise ValueError(f"Could not discover OAuth resource metadata for {label}")

    as_list = [str(item).rstrip("/") for item in (resource_meta.get("authorization_servers") or [])]
    if not as_list:
        raise ValueError(f"No authorization servers listed for {label}")

    # Prefer an AS that advertises dynamic client registration when available.
    discovered: list[dict[str, Any]] = []
    for issuer in as_list:
        as_meta_urls = [
            f"{issuer}/.well-known/oauth-authorization-server",
            f"{issuer}/.well-known/openid-configuration",
        ]
        # RFC 8414 path insertion when issuer has a path component.
        issuer_parsed = urllib.parse.urlparse(issuer)
        if issuer_parsed.path and issuer_parsed.path != "/":
            path = issuer_parsed.path.rstrip("/")
            as_meta_urls.insert(
                0,
                f"{issuer_parsed.scheme}://{issuer_parsed.netloc}"
                f"/.well-known/oauth-authorization-server{path}",
            )
            as_meta_urls.insert(
                1,
                f"{issuer_parsed.scheme}://{issuer_parsed.netloc}"
                f"/.well-known/openid-configuration{path}",
            )
        if catalog_id == "linear":
            as_meta_urls.insert(
                0, "https://mcp.linear.app/.well-known/oauth-authorization-server"
            )
        if catalog_id == "paperclip":
            as_meta_urls.insert(
                0, "https://paperclip.gxl.ai/.well-known/oauth-authorization-server"
            )
        for meta_url in as_meta_urls:
            status, data = _mcp_service._http_json(meta_url)
            if status == 200 and isinstance(data, dict) and data.get("authorization_endpoint"):
                discovered.append(
                    {
                        "issuer": data.get("issuer") or issuer,
                        "authorization_endpoint": data["authorization_endpoint"],
                        "token_endpoint": data["token_endpoint"],
                        "registration_endpoint": data.get("registration_endpoint"),
                    }
                )
                break

    if not discovered:
        raise ValueError(f"Could not discover OAuth authorization server for {label}")

    as_meta = next((row for row in discovered if row.get("registration_endpoint")), discovered[0])

    return {
        "resource": resource_meta.get("resource") or url,
        "scopes": resource_meta.get("scopes_supported") or ["openid", "offline_access"],
        "authorization_endpoint": as_meta["authorization_endpoint"],
        "token_endpoint": as_meta["token_endpoint"],
        "registration_endpoint": as_meta.get("registration_endpoint"),
        "issuer": as_meta.get("issuer"),
    }


def discover_oauth(entry: McpCatalogEntry) -> dict[str, Any]:
    """Fetch OAuth protected-resource + authorization-server metadata."""
    return discover_oauth_for_url(entry.url, label=entry.id, catalog_id=entry.id)
