"""Suggested MCP server catalog (defaults off until Connect / Enable)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AuthPreference = Literal["oauth", "api_key"]
AuthMode = Literal["oauth", "api_key", "api_key_or_oauth", "none"]
Transport = Literal["streamable_http", "sse", "stdio"]


@dataclass(frozen=True)
class McpCatalogEntry:
    id: str
    name: str
    description: str
    url: str | None = None
    transport: Transport = "streamable_http"
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
    # Shown in Featured / onboarding MCP grids. Non-featured stay in the full list.
    featured: bool = True
    # Local stdio catalog entries (e.g. PyMOL). Resolved at seed/install time.
    command: str | None = None
    args: list[str] = field(default_factory=list)


def _pymol_command() -> str:
    from agent.mcps.pymol_mcp import launcher_path

    return str(launcher_path())


def _raymol_command() -> str:
    from agent.mcps.raymol_mcp import launcher_path

    return str(launcher_path())


MCP_CATALOG: list[McpCatalogEntry] = [
    McpCatalogEntry(
        id="pymol",
        name="PyMOL",
        description=(
            "Control a live commercial or open-source PyMOL session — "
            "structures, selections, alignments, and renders via agentic-pymol."
        ),
        url=None,
        transport="stdio",
        auth_mode="none",
        preferred_auth="api_key",
        docs_url=None,
        setup_url="https://sandwalk.sh/pymol/plugin.zip",
        featured=True,
        # command resolved dynamically in catalog_create_kwargs / catalog_as_dicts
        command=None,
        args=[],
    ),
    McpCatalogEntry(
        id="raymol",
        name="RayMol",
        description=(
            "Drive RayMol (Metal PyMOL for Apple Silicon) — fetch structures, "
            "run commands, change representations, and capture the viewport."
        ),
        url=None,
        transport="stdio",
        auth_mode="none",
        preferred_auth="api_key",
        docs_url="https://raymol.io/",
        setup_url="https://raymol.io/",
        featured=True,
        command=None,
        args=["--mcp-bridge"],
    ),
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
        featured=True,
    ),
    McpCatalogEntry(
        id="paperclip",
        name="Paperclip",
        description=(
            "Search and synthesize 11M+ biomedical papers, regulatory docs, "
            "clinical trials, and biology databases (UniProt, PDB, ChEMBL)."
        ),
        url="https://paperclip.gxl.ai/mcp",
        auth_mode="api_key_or_oauth",
        preferred_auth="oauth",
        api_key_config_key="mcp.paperclip_api_key",
        api_key_env_var="PAPERCLIP_API_KEY",
        api_key_header="X-API-Key",
        docs_url="https://paperclip.gxl.ai/install",
        setup_url="https://paperclip.gxl.ai/keys",
        integration_key="paperclip",
        featured=True,
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
        featured=True,
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
        featured=True,
    ),
    McpCatalogEntry(
        id="huggingface",
        name="Hugging Face",
        description=(
            "Search Hub models, datasets, Spaces, papers, and docs; "
            "run enabled community Gradio tools."
        ),
        url="https://huggingface.co/mcp",
        auth_mode="api_key",
        preferred_auth="api_key",
        api_key_config_key="mcp.huggingface_api_key",
        api_key_env_var="HF_TOKEN",
        api_key_header="Authorization",
        api_key_header_prefix="Bearer ",
        docs_url="https://huggingface.co/docs/hub/en/agents-mcp",
        setup_url="https://huggingface.co/settings/tokens",
        integration_key="huggingface",
        featured=True,
    ),
    McpCatalogEntry(
        id="tavily",
        name="Tavily",
        description="Real-time web search and intelligent content extraction.",
        url="https://mcp.tavily.com/mcp/",
        auth_mode="api_key_or_oauth",
        preferred_auth="oauth",
        api_key_config_key="api.tavily_api_key",
        api_key_env_var="TAVILY_API_KEY",
        api_key_header="Authorization",
        api_key_header_prefix="Bearer ",
        docs_url="https://docs.tavily.com/documentation/mcp",
        setup_url="https://app.tavily.com/home",
        integration_key="tavily",
        featured=True,
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
        featured=False,
    ),
]

_BY_ID = {entry.id: entry for entry in MCP_CATALOG}


def get_catalog_entry(catalog_id: str) -> McpCatalogEntry | None:
    return _BY_ID.get(catalog_id)


def resolve_catalog_command(entry: McpCatalogEntry) -> str | None:
    """Resolve stdio command for a catalog entry (may be dynamic)."""
    if entry.transport != "stdio":
        return entry.command
    if entry.id == "pymol":
        return _pymol_command()
    if entry.id == "raymol":
        return _raymol_command()
    return entry.command


def catalog_create_kwargs(entry: McpCatalogEntry, *, enabled: bool = False) -> dict[str, Any]:
    """kwargs for store.create_mcp_server from a catalog entry."""
    if entry.transport == "stdio":
        return {
            "name": entry.name,
            "transport": "stdio",
            "command": resolve_catalog_command(entry),
            "args": list(entry.args or []),
            "url": None,
            "enabled": enabled,
            "catalog_id": entry.id,
            "description": entry.description,
        }
    return {
        "name": entry.name,
        "transport": entry.transport,
        "command": None,
        "args": [],
        "url": entry.url,
        "enabled": enabled,
        "catalog_id": entry.id,
        "description": entry.description,
    }


def catalog_as_dicts() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in MCP_CATALOG:
        command = resolve_catalog_command(e) if e.transport == "stdio" else e.command
        out.append(
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
                "featured": e.featured,
                "defaultEnabled": False,
                "command": command,
                "args": list(e.args or []),
            }
        )
    return out
