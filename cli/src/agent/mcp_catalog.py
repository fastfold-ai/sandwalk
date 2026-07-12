"""Suggested remote MCP server catalog (defaults off until Connect)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AuthPreference = Literal["oauth", "api_key"]
AuthMode = Literal["oauth", "api_key", "api_key_or_oauth"]


@dataclass(frozen=True)
class McpCatalogEntry:
    id: str
    name: str
    description: str
    url: str
    transport: Literal["streamable_http", "sse"] = "streamable_http"
    auth_mode: AuthMode = "api_key"
    preferred_auth: AuthPreference = "api_key"
    # API key → config.json / Integrations (/keys)
    api_key_config_key: str | None = None
    api_key_env_var: str | None = None
    api_key_header: str | None = None  # e.g. "x-api-key" or "Authorization"
    api_key_header_prefix: str = ""  # e.g. "Bearer " for Authorization
    docs_url: str | None = None
    setup_url: str | None = None
    integration_key: str | None = None  # Integrations provider key


MCP_CATALOG: list[McpCatalogEntry] = [
    McpCatalogEntry(
        id="tamarind",
        name="Tamarind Bio",
        description="Protein design, structure prediction, docking, and molecular dynamics.",
        url="https://mcp.tamarind.bio/mcp",
        auth_mode="api_key",
        preferred_auth="api_key",
        api_key_config_key="mcp.tamarind_api_key",
        api_key_env_var="TAMARIND_API_KEY",
        api_key_header="x-api-key",
        docs_url="https://app.tamarind.bio/api-docs/mcp-server",
        setup_url="https://app.tamarind.bio",
        integration_key="tamarind",
    ),
    McpCatalogEntry(
        id="latch",
        name="Latch Bio",
        description="Bioinformatics workflows, data, and compute on the Latch platform.",
        url="https://mcp.latch.bio/mcp",
        auth_mode="oauth",
        preferred_auth="oauth",
        docs_url="https://wiki.latch.bio/agent/latch-mcp",
        setup_url="https://latch.bio",
        integration_key="latch",
    ),
    McpCatalogEntry(
        id="neurosnap",
        name="Neurosnap",
        description="Protein folding, docking, design, and computational biology jobs.",
        url="https://neurosnap.ai/mcp",
        auth_mode="api_key",
        preferred_auth="api_key",
        api_key_config_key="mcp.neurosnap_api_key",
        api_key_env_var="NEUROSNAP_API_KEY",
        api_key_header="Authorization",
        api_key_header_prefix="Bearer ",
        docs_url="https://neurosnap.ai/overview?view=api",
        setup_url="https://neurosnap.ai",
        integration_key="neurosnap",
    ),
    McpCatalogEntry(
        id="linear",
        name="Linear",
        description="Issues, projects, and comments for product and ops workflows.",
        url="https://mcp.linear.app/mcp",
        auth_mode="api_key_or_oauth",
        preferred_auth="oauth",
        api_key_config_key="mcp.linear_api_key",
        api_key_env_var="LINEAR_API_KEY",
        api_key_header="Authorization",
        api_key_header_prefix="Bearer ",
        docs_url="https://linear.app/docs/mcp",
        setup_url="https://linear.app/settings/account/security",
        integration_key="linear",
    ),
]

_BY_ID = {entry.id: entry for entry in MCP_CATALOG}


def get_catalog_entry(catalog_id: str) -> McpCatalogEntry | None:
    return _BY_ID.get(catalog_id)


def catalog_as_dicts() -> list[dict[str, Any]]:
    return [
        {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "url": e.url,
            "transport": e.transport,
            "authMode": e.auth_mode,
            "preferredAuth": e.preferred_auth,
            "apiKeyEnvVar": e.api_key_env_var,
            "apiKeyHeader": e.api_key_header,
            "docsUrl": e.docs_url,
            "setupUrl": e.setup_url,
            "integrationKey": e.integration_key,
            "defaultEnabled": False,
        }
        for e in MCP_CATALOG
    ]
