"""`/v1/skills/*` routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from agent_server.app_deps import AppDeps
from agent_server.models import (
    CatalogSkillAudit,
    CatalogSkillDetail,
    CatalogSkillList,
    InstallSkillRequest,
    SkillBatchActionRequest,
    SkillBatchActionResponse,
    SkillDetail,
    SkillList,
    SkillMutationResponse,
    SkillSourceList,
    UpdateSkillRequest,
)


def register_skill_routes(app: FastAPI, deps: AppDeps) -> None:
    skills_service = deps.skills_service

    @app.get("/v1/skills", response_model=SkillList)
    async def list_skills() -> SkillList:
        return SkillList(data=await asyncio.to_thread(skills_service.list))

    @app.get("/v1/skills/sources", response_model=SkillSourceList)
    async def list_skill_sources() -> SkillSourceList:
        return SkillSourceList(data=await asyncio.to_thread(skills_service.suggested_sources))

    @app.get("/v1/skills/catalog/search", response_model=CatalogSkillList)
    async def search_skill_catalog(
        q: str = Query(min_length=2, max_length=200),
        limit: int = Query(default=12, ge=1, le=50),
    ) -> CatalogSkillList:
        try:
            items = await asyncio.to_thread(skills_service.search_catalog, q, limit)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return CatalogSkillList(data=items, query=q, count=len(items))

    @app.get("/v1/skills/catalog/detail", response_model=CatalogSkillDetail)
    async def get_catalog_skill_detail(
        source: str = Query(min_length=1, max_length=200),
        skill: str = Query(min_length=1, max_length=200),
    ) -> CatalogSkillDetail:
        try:
            return await asyncio.to_thread(
                skills_service.get_catalog_detail,
                source,
                skill,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc) or "Skill not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/v1/skills/catalog/audit", response_model=CatalogSkillAudit)
    async def get_catalog_skill_audit(
        source: str = Query(min_length=1, max_length=200),
        skill: str = Query(min_length=1, max_length=200),
    ) -> CatalogSkillAudit:
        try:
            return await asyncio.to_thread(
                skills_service.get_catalog_audit,
                source,
                skill,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/v1/skills/{skill_name}", response_model=SkillDetail)
    async def get_skill(skill_name: str) -> SkillDetail:
        skill = await asyncio.to_thread(skills_service.get, skill_name)
        if skill is None:
            raise HTTPException(status_code=404, detail="Skill not found.")
        return skill

    @app.get("/v1/skills/{skill_name}/icon")
    async def get_skill_icon(skill_name: str) -> FileResponse:
        icon_path = await asyncio.to_thread(skills_service.get_icon_path, skill_name)
        if icon_path is None:
            raise HTTPException(status_code=404, detail="Skill icon not found.")
        return FileResponse(icon_path, filename=icon_path.name)

    @app.patch("/v1/skills/{skill_name}", response_model=SkillDetail)
    async def update_skill(skill_name: str, payload: UpdateSkillRequest) -> SkillDetail:
        if payload.enabled is None:
            raise HTTPException(status_code=400, detail="No skill updates provided.")
        result = await asyncio.to_thread(
            skills_service.set_enabled,
            skill_name,
            payload.enabled,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Skill not found.")
        detail = await asyncio.to_thread(skills_service.get, skill_name)
        if detail is None:
            raise HTTPException(status_code=404, detail="Skill not found.")
        return detail

    @app.post("/v1/skills/batch", response_model=SkillBatchActionResponse)
    async def batch_skills(payload: SkillBatchActionRequest) -> SkillBatchActionResponse:
        return await asyncio.to_thread(
            skills_service.batch_action,
            payload.action,
            payload.names,
        )

    @app.post("/v1/skills", response_model=SkillMutationResponse)
    async def install_skill(payload: InstallSkillRequest) -> SkillMutationResponse:
        result = await asyncio.to_thread(skills_service.install, payload.source)
        if not result.ok:
            raise HTTPException(status_code=400, detail=result.summary)
        return result

    @app.post("/v1/skills/upload", response_model=SkillMutationResponse)
    async def upload_skill(file: UploadFile = File(...)) -> SkillMutationResponse:
        data = await file.read()
        result = await asyncio.to_thread(
            skills_service.install_uploaded_file,
            file.filename,
            data,
        )
        if not result.ok:
            raise HTTPException(status_code=400, detail=result.summary)
        return result

    @app.delete("/v1/skills/{skill_name}", response_model=SkillMutationResponse)
    async def remove_skill(skill_name: str) -> SkillMutationResponse:
        result = await asyncio.to_thread(skills_service.remove, skill_name)
        if not result.ok:
            raise HTTPException(status_code=400, detail=result.summary)
        return result

    @app.post("/v1/skills/upgrade", response_model=SkillMutationResponse)
    async def upgrade_skills() -> SkillMutationResponse:
        return await asyncio.to_thread(skills_service.upgrade)
