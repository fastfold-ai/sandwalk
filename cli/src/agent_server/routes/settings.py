"""`/v1/settings/*` runtime, onboarding, sandbox, and prompt-budget routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, Query

from agent_server.app_deps import AppDeps
from agent_server.models import (
    OnboardingSettings,
    PromptBudgetResponse,
    RunCapacity,
    RuntimeSettings,
    SandboxProbeReport,
    SandboxSettings,
    UpdateOnboardingSettingsRequest,
    UpdateRuntimeSettingsRequest,
    UpdateSandboxSettingsRequest,
)


def register_settings_routes(app: FastAPI, deps: AppDeps) -> None:
    settings_service = deps.settings_service
    sandbox_settings_service = deps.sandbox_settings_service

    @app.get("/v1/settings/prompt-budget", response_model=PromptBudgetResponse)
    async def get_prompt_budget(
        specialist_id: str | None = Query(default=None, alias="specialistId"),
        project_id: str | None = Query(default=None, alias="projectId"),
        sample_query: str | None = Query(default=None, alias="sampleQuery"),
        token_count_method: str | None = Query(
            default=None, alias="tokenCountMethod"
        ),
    ) -> PromptBudgetResponse:
        from agent_server.prompt_budget_service import PromptBudgetService

        try:
            return await asyncio.wait_for(
                PromptBudgetService(deps.store).estimate(
                    specialist_id=specialist_id,
                    project_id=project_id,
                    sample_query=sample_query,
                    token_count_method=token_count_method,
                ),
                timeout=45.0,
            )
        except TimeoutError as exc:
            raise HTTPException(
                status_code=504,
                detail=(
                    "Context estimate timed out while building prompts/tool schemas. "
                    "Disable hung MCP servers (e.g. Latch Bio) and retry."
                ),
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail=f"Context estimate failed: {exc}",
            ) from exc

    @app.get("/v1/settings/runtime", response_model=RuntimeSettings)
    async def get_runtime_settings() -> RuntimeSettings:
        return await asyncio.to_thread(settings_service.get)

    @app.patch("/v1/settings/runtime", response_model=RuntimeSettings)
    async def update_runtime_settings(
        payload: UpdateRuntimeSettingsRequest,
    ) -> RuntimeSettings:
        try:
            return await asyncio.to_thread(settings_service.update, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/settings/capacity", response_model=RunCapacity)
    async def get_run_capacity() -> RunCapacity:
        """How many agent runs are executing or queued, and the memory headroom."""
        import os

        from agent_server.run_admission import run_admission

        snap = await asyncio.to_thread(run_admission().snapshot)
        return RunCapacity(
            running=snap.running,
            queued=snap.queued,
            max_concurrent_runs=snap.max_concurrent_runs,
            min_free_memory_mb=snap.min_free_memory_mb,
            available_memory_mb=snap.available_memory_mb,
            total_memory_mb=snap.total_memory_mb,
            cpu_count=os.cpu_count() or 1,
        )

    @app.get("/v1/settings/onboarding", response_model=OnboardingSettings)
    async def get_onboarding_settings() -> OnboardingSettings:
        return await asyncio.to_thread(settings_service.get_onboarding)

    @app.patch("/v1/settings/onboarding", response_model=OnboardingSettings)
    async def update_onboarding_settings(
        payload: UpdateOnboardingSettingsRequest,
    ) -> OnboardingSettings:
        return await asyncio.to_thread(settings_service.update_onboarding, payload)

    @app.post("/v1/settings/reset", response_model=OnboardingSettings)
    async def reset_settings() -> OnboardingSettings:
        return await asyncio.to_thread(settings_service.reset_to_factory_defaults)

    @app.get("/v1/settings/sandbox", response_model=SandboxSettings)
    async def get_sandbox_settings() -> SandboxSettings:
        return await asyncio.to_thread(sandbox_settings_service.get)

    @app.patch("/v1/settings/sandbox", response_model=SandboxSettings)
    async def update_sandbox_settings(
        payload: UpdateSandboxSettingsRequest,
    ) -> SandboxSettings:
        try:
            return await asyncio.to_thread(sandbox_settings_service.update, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/settings/sandbox/probe", response_model=SandboxProbeReport)
    async def probe_sandbox_settings() -> SandboxProbeReport:
        return await asyncio.to_thread(sandbox_settings_service.probe)
