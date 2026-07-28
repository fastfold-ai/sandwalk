"""`/v1/integrations/*` routes."""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import Body, FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.models import (
    IntegrationList,
    IntegrationProvider,
    IntegrationSetupRequest,
    IntegrationSetupResponse,
    UpdateIntegrationRequest,
    ValidateIntegrationResponse,
)


def register_integration_routes(app: FastAPI, deps: AppDeps) -> None:
    integrations_service = deps.integrations_service

    async def _sync_slack_relay_after_fastfold(integration_key: str) -> None:
        if integration_key != "fastfold-cloud":
            return
        with contextlib.suppress(Exception):
            await deps.connector_service.reconcile_fastfold_auth()

    @app.get("/v1/integrations", response_model=IntegrationList)
    async def list_integrations() -> IntegrationList:
        return IntegrationList(data=await asyncio.to_thread(integrations_service.list))

    @app.get("/v1/integrations/{integration_key}", response_model=IntegrationProvider)
    async def get_integration(integration_key: str) -> IntegrationProvider:
        provider = await asyncio.to_thread(integrations_service.get, integration_key)
        if provider is None:
            raise HTTPException(status_code=404, detail="Integration not found.")
        return provider

    @app.put("/v1/integrations/{integration_key}", response_model=IntegrationProvider)
    async def update_integration(
        integration_key: str,
        payload: UpdateIntegrationRequest,
    ) -> IntegrationProvider:
        try:
            values = dict(payload.values)
            if payload.value:
                provider = await asyncio.to_thread(
                    integrations_service.get,
                    integration_key,
                )
                if provider is None:
                    raise KeyError(integration_key)
                values[provider.env_var] = payload.value
            provider = await asyncio.to_thread(
                integrations_service.update,
                integration_key,
                values,
            )
            await _sync_slack_relay_after_fastfold(integration_key)
            return provider
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Integration not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/v1/integrations/{integration_key}", response_model=IntegrationProvider)
    async def remove_integration(integration_key: str) -> IntegrationProvider:
        try:
            provider = await asyncio.to_thread(
                integrations_service.remove, integration_key
            )
            await _sync_slack_relay_after_fastfold(integration_key)
            return provider
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Integration not found.") from exc

    @app.post(
        "/v1/integrations/{integration_key}/validate",
        response_model=ValidateIntegrationResponse,
    )
    async def validate_integration(integration_key: str) -> ValidateIntegrationResponse:
        try:
            return await asyncio.to_thread(integrations_service.validate, integration_key)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Integration not found.") from exc

    @app.post(
        "/v1/integrations/{integration_key}/capabilities/{capability_id}/install",
        response_model=IntegrationProvider,
    )
    async def install_integration_capability(
        integration_key: str,
        capability_id: str,
    ) -> IntegrationProvider:
        try:
            return await asyncio.to_thread(
                integrations_service.install_capability,
                integration_key,
                capability_id,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail="Installable integration capability not found.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/integrations/{integration_key}/autofill", response_model=IntegrationProvider)
    async def autofill_integration(integration_key: str) -> IntegrationProvider:
        try:
            return await asyncio.to_thread(integrations_service.autofill, integration_key)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Integration not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/v1/integrations/{integration_key}/setup",
        response_model=IntegrationSetupResponse,
    )
    async def setup_integration(
        integration_key: str,
        payload: IntegrationSetupRequest = Body(
            default_factory=IntegrationSetupRequest
        ),
    ) -> IntegrationSetupResponse:
        try:
            return await asyncio.to_thread(
                integrations_service.setup,
                integration_key,
                payload.working_directory,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Integration not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
