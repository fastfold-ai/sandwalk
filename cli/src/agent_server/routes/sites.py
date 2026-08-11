"""Local Sites lifecycle and token-scoped preview routes."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from agent_server.app_deps import AppDeps
from agent_server.models import (
    DeleteSiteResponse,
    PublishSiteRequest,
    RegisterSiteRequest,
    RenameSiteRequest,
    Site,
    SiteList,
    SitePreview,
    SitePublishResult,
)


def _site_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc.args[0]))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="Site operation failed.")


def register_site_routes(app: FastAPI, deps: AppDeps) -> None:
    service = deps.sites_service

    @app.get("/v1/sites", response_model=SiteList)
    async def list_sites() -> SiteList:
        return SiteList(data=await asyncio.to_thread(deps.store.list_sites))

    @app.post("/v1/sites", response_model=Site, status_code=201)
    async def create_site(payload: RegisterSiteRequest) -> Site:
        try:
            return await asyncio.to_thread(
                service.register,
                name=payload.name,
                source=payload.path,
                session_id=payload.session_id,
                project_id=payload.project_id,
            )
        except Exception as exc:
            raise _site_error(exc) from exc

    @app.get("/v1/sites/{site_id}", response_model=Site)
    async def get_site(site_id: str) -> Site:
        site = await asyncio.to_thread(deps.store.get_site, site_id)
        if site is None:
            raise HTTPException(status_code=404, detail="Site not found.")
        return site

    @app.put("/v1/sites/{site_id}/content", response_model=Site)
    async def update_site(site_id: str, payload: RegisterSiteRequest) -> Site:
        try:
            return await asyncio.to_thread(
                service.register,
                site_id=site_id,
                name=payload.name,
                source=payload.path,
                session_id=payload.session_id,
                project_id=payload.project_id,
            )
        except Exception as exc:
            raise _site_error(exc) from exc

    @app.patch("/v1/sites/{site_id}", response_model=Site)
    async def rename_site(site_id: str, payload: RenameSiteRequest) -> Site:
        try:
            return await asyncio.to_thread(service.rename, site_id, payload.name)
        except Exception as exc:
            raise _site_error(exc) from exc

    @app.delete("/v1/sites/{site_id}", response_model=DeleteSiteResponse)
    async def delete_site(site_id: str) -> DeleteSiteResponse:
        try:
            await asyncio.to_thread(service.delete, site_id)
        except Exception as exc:
            raise _site_error(exc) from exc
        return DeleteSiteResponse(deleted=True)

    @app.post("/v1/sites/{site_id}/preview-ticket", response_model=SitePreview)
    async def preview_site(site_id: str) -> SitePreview:
        try:
            url, expires = await asyncio.to_thread(service.create_preview, site_id)
        except Exception as exc:
            raise _site_error(exc) from exc
        return SitePreview(url=url, expires_at=expires)

    @app.post("/v1/sites/{site_id}/publish", response_model=SitePublishResult)
    async def publish_site(site_id: str, payload: PublishSiteRequest) -> SitePublishResult:
        try:
            site = await asyncio.to_thread(service.publish, site_id, slug=payload.slug)
        except Exception as exc:
            if isinstance(exc, (KeyError, ValueError)):
                raise _site_error(exc) from exc
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return SitePublishResult(
            site=site,
            url=site.cloud_url or "",
            cloud_site_id=site.cloud_site_id,
        )

    @app.get("/v1/sites/{site_id}/preview/{token}/{asset_path:path}")
    async def serve_preview(
        site_id: str,
        token: str,
        asset_path: str,
        request: Request,
    ) -> FileResponse:
        site = service.preview_site(site_id, token)
        if site is None:
            raise HTTPException(status_code=404, detail="Preview not found or expired.")
        root = Path(site.storage_path).resolve()
        relative = asset_path or "index.html"
        candidate = (root / relative).resolve()
        if candidate != root and not candidate.is_relative_to(root):
            raise HTTPException(status_code=404, detail="Preview asset not found.")
        if not candidate.is_file():
            wants_html = "text/html" in request.headers.get("accept", "")
            if Path(relative).suffix and not wants_html:
                raise HTTPException(status_code=404, detail="Preview asset not found.")
            candidate = root / "index.html"
        media = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        headers = {
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": (
                "no-store" if candidate.name == "index.html" else "public, max-age=3600"
            ),
        }
        return FileResponse(candidate, media_type=media, headers=headers)
