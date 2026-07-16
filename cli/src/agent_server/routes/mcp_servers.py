"""Custom MCP server listing, mcp.json config export/import, and create routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.mcp_json_config import apply_mcp_json, get_or_export_mcp_json, mcp_json_path
from agent_server.mcp_service import enrich_mcp_server, set_custom_headers
from agent_server.models import (
    CreateMcpServerRequest,
    McpJsonConfigRequest,
    McpJsonConfigResponse,
    McpServer,
    McpServerList,
)


def register_mcp_server_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get("/v1/mcp-servers", response_model=McpServerList)
    async def list_mcp_servers() -> McpServerList:
        def _list() -> list[McpServer]:
            # Seed catalog templates into DB + mcp.json before listing.
            get_or_export_mcp_json(store)
            out: list[McpServer] = []
            for server in store.list_mcp_servers():
                enriched = enrich_mcp_server(server)
                # Persist force-off for stale remotes that were saved as enabled.
                if (
                    not enriched.catalog_id
                    and enriched.transport != "stdio"
                    and not enriched.headers_configured
                    and server.enabled
                ):
                    updated = store.update_mcp_server(server.id, enabled=False)
                    if updated is not None:
                        enriched = enrich_mcp_server(updated)
                out.append(enriched)
            return out

        return McpServerList(data=await asyncio.to_thread(_list))

    @app.get("/v1/mcp-servers/config", response_model=McpJsonConfigResponse)
    async def get_mcp_json_config() -> McpJsonConfigResponse:
        """Export MCP servers (custom + seeded catalog) as mcp.json."""

        def _get() -> McpJsonConfigResponse:
            document = get_or_export_mcp_json(store)
            return McpJsonConfigResponse(
                path=str(mcp_json_path()),
                document=document,
            )

        return await asyncio.to_thread(_get)

    @app.put("/v1/mcp-servers/config", response_model=McpJsonConfigResponse)
    async def put_mcp_json_config(
        payload: McpJsonConfigRequest,
    ) -> McpJsonConfigResponse:
        """Replace MCP servers from an mcp.json document (custom + catalog)."""

        def _put() -> McpJsonConfigResponse:
            try:
                document = apply_mcp_json(store, payload.document)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return McpJsonConfigResponse(
                path=str(mcp_json_path()),
                document=document,
            )

        return await asyncio.to_thread(_put)

    @app.post("/v1/mcp-servers", response_model=McpServer, status_code=201)
    async def create_mcp_server(payload: CreateMcpServerRequest) -> McpServer:
        if payload.transport == "stdio" and not payload.command:
            raise HTTPException(status_code=400, detail="stdio MCP servers require a command.")
        if payload.transport != "stdio" and not payload.url:
            raise HTTPException(status_code=400, detail="Remote MCP servers require a URL.")

        def _create() -> McpServer:
            enabled = payload.enabled
            # Remote custom servers without credentials stay off until Connect.
            if (
                not payload.catalog_id
                and payload.transport != "stdio"
                and not payload.headers
                and not (payload.headers_helper_command or "").strip()
            ):
                enabled = False
            url = payload.url
            if url and "://" not in url:
                url = f"https://{url}"
            server = store.create_mcp_server(
                name=payload.name,
                transport=payload.transport,
                command=payload.command,
                args=payload.args,
                url=url,
                enabled=enabled,
                catalog_id=payload.catalog_id,
                description=payload.description,
                oauth_client_id=payload.oauth_client_id,
                oauth_server_url=payload.oauth_server_url,
                oauth_scopes=payload.oauth_scopes,
                headers_helper_command=payload.headers_helper_command,
            )
            if payload.headers is not None:
                set_custom_headers(server.id, payload.headers)
            get_or_export_mcp_json(store)
            return enrich_mcp_server(server)

        return await asyncio.to_thread(_create)
