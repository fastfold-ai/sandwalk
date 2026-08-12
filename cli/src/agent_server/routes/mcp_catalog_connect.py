"""MCP catalog connect/disconnect and enable-toggle routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.models import (
    ConnectMcpCatalogRequest,
    ConnectMcpCatalogResponse,
    UpdateMcpCatalogRequest,
)


def register_mcp_catalog_connect_routes(app: FastAPI, deps: AppDeps) -> None:
    mcp_service = deps.mcp_service

    @app.post(
        "/v1/mcp-servers/catalog/{catalog_id}/connect",
        response_model=ConnectMcpCatalogResponse,
    )
    async def connect_mcp_catalog(
        catalog_id: str,
        payload: ConnectMcpCatalogRequest,
    ) -> ConnectMcpCatalogResponse:
        try:
            if payload.method == "oauth":
                result = await asyncio.to_thread(mcp_service.start_oauth, catalog_id)
                return ConnectMcpCatalogResponse(
                    ok=True,
                    authorize_url=result.get("authorizeUrl"),
                    state=result.get("state"),
                    redirect_uri=result.get("redirectUri"),
                    catalog_id=result.get("catalogId") or catalog_id,
                    message="Open authorizeUrl in a browser to finish OAuth",
                )
            if not payload.api_key:
                raise HTTPException(status_code=400, detail="apiKey is required for API key connect")
            result = await asyncio.to_thread(
                mcp_service.connect_with_api_key,
                catalog_id,
                payload.api_key,
            )
            return ConnectMcpCatalogResponse(
                ok=bool(result.get("ok")),
                catalog_id=catalog_id,
                server_id=result.get("serverId"),
                enabled=result.get("enabled"),
                tool_count=result.get("toolCount"),
                message=result.get("message"),
                tools=list(result.get("tools") or []),
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown MCP catalog entry") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.delete(
        "/v1/mcp-servers/catalog/{catalog_id}/connect",
        response_model=ConnectMcpCatalogResponse,
    )
    async def disconnect_mcp_catalog(catalog_id: str) -> ConnectMcpCatalogResponse:
        try:
            _result = await asyncio.to_thread(mcp_service.disconnect, catalog_id)
            return ConnectMcpCatalogResponse(
                ok=True,
                catalog_id=catalog_id,
                enabled=False,
                message="Disconnected — credentials cleared and MCP disabled",
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown MCP catalog entry") from None

    @app.patch(
        "/v1/mcp-servers/catalog/{catalog_id}",
        response_model=ConnectMcpCatalogResponse,
    )
    async def update_mcp_catalog(
        catalog_id: str,
        payload: UpdateMcpCatalogRequest,
    ) -> ConnectMcpCatalogResponse:
        try:
            result = await asyncio.to_thread(
                mcp_service.set_enabled,
                catalog_id,
                payload.enabled,
            )
            from agent.deepagents_runtime.mcp_tools import clear_mcp_tool_caches
            from agent_server import ttl_cache

            clear_mcp_tool_caches()
            ttl_cache.invalidate("mcp:")
            return ConnectMcpCatalogResponse(
                ok=bool(result.get("ok")),
                catalog_id=catalog_id,
                server_id=result.get("serverId"),
                enabled=result.get("enabled"),
                message=(
                    "Enabled" if result.get("enabled") else "Disabled"
                ),
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown MCP catalog entry") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
