from __future__ import annotations

from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class McpCatalogEntryStatus(ApiModel):
    id: str
    name: str
    description: str
    url: str
    transport: Literal["stdio", "sse", "streamable_http"]
    auth_mode: str
    preferred_auth: str
    api_key_env_var: str | None = None
    docs_url: str | None = None
    setup_url: str | None = None
    integration_key: str | None = None
    featured: bool = True
    default_enabled: bool = False
    configured: bool = False
    auth_method: str | None = None
    enabled: bool = False
    server_id: str | None = None
    connected: bool = False
    tool_count: int | None = None
    status_message: str | None = None


class McpCatalogList(ApiModel):
    data: list[McpCatalogEntryStatus]


class ConnectMcpCatalogRequest(ApiModel):
    method: Literal["oauth", "api_key"] = "oauth"
    api_key: str | None = None


class UpdateMcpCatalogRequest(ApiModel):
    enabled: bool


class ConnectMcpCatalogResponse(ApiModel):
    ok: bool = True
    authorize_url: str | None = None
    state: str | None = None
    redirect_uri: str | None = None
    catalog_id: str | None = None
    server_id: str | None = None
    enabled: bool | None = None
    tool_count: int | None = None
    message: str | None = None
    tools: list[str] = Field(default_factory=list)
