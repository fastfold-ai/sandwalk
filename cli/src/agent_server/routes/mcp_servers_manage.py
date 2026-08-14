"""Custom MCP server update and delete routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.mcp_json_config import get_or_export_mcp_json, mark_catalog_removed
from agent_server.mcp_service import (
    clear_custom_headers,
    custom_server_credentials_configured,
    enrich_mcp_server,
    set_custom_headers,
)
from agent_server.models import DeleteSessionResponse, McpServer, UpdateMcpServerRequest


def register_mcp_server_manage_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store
    mcp_service = deps.mcp_service

    @app.patch("/v1/mcp-servers/{server_id}", response_model=McpServer)
    async def update_mcp_server(
        server_id: str,
        payload: UpdateMcpServerRequest,
    ) -> McpServer:
        def _update() -> McpServer | None:
            changes = payload.model_dump(exclude_unset=True)
            headers = changes.pop("headers", None)
            headers_provided = "headers" in payload.model_fields_set
            existing = next(
                (s for s in store.list_mcp_servers() if s.id == server_id),
                None,
            )
            if existing is None:
                return None
            # Apply headers first so enable checks see new credentials.
            if headers_provided:
                set_custom_headers(existing.id, headers)
            will_enable = bool(changes.get("enabled", existing.enabled))
            if (
                will_enable
                and not existing.catalog_id
                and existing.transport != "stdio"
            ):
                probe = existing.model_copy(
                    update={
                        "headers_helper_command": changes.get(
                            "headers_helper_command",
                            existing.headers_helper_command,
                        ),
                    }
                )
                if not custom_server_credentials_configured(probe):
                    raise ValueError(
                        "Authenticate this MCP server before enabling it."
                    )
            server = store.update_mcp_server(server_id, **changes)
            if server is None:
                return None
            if (
                will_enable
                and not server.catalog_id
                and server.transport != "stdio"
                and server.url
            ):
                # Refresh cached tool count so the list can show Connected (N).
                mcp_service.validate(server_id=server_id)
            get_or_export_mcp_json(store)
            return enrich_mcp_server(server)

        try:
            server = await asyncio.to_thread(_update)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        if server is None:
            raise HTTPException(status_code=404, detail="MCP server not found.")
        from agent.deepagents_runtime.mcp_tools import clear_mcp_tool_caches
        from agent_server import ttl_cache

        clear_mcp_tool_caches()
        ttl_cache.invalidate("mcp:")
        return server

    @app.delete("/v1/mcp-servers/{server_id}", response_model=DeleteSessionResponse)
    async def delete_mcp_server(server_id: str) -> DeleteSessionResponse:
        def _delete() -> bool:
            existing = next(
                (s for s in store.list_mcp_servers() if s.id == server_id),
                None,
            )
            if existing is None:
                return False
            catalog_id = getattr(existing, "catalog_id", None)
            deleted = store.delete_mcp_server(server_id)
            if deleted:
                clear_custom_headers(server_id)
                if catalog_id:
                    mark_catalog_removed(str(catalog_id))
                get_or_export_mcp_json(store)
            return deleted

        if not await asyncio.to_thread(_delete):
            raise HTTPException(status_code=404, detail="MCP server not found.")
        from agent.deepagents_runtime.mcp_tools import clear_mcp_tool_caches
        from agent_server import ttl_cache

        clear_mcp_tool_caches()
        ttl_cache.invalidate("mcp:")
        return DeleteSessionResponse()
