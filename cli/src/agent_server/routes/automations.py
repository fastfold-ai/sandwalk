"""FastAPI `/v1/automations/*` and `/v1/ssh/*` routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from agent_server.app_deps import AppDeps
from agent_server.automations_service import AutomationsService
from agent_server.models.automations import (
    Automation,
    AutomationList,
    AutomationRun,
    AutomationRunList,
    AutomationTemplateList,
    CreateAutomationRequest,
    CreateSshHostRequest,
    DeleteAutomationResponse,
    DeleteSshHostResponse,
    SshConfigFileResponse,
    SshConnectRequest,
    SshConnectResponse,
    SshExecRequest,
    SshExecResponse,
    SshHost,
    SshHostList,
    SshProbeResult,
    SshSlurmStatusResponse,
    SshSyncRequest,
    SshSyncResponse,
    TriggerAutomationRequest,
    UpdateAutomationRequest,
    UpdateSshConfigFileRequest,
    UpdateSshHostRequest,
)
from agent_server.ssh_service import SshService


def register_automation_and_ssh_routes(app: FastAPI, deps: AppDeps) -> None:
    ssh_svc = SshService(deps.store)
    auto_svc = AutomationsService(
        deps.store, agent_service=deps.service, ssh_service=ssh_svc
    )

    # --- Automations Routes ---

    @app.get("/v1/automations/templates", response_model=AutomationTemplateList)
    async def list_automation_templates_route() -> AutomationTemplateList:
        return AutomationTemplateList(data=auto_svc.list_templates())

    @app.get("/v1/automations", response_model=AutomationList)
    async def list_automations_route() -> AutomationList:
        rows = await asyncio.to_thread(auto_svc.list_automations)
        return AutomationList(data=rows)

    @app.post("/v1/automations", response_model=Automation, status_code=201)
    async def create_automation_route(
        payload: CreateAutomationRequest,
    ) -> Automation:
        try:
            return await asyncio.to_thread(auto_svc.create_automation, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/automations/runs", response_model=AutomationRunList)
    async def list_all_automation_runs_route(
        automation_id: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> AutomationRunList:
        rows = await asyncio.to_thread(
            auto_svc.list_runs, automation_id=automation_id, limit=limit
        )
        return AutomationRunList(data=rows)

    @app.get("/v1/automations/{automation_id}", response_model=Automation)
    async def get_automation_route(automation_id: str) -> Automation:
        item = await asyncio.to_thread(auto_svc.get_automation, automation_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Automation not found.")
        return item

    @app.patch("/v1/automations/{automation_id}", response_model=Automation)
    async def update_automation_route(
        automation_id: str,
        payload: UpdateAutomationRequest,
    ) -> Automation:
        try:
            updated = await asyncio.to_thread(
                auto_svc.update_automation, automation_id, payload
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if updated is None:
            raise HTTPException(status_code=404, detail="Automation not found.")
        return updated

    @app.delete(
        "/v1/automations/{automation_id}",
        response_model=DeleteAutomationResponse,
    )
    async def delete_automation_route(
        automation_id: str,
    ) -> DeleteAutomationResponse:
        deleted = await asyncio.to_thread(auto_svc.delete_automation, automation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Automation not found.")
        return DeleteAutomationResponse(deleted=True)

    @app.post(
        "/v1/automations/{automation_id}/run",
        response_model=AutomationRun,
    )
    async def trigger_automation_route(
        automation_id: str,
        payload: TriggerAutomationRequest | None = None,
    ) -> AutomationRun:
        body = payload or TriggerAutomationRequest()
        try:
            return await auto_svc.trigger_automation(
                automation_id,
                trigger_source="manual",
                transient_context=body.context,
                wait=body.wait,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Automation not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/v1/automations/webhook/{webhook_token}",
        response_model=AutomationRun,
    )
    async def webhook_trigger_automation_route(
        webhook_token: str,
        payload: dict[str, Any] | None = None,
    ) -> AutomationRun:
        found = await asyncio.to_thread(
            deps.store.get_automation_by_webhook_token, webhook_token
        )
        if found is None:
            raise HTTPException(status_code=404, detail="Invalid webhook token.")
        ctx_str = str(payload.get("context") or payload) if payload else None
        try:
            return await auto_svc.trigger_automation(
                found.id,
                trigger_source="webhook",
                transient_context=ctx_str,
                wait=False,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    # --- SSH Manager & Remote-SSH Bootstrap Routes ---

    @app.get("/v1/ssh/hosts", response_model=SshHostList)
    async def list_ssh_hosts_route(
        include_ssh_config: bool = Query(default=True),
    ) -> SshHostList:
        hosts = await asyncio.to_thread(
            ssh_svc.list_hosts, include_ssh_config=include_ssh_config
        )
        return SshHostList(data=hosts)

    @app.post("/v1/ssh/hosts", response_model=SshHost, status_code=201)
    async def create_ssh_host_route(payload: CreateSshHostRequest) -> SshHost:
        try:
            return await asyncio.to_thread(ssh_svc.create_host, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/v1/ssh/hosts/{host_id}", response_model=SshHost)
    async def update_ssh_host_route(
        host_id: str,
        payload: UpdateSshHostRequest,
    ) -> SshHost:
        updated = await asyncio.to_thread(ssh_svc.update_host, host_id, payload)
        if updated is None:
            raise HTTPException(status_code=404, detail="SSH host not found.")
        return updated

    @app.delete("/v1/ssh/hosts/{host_id}", response_model=DeleteSshHostResponse)
    async def delete_ssh_host_route(host_id: str) -> DeleteSshHostResponse:
        deleted = await asyncio.to_thread(ssh_svc.delete_host, host_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="SSH host not found.")
        return DeleteSshHostResponse(deleted=True)

    @app.post("/v1/ssh/hosts/{host_id}/probe", response_model=SshProbeResult)
    async def probe_ssh_host_route(host_id: str) -> SshProbeResult:
        try:
            return await asyncio.to_thread(ssh_svc.probe_host, host_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/v1/ssh/hosts/{host_id}/slurm",
        response_model=SshSlurmStatusResponse,
    )
    async def slurm_status_ssh_host_route(host_id: str) -> SshSlurmStatusResponse:
        try:
            return await asyncio.to_thread(ssh_svc.get_slurm_status, host_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/ssh/connect", response_model=SshConnectResponse)
    async def connect_and_bootstrap_ssh_route(
        payload: SshConnectRequest,
    ) -> SshConnectResponse:
        try:
            return await asyncio.to_thread(ssh_svc.connect_and_bootstrap, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/ssh/hosts/{host_id}/disconnect")
    async def disconnect_ssh_tunnel_route(host_id: str) -> dict[str, bool]:
        closed = await asyncio.to_thread(ssh_svc.close_tunnel, host_id)
        return {"closed": closed}

    @app.post("/v1/ssh/exec", response_model=SshExecResponse)
    async def exec_ssh_command_route(payload: SshExecRequest) -> SshExecResponse:
        try:
            return await asyncio.to_thread(
                ssh_svc.exec_command,
                payload.host_id_or_target,
                payload.command,
                workdir=payload.workdir,
                timeout_seconds=payload.timeout_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/ssh/sync", response_model=SshSyncResponse)
    async def sync_ssh_files_route(payload: SshSyncRequest) -> SshSyncResponse:
        try:
            return await asyncio.to_thread(
                ssh_svc.sync_files,
                payload.host_id_or_target,
                local_path=payload.local_path,
                remote_path=payload.remote_path,
                direction=payload.direction,
                delete=payload.delete,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/ssh/config", response_model=SshConfigFileResponse)
    async def get_ssh_config_route() -> SshConfigFileResponse:
        return await asyncio.to_thread(ssh_svc.get_ssh_config_file)

    @app.put("/v1/ssh/config", response_model=SshConfigFileResponse)
    async def update_ssh_config_route(
        payload: UpdateSshConfigFileRequest,
    ) -> SshConfigFileResponse:
        return await asyncio.to_thread(
            ssh_svc.update_ssh_config_file, payload.content
        )
