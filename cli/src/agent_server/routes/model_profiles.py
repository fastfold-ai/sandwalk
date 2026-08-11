"""`/v1/model-profiles/*` routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, Query

from agent_server.app_deps import AppDeps
from agent_server.models import (
    DeleteModelProfileResponse,
    DiscoverModelEndpointRequest,
    ModelProfile,
    ModelProfileList,
    ModelProfileProbeResult,
    ModelProfileSecretResponse,
    UpsertModelProfileRequest,
)


def register_model_profile_routes(app: FastAPI, deps: AppDeps) -> None:
    models_service = deps.models_service

    @app.get("/v1/model-profiles", response_model=ModelProfileList)
    async def list_model_profiles(
        include_cloud: bool = Query(default=True),
    ) -> ModelProfileList:
        return await asyncio.to_thread(
            models_service.list_profiles,
            include_cloud=include_cloud,
        )

    # Static path must be registered before `/{profile_id}` or POST /discover
    # is captured as profile_id="discover" and returns 405.
    @app.post(
        "/v1/model-profiles/discover",
        response_model=ModelProfileProbeResult,
    )
    async def discover_model_endpoint(
        payload: DiscoverModelEndpointRequest,
    ) -> ModelProfileProbeResult:
        return await asyncio.to_thread(
            models_service.discover_endpoint,
            backend=payload.backend,
            base_url=payload.base_url,
            api_key=payload.api_key,
        )

    @app.post("/v1/model-profiles", response_model=ModelProfile, status_code=201)
    async def create_model_profile(payload: UpsertModelProfileRequest) -> ModelProfile:
        try:
            return await asyncio.to_thread(models_service.upsert_profile, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/v1/model-profiles/{profile_id}", response_model=ModelProfile)
    async def update_model_profile(
        profile_id: str,
        payload: UpsertModelProfileRequest,
    ) -> ModelProfile:
        merged = payload.model_copy(update={"id": profile_id})
        try:
            return await asyncio.to_thread(models_service.upsert_profile, merged)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/v1/model-profiles/{profile_id}/secret",
        response_model=ModelProfileSecretResponse,
    )
    async def reveal_model_profile_secret(
        profile_id: str,
    ) -> ModelProfileSecretResponse:
        """Return the stored profile API key for local reveal/copy."""
        try:
            return await asyncio.to_thread(
                models_service.reveal_profile_secret, profile_id
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail="Model profile not found."
            ) from exc

    @app.delete("/v1/model-profiles/{profile_id}", response_model=DeleteModelProfileResponse)
    async def delete_model_profile(profile_id: str) -> DeleteModelProfileResponse:
        try:
            removed = await asyncio.to_thread(models_service.delete_profile, profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not removed:
            raise HTTPException(status_code=404, detail="Model profile not found.")
        return DeleteModelProfileResponse(ok=True, id=profile_id)

    @app.post(
        "/v1/model-profiles/{profile_id}/probe",
        response_model=ModelProfileProbeResult,
    )
    async def probe_model_profile(profile_id: str) -> ModelProfileProbeResult:
        try:
            return await asyncio.to_thread(models_service.probe_profile, profile_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Model profile not found.") from exc
