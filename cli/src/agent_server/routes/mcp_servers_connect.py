"""Custom MCP server connect and validate routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.models import (
    ConnectMcpCatalogRequest,
    ConnectMcpCatalogResponse,
    McpToolDetail,
    ValidateMcpResponse,
)


def register_mcp_server_connect_routes(app: FastAPI, deps: AppDeps) -> None:
    mcp_service = deps.mcp_service

    @app.post(
        "/v1/mcp-servers/{server_id}/connect",
        response_model=ConnectMcpCatalogResponse,
    )
    async def connect_mcp_server(
        server_id: str,
        payload: ConnectMcpCatalogRequest,
    ) -> ConnectMcpCatalogResponse:
        """OAuth or API-key connect for a custom remote MCP (Cursor-style)."""
        try:
            if payload.method == "oauth":
                result = await asyncio.to_thread(
                    mcp_service.start_oauth_custom,
                    server_id,
                )
                return ConnectMcpCatalogResponse(
                    ok=True,
                    authorize_url=result.get("authorizeUrl"),
                    state=result.get("state"),
                    redirect_uri=result.get("redirectUri"),
                    server_id=result.get("serverId") or server_id,
                    message="Open authorizeUrl in a browser to finish OAuth",
                )
            if not payload.api_key:
                raise HTTPException(
                    status_code=400,
                    detail="apiKey is required for API key connect",
                )
            result = await asyncio.to_thread(
                mcp_service.connect_custom_api_key,
                server_id,
                payload.api_key,
            )
            return ConnectMcpCatalogResponse(
                ok=bool(result.get("ok")),
                server_id=server_id,
                enabled=False,
                tool_count=result.get("toolCount"),
                message=result.get("message"),
                tools=list(result.get("tools") or []),
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="MCP server not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.post(
        "/v1/mcp-servers/{server_id}/validate",
        response_model=ValidateMcpResponse,
    )
    async def validate_mcp_server(server_id: str) -> ValidateMcpResponse:
        try:
            result = await asyncio.to_thread(mcp_service.validate, None, server_id)
            details = []
            for item in result.get("toolDetails") or []:
                if not isinstance(item, dict):
                    continue
                details.append(
                    McpToolDetail(
                        name=str(item.get("name") or ""),
                        title=item.get("title"),
                        description=item.get("description"),
                        input_schema=item.get("inputSchema"),
                    )
                )
            return ValidateMcpResponse(
                ok=bool(result.get("ok")),
                tool_count=int(result.get("toolCount") or 0),
                message=str(result.get("message") or ""),
                tools=list(result.get("tools") or []),
                tool_details=details,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="MCP server not found") from None
