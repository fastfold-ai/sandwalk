"""MCP catalog listing, install, and validate routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.mcp_json_config import install_catalog_server, seed_catalog_defaults
from agent_server.mcp_service import enrich_mcp_server
from agent_server.models import (
    McpCatalogEntryStatus,
    McpCatalogList,
    McpServer,
    McpToolDetail,
    ValidateMcpResponse,
)


def register_mcp_catalog_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store
    mcp_service = deps.mcp_service

    @app.get("/v1/mcp-servers/catalog", response_model=McpCatalogList)
    async def list_mcp_catalog() -> McpCatalogList:
        def _list() -> list:
            seed_catalog_defaults(store)
            return mcp_service.catalog_statuses()

        rows = await asyncio.to_thread(_list)
        return McpCatalogList(
            data=[McpCatalogEntryStatus.model_validate(row) for row in rows]
        )

    @app.post(
        "/v1/mcp-servers/catalog/{catalog_id}/install",
        response_model=McpServer,
        status_code=201,
    )
    async def install_mcp_catalog(
        catalog_id: str,
        force: bool = False,
    ) -> McpServer:
        """Install a catalog template (PyMOL also creates the managed launcher).

        Pass ``force=true`` to recreate the PyMOL managed venv (reinstall launcher).
        """

        def _install() -> McpServer:
            from agent.mcp_catalog import get_catalog_entry

            entry = get_catalog_entry(catalog_id)
            if entry is not None and (
                entry.transport == "stdio" or entry.auth_mode == "none"
            ):
                result = mcp_service.install_featured(catalog_id, force=force)
                return result["server"]
            server = install_catalog_server(store, catalog_id)
            return enrich_mcp_server(server)

        try:
            return await asyncio.to_thread(_install)
        except KeyError:
            raise HTTPException(
                status_code=404, detail="Unknown MCP catalog entry"
            ) from None
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.post(
        "/v1/mcp-servers/catalog/{catalog_id}/validate",
        response_model=ValidateMcpResponse,
    )
    async def validate_mcp_catalog(catalog_id: str) -> ValidateMcpResponse:
        try:
            result = await asyncio.to_thread(mcp_service.validate, catalog_id, None)
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
            raise HTTPException(status_code=404, detail="Unknown MCP catalog entry") from None
