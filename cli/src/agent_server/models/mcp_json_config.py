from __future__ import annotations

from typing import Any

from agent_server.models.base import ApiModel


class McpJsonConfigResponse(ApiModel):
    """mcp.json document plus on-disk path."""

    path: str
    document: dict[str, Any]


class McpJsonConfigRequest(ApiModel):
    document: dict[str, Any]
