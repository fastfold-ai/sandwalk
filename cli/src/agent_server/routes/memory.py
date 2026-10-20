"""`/v1/memory/*` routes for Memory, Living Wiki, Cookbooks, and Omnigraph."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from agent_server.app_deps import AppDeps
from agent_server.memory_service import MemoryService
from agent_server.models.memory import (
    CookbookList,
    CreateGraphClaimRequest,
    CreateMemoryEntryRequest,
    DistillSessionRequest,
    DistillSessionResponse,
    GraphBranch,
    GraphBranchActionRequest,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    MemoryEntry,
    MemoryEntryList,
    MemoryOverview,
    MemorySettings,
    OmnigraphEngineStatus,
    PendingMemoryWriteList,
    RunCookbookQueryRequest,
    SelectCookbookRequest,
    UpdateMemoryEntryRequest,
    UpdateMemorySettingsRequest,
    UpsertGraphNodeRequest,
    UpsertWikiPageRequest,
    WikiPageDetail,
    WikiPageList,
)


def register_memory_routes(app: FastAPI, deps: AppDeps) -> None:
    def _svc() -> MemoryService:
        return MemoryService(agent_store=deps.store)

    @app.get("/v1/memory/overview", response_model=MemoryOverview)
    async def get_memory_overview(
        scope: str = Query(default="global"),
    ) -> MemoryOverview:
        return await asyncio.to_thread(_svc().get_overview, scope)

    @app.get("/v1/memory/settings", response_model=MemorySettings)
    async def get_memory_settings() -> MemorySettings:
        return await asyncio.to_thread(_svc().get_settings)

    @app.patch("/v1/memory/settings", response_model=MemorySettings)
    async def patch_memory_settings(
        payload: UpdateMemorySettingsRequest,
    ) -> MemorySettings:
        return await asyncio.to_thread(_svc().update_settings, payload)

    @app.get("/v1/memory/entries", response_model=MemoryEntryList)
    async def list_memory_entries(
        scope: str = Query(default="global"),
        include_user: bool = Query(default=True, alias="includeUser"),
    ) -> MemoryEntryList:
        return await asyncio.to_thread(
            _svc().list_entries, scope, include_user=include_user
        )

    @app.post("/v1/memory/entries", response_model=MemoryEntry, status_code=201)
    async def create_memory_entry(
        payload: CreateMemoryEntryRequest,
    ) -> MemoryEntry:
        try:
            return await asyncio.to_thread(_svc().create_entry, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/v1/memory/entries/{entry_id}", response_model=MemoryEntry)
    async def update_memory_entry(
        entry_id: str,
        payload: UpdateMemoryEntryRequest,
    ) -> MemoryEntry:
        try:
            updated = await asyncio.to_thread(_svc().update_entry, entry_id, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if updated is None:
            raise HTTPException(status_code=404, detail="Memory entry not found.")
        return updated

    @app.delete("/v1/memory/entries/{entry_id}")
    async def delete_memory_entry(entry_id: str) -> dict[str, bool]:
        deleted = await asyncio.to_thread(_svc().delete_entry, entry_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory entry not found.")
        return {"deleted": True}

    @app.get("/v1/memory/pending", response_model=PendingMemoryWriteList)
    async def list_pending_memory_writes(
        scope: str | None = Query(default=None),
    ) -> PendingMemoryWriteList:
        return await asyncio.to_thread(_svc().list_pending, scope)

    @app.post("/v1/memory/pending/{pending_id}/approve")
    async def approve_pending_memory_write(pending_id: str) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(_svc().approve_pending, pending_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Pending write not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/memory/pending/{pending_id}/reject")
    async def reject_pending_memory_write(pending_id: str) -> dict[str, bool]:
        rejected = await asyncio.to_thread(_svc().reject_pending, pending_id)
        if not rejected:
            raise HTTPException(status_code=404, detail="Pending write not found.")
        return {"rejected": True}

    @app.get("/v1/memory/wiki", response_model=WikiPageList)
    async def list_wiki_pages(
        scope: str = Query(default="global"),
    ) -> WikiPageList:
        return await asyncio.to_thread(_svc().list_wiki, scope)

    @app.get("/v1/memory/wiki/{slug}", response_model=WikiPageDetail)
    async def get_wiki_page(
        slug: str,
        scope: str = Query(default="global"),
    ) -> WikiPageDetail:
        page = await asyncio.to_thread(_svc().get_wiki_page, slug, scope)
        if page is None:
            raise HTTPException(status_code=404, detail="Wiki page not found.")
        return page

    @app.put("/v1/memory/wiki/{slug}", response_model=WikiPageDetail)
    async def put_wiki_page(
        slug: str,
        payload: UpsertWikiPageRequest,
    ) -> WikiPageDetail:
        return await asyncio.to_thread(_svc().write_wiki_page, slug, payload)

    @app.delete("/v1/memory/wiki/{slug}")
    async def delete_wiki_page(
        slug: str,
        scope: str = Query(default="global"),
    ) -> dict[str, bool]:
        deleted = await asyncio.to_thread(_svc().delete_wiki_page, slug, scope)
        if not deleted:
            raise HTTPException(status_code=404, detail="Wiki page not found.")
        return {"deleted": True}

    @app.get("/v1/memory/cookbooks", response_model=CookbookList)
    async def list_cookbooks(
        scope: str = Query(default="global"),
    ) -> CookbookList:
        return await asyncio.to_thread(_svc().list_cookbooks, scope)

    @app.post("/v1/memory/cookbooks/select", response_model=GraphSnapshot)
    async def select_cookbook(
        payload: SelectCookbookRequest,
    ) -> GraphSnapshot:
        try:
            return await asyncio.to_thread(
                _svc().select_cookbook,
                scope=payload.scope,
                cookbook_id=payload.cookbook_id,
                load_demo_seed=payload.load_demo_seed,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/memory/cookbooks/query", response_model=GraphSnapshot)
    async def run_cookbook_query(
        payload: RunCookbookQueryRequest,
    ) -> GraphSnapshot:
        return await asyncio.to_thread(
            _svc().get_graph,
            payload.scope,
            branch=payload.branch,
            query_name=payload.query_name,
        )

    @app.get("/v1/memory/graph", response_model=GraphSnapshot)
    async def get_memory_graph(
        scope: str = Query(default="global"),
        branch: str = Query(default="main"),
        query_name: str | None = Query(default=None, alias="queryName"),
    ) -> GraphSnapshot:
        return await asyncio.to_thread(
            _svc().get_graph,
            scope,
            branch=branch,
            query_name=query_name,
        )

    @app.post("/v1/memory/graph/nodes", response_model=GraphNode, status_code=201)
    async def upsert_graph_node(
        payload: UpsertGraphNodeRequest,
    ) -> GraphNode:
        return await asyncio.to_thread(_svc().upsert_graph_node, payload)

    @app.delete("/v1/memory/graph/nodes/{node_id:path}")
    async def delete_graph_node(
        node_id: str,
        scope: str = Query(default="global"),
        branch: str = Query(default="main"),
    ) -> dict[str, bool]:
        deleted = await asyncio.to_thread(
            _svc().delete_graph_node, node_id, scope, branch
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Graph node not found.")
        return {"deleted": True}

    @app.post("/v1/memory/graph/claims", response_model=GraphEdge, status_code=201)
    async def create_graph_claim(
        payload: CreateGraphClaimRequest,
    ) -> GraphEdge:
        return await asyncio.to_thread(_svc().record_graph_claim, payload)

    @app.post("/v1/memory/graph/branches", response_model=list[GraphBranch])
    async def manage_graph_branches(
        payload: GraphBranchActionRequest,
    ) -> list[GraphBranch]:
        try:
            return await asyncio.to_thread(_svc().manage_graph_branch, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/v1/memory/distill/{session_id}",
        response_model=DistillSessionResponse,
    )
    async def distill_session_route(
        session_id: str,
        payload: DistillSessionRequest | None = None,
    ) -> DistillSessionResponse:
        body = payload or DistillSessionRequest()
        try:
            return await asyncio.to_thread(
                _svc().distill_session,
                session_id,
                scope=body.scope,
                include_wiki=body.include_wiki,
                include_graph=body.include_graph,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.get("/v1/memory/omnigraph/status", response_model=OmnigraphEngineStatus)
    async def get_omnigraph_status_route(
        scope: str = Query(default="global"),
    ) -> OmnigraphEngineStatus:
        return await asyncio.to_thread(_svc().omnigraph_status, scope)

    @app.post("/v1/memory/omnigraph/install", response_model=OmnigraphEngineStatus)
    async def install_omnigraph_route() -> OmnigraphEngineStatus:
        return await asyncio.to_thread(_svc().omnigraph_install)

    @app.post("/v1/memory/omnigraph/sync")
    async def sync_omnigraph_route(
        scope: str = Query(default="global"),
        branch: str = Query(default="main"),
    ) -> dict[str, Any]:
        return await asyncio.to_thread(_svc().omnigraph_sync, scope, branch)

    @app.post("/v1/memory/demo/seed")
    async def seed_memory_demo_route(
        force: bool = Query(default=True),
    ) -> dict[str, Any]:
        return await asyncio.to_thread(_svc().seed_showcase, force=force)
