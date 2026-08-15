"""`/v1/integrations/*` routes."""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import Body, FastAPI, HTTPException, Request

from agent_server.app_deps import AppDeps
from agent_server.models import (
    FastfoldOneClickImport,
    FastfoldOneClickStart,
    IntegrationList,
    IntegrationProvider,
    IntegrationSecretResponse,
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

    @app.get(
        "/v1/integrations/{integration_key}/secret",
        response_model=IntegrationSecretResponse,
    )
    async def reveal_integration_secret(
        integration_key: str,
    ) -> IntegrationSecretResponse:
        """Return the stored secret for local reveal/copy (user opt-in)."""
        try:
            return await asyncio.to_thread(
                integrations_service.reveal_secret, integration_key
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Integration not found.") from exc

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

    @app.post(
        "/v1/integrations/fastfold-cloud/one-click",
        response_model=FastfoldOneClickStart,
    )
    async def start_fastfold_one_click(request: Request) -> FastfoldOneClickStart:
        from agent_server.connectors.service import oauth_callback_return_to
        from agent_server.integrations_service.fastfold_one_click import (
            start_fastfold_one_click as _start,
        )

        return_to = oauth_callback_return_to(
            origin=request.headers.get("origin"),
            base_url=str(request.base_url),
        )
        try:
            auth_url = await asyncio.to_thread(_start, return_to=return_to)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return FastfoldOneClickStart(auth_url=auth_url)

    @app.post(
        "/v1/integrations/fastfold-cloud/one-click/import",
        response_model=FastfoldOneClickImport,
    )
    async def import_fastfold_one_click() -> FastfoldOneClickImport:
        from agent_server.integrations_service.fastfold_one_click import (
            import_fastfold_one_click as _import,
        )

        try:
            result = await asyncio.to_thread(_import, integrations_service)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if result.get("ready"):
            await _sync_slack_relay_after_fastfold("fastfold-cloud")
        return FastfoldOneClickImport(
            ready=bool(result.get("ready")),
            provider=result.get("provider"),
            team_id=(
                str(result["team_id"])
                if result.get("team_id") is not None
                else None
            ),
        )
