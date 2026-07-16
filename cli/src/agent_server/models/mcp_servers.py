from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class McpServer(ApiModel):
    id: str
    name: str
    transport: Literal["stdio", "sse", "streamable_http"]
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    enabled: bool = True
    catalog_id: str | None = None
    description: str | None = None
    oauth_client_id: str | None = None
    oauth_server_url: str | None = None
    oauth_scopes: str | None = None
    headers_helper_command: str | None = None
    header_names: list[str] = Field(default_factory=list)
    headers_configured: bool = False
    tool_count: int | None = None
    created_at: datetime
    updated_at: datetime


class McpServerList(ApiModel):
    data: list[McpServer]


class McpToolDetail(ApiModel):
    name: str
    title: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] | None = None


class ValidateMcpResponse(ApiModel):
    ok: bool
    tool_count: int = 0
    message: str
    tools: list[str] = Field(default_factory=list)
    tool_details: list[McpToolDetail] = Field(default_factory=list)


class CreateMcpServerRequest(ApiModel):
    name: str = Field(min_length=1)
    transport: Literal["stdio", "sse", "streamable_http"]
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    # Remotes without auth are forced off in the create handler regardless.
    enabled: bool = False
    catalog_id: str | None = None
    description: str | None = None
    oauth_client_id: str | None = None
    oauth_server_url: str | None = None
    oauth_scopes: str | None = None
    headers_helper_command: str | None = None
    headers: dict[str, str] | None = None


class UpdateMcpServerRequest(ApiModel):
    name: str | None = None
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    enabled: bool | None = None
    catalog_id: str | None = None
    description: str | None = None
    oauth_client_id: str | None = None
    oauth_server_url: str | None = None
    oauth_scopes: str | None = None
    headers_helper_command: str | None = None
    headers: dict[str, str] | None = None
