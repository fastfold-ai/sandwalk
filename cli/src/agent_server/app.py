"""FastAPI transport for the FastFold agent application service."""

from __future__ import annotations

import asyncio
import getpass
import json
import os
import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from _version import __version__
from agent_server.account_service import AccountService
from agent_server.models import (
    AccountSummary,
    AgentModel,
    AgentModelList,
    AgentProject,
    CreateAgentModelRequest,
    DatasetInstallResponse,
    DatasetList,
    ToolBatchActionRequest,
    ToolBatchActionResponse,
    ToolList,
    ToolSummary,
    UpdateToolRequest,
    DeleteModelProfileResponse,
    ModelProfile,
    ModelProfileList,
    ModelProfileProbeResult,
    UpdateAgentModelRequest,
    UpsertModelProfileRequest,
    AgentSession,
    CatalogSkillAudit,
    CatalogSkillDetail,
    CatalogSkillList,
    Capabilities,
    CreateProjectRequest,
    CreatePtyRequest,
    CreateSessionRequest,
    DeleteProjectResponse,
    DeleteSessionResponse,
    DoctorDiagnosticsRequest,
    DoctorReport,
    HealthResponse,
    ServerCacheInfo,
    ServerLifecycleResult,
    ServerStatusReport,
    IntegrationList,
    IntegrationProvider,
    IntegrationSetupRequest,
    IntegrationSetupResponse,
    InterruptRunResponse,
    MessageList,
    MessageFeedbackRequest,
    MessageFeedbackResponse,
    McpServer,
    McpServerList,
    McpCatalogList,
    McpCatalogEntryStatus,
    ConnectMcpCatalogRequest,
    ConnectMcpCatalogResponse,
    UpdateMcpCatalogRequest,
    ValidateMcpResponse,
    CreateMcpServerRequest,
    MoveWorkspaceFileRequest,
    ProjectList,
    PtySessionInfo,
    PtySessionList,
    RuntimeSettings,
    SendMessageRequest,
    SessionList,
    StartRunResponse,
    StorageReport,
    EnvironmentReport,
    EnvironmentPackageRequest,
    EnvironmentPackageMutationResult,
    InstallSkillRequest,
    SkillDetail,
    SkillList,
    SkillSourceList,
    SkillBatchActionRequest,
    SkillBatchActionResponse,
    SkillMutationResponse,
    UpdateSkillRequest,
    UpdateIntegrationRequest,
    UpdateProjectRequest,
    UpdatePtyRequest,
    UpdateRuntimeSettingsRequest,
    UpdateMcpServerRequest,
    ValidateIntegrationResponse,
    UpdateSessionRequest,
    AutoTitleSessionRequest,
    CreateWorkspaceFolderRequest,
    WorkspaceFileContent,
    WorkspaceFileList,
    WorkspaceMutationResponse,
    WriteWorkspaceFileRequest,
)
from agent_server.pty_manager import PtyManager
from agent_server.service import AgentService, SessionBusyError
from agent_server.skills_service import SkillsService
from agent_server.integrations_service import IntegrationsService
from agent_server.mcp_service import (
    McpService,
    clear_custom_headers,
    enrich_mcp_server,
    set_custom_headers,
)
from agent_server.models_service import ModelsService
from agent_server.datasets_service import DatasetsService
from agent_server.tools_service import ToolsService
from agent_server.settings_service import SettingsService
from agent_server.store import AgentStore
from agent_server.workspace import (
    MAX_FILE_SIZE,
    WorkspaceConflictError,
    WorkspacePathError,
    WorkspaceService,
)

DEFAULT_LOCAL_ORIGINS = [
    "http://127.0.0.1:8969",
    "http://localhost:8969",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


def local_user_name() -> str:
    try:
        import pwd

        full_name = pwd.getpwuid(os.getuid()).pw_gecos.split(",", 1)[0].strip()
        if full_name:
            return full_name.split()[0]
    except (ImportError, KeyError, OSError):
        pass
    return getpass.getuser().replace(".", " ").replace("_", " ").title()


def create_app(
    *,
    store_path: Path | None = None,
    api_key: str | None = None,
    allowed_origins: list[str] | None = None,
    allowed_hosts: list[str] | None = None,
) -> FastAPI:
    store = AgentStore(store_path)
    service = AgentService(store)
    skills_service = SkillsService()
    integrations_service = IntegrationsService()
    settings_service = SettingsService()
    account_service = AccountService(integrations=integrations_service)
    models_service = ModelsService()
    datasets_service = DatasetsService()
    tools_service = ToolsService()
    pty_manager = PtyManager()
    public_base = (
        os.environ.get("FASTFOLD_SERVER_URL")
        or os.environ.get("FASTFOLD_AGENT_URL")
        or "http://127.0.0.1:8787"
    ).rstrip("/")
    mcp_service = McpService(store, public_base_url=public_base)
    backend_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(store.path.resolve())))

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await pty_manager.shutdown()
        await service.shutdown()

    app = FastAPI(
        title="Sandwalk",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.agent_service = service

    def session_workspace(session_id: str) -> WorkspaceService:
        session = store.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        try:
            session = service.ensure_workspace(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        if not session.workspace_path:
            raise HTTPException(status_code=409, detail="Session has no workspace.")
        try:
            return WorkspaceService(Path(session.workspace_path))
        except WorkspacePathError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    def _workspace_http_error(exc: Exception) -> HTTPException:
        if isinstance(exc, FileNotFoundError):
            return HTTPException(status_code=404, detail="Workspace path not found.")
        if isinstance(exc, FileExistsError):
            return HTTPException(status_code=409, detail="Workspace target already exists.")
        if isinstance(exc, (IsADirectoryError, NotADirectoryError, WorkspacePathError)):
            return HTTPException(status_code=400, detail=str(exc))
        return HTTPException(status_code=500, detail="Workspace operation failed.")

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts or ["127.0.0.1", "localhost", "testserver"],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or DEFAULT_LOCAL_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type", "last-event-id"],
    )

    if api_key:

        @app.middleware("http")
        async def require_api_key(request: Request, call_next):
            if request.url.path.startswith("/v1/"):
                authorization = request.headers.get("authorization", "")
                scheme, _, candidate = authorization.partition(" ")
                valid = (
                    scheme.lower() == "bearer"
                    and bool(candidate)
                    and secrets.compare_digest(candidate, api_key)
                )
                if not valid:
                    from fastapi.responses import JSONResponse

                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Missing or invalid backend API key."},
                    )
            return await call_next(request)

    @app.get("/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            version=__version__,
            backend_id=backend_id,
            user_name=local_user_name(),
            capabilities=Capabilities(
                local_filesystem=True,
                skills=True,
                integrations=True,
                mcp=True,
                terminal=True,
            ),
        )

    @app.get("/v1/status", response_model=ServerStatusReport)
    async def server_status() -> ServerStatusReport:
        from agent_server.status_service import get_status_report

        return await asyncio.to_thread(
            lambda: get_status_report(version=__version__)
        )

    @app.post("/v1/server/stop", response_model=ServerLifecycleResult)
    async def stop_server() -> ServerLifecycleResult:
        from agent_server.status_service import schedule_stop

        return schedule_stop()

    @app.post("/v1/server/restart", response_model=ServerLifecycleResult)
    async def restart_server() -> ServerLifecycleResult:
        from agent_server.status_service import schedule_restart

        return schedule_restart()

    @app.post("/v1/storage/cache/clear", response_model=ServerCacheInfo)
    async def clear_runtime_cache() -> ServerCacheInfo:
        from agent_server.status_service import clear_cache

        return await asyncio.to_thread(clear_cache)

    @app.get("/v1/doctor", response_model=DoctorReport)
    async def doctor() -> DoctorReport:
        from agent.doctor import to_report

        payload = await asyncio.to_thread(to_report)
        return DoctorReport.model_validate(payload)

    async def _build_diagnostics_response(
        ui_diagnostics: dict | None = None,
    ) -> Response:
        from agent.diagnostics import build_diagnostics_zip

        data, filename = await asyncio.to_thread(
            build_diagnostics_zip,
            version=__version__,
            ui_diagnostics=ui_diagnostics,
        )
        return Response(
            content=data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/v1/doctor/diagnostics")
    async def download_diagnostics() -> Response:
        return await _build_diagnostics_response()

    @app.post("/v1/doctor/diagnostics")
    async def download_diagnostics_with_ui(
        payload: DoctorDiagnosticsRequest | None = None,
    ) -> Response:
        ui = payload.ui_diagnostics if payload else None
        return await _build_diagnostics_response(ui)

    @app.get("/v1/storage", response_model=StorageReport)
    async def get_storage() -> StorageReport:
        from agent_server.storage_service import StorageService

        return await asyncio.to_thread(StorageService().get_report)

    @app.get("/v1/environment", response_model=EnvironmentReport)
    async def get_environment() -> EnvironmentReport:
        from agent_server.environment_service import EnvironmentService

        return await asyncio.to_thread(EnvironmentService().get_report)

    @app.post(
        "/v1/environment/packages/install",
        response_model=EnvironmentPackageMutationResult,
    )
    async def install_environment_package(
        payload: EnvironmentPackageRequest,
    ) -> EnvironmentPackageMutationResult:
        from agent_server.environment_service import EnvironmentError, EnvironmentService

        try:
            return await asyncio.to_thread(
                lambda: EnvironmentService().install(
                    payload.name,
                    allow_unlisted=payload.allow_unlisted,
                )
            )
        except EnvironmentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/v1/environment/packages/uninstall",
        response_model=EnvironmentPackageMutationResult,
    )
    async def uninstall_environment_package(
        payload: EnvironmentPackageRequest,
    ) -> EnvironmentPackageMutationResult:
        from agent_server.environment_service import EnvironmentError, EnvironmentService

        try:
            return await asyncio.to_thread(EnvironmentService().uninstall, payload.name)
        except EnvironmentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/mcp-servers", response_model=McpServerList)
    async def list_mcp_servers() -> McpServerList:
        def _list() -> list[McpServer]:
            return [enrich_mcp_server(server) for server in store.list_mcp_servers()]

        return McpServerList(data=await asyncio.to_thread(_list))

    @app.get("/v1/mcp-servers/catalog", response_model=McpCatalogList)
    async def list_mcp_catalog() -> McpCatalogList:
        rows = await asyncio.to_thread(mcp_service.catalog_statuses)
        return McpCatalogList(
            data=[McpCatalogEntryStatus.model_validate(row) for row in rows]
        )

    @app.post(
        "/v1/mcp-servers/catalog/{catalog_id}/connect",
        response_model=ConnectMcpCatalogResponse,
    )
    async def connect_mcp_catalog(
        catalog_id: str,
        payload: ConnectMcpCatalogRequest,
    ) -> ConnectMcpCatalogResponse:
        try:
            if payload.method == "oauth":
                result = await asyncio.to_thread(mcp_service.start_oauth, catalog_id)
                return ConnectMcpCatalogResponse(
                    ok=True,
                    authorize_url=result.get("authorizeUrl"),
                    state=result.get("state"),
                    redirect_uri=result.get("redirectUri"),
                    catalog_id=result.get("catalogId") or catalog_id,
                    message="Open authorizeUrl in a browser to finish OAuth",
                )
            if not payload.api_key:
                raise HTTPException(status_code=400, detail="apiKey is required for API key connect")
            result = await asyncio.to_thread(
                mcp_service.connect_with_api_key,
                catalog_id,
                payload.api_key,
            )
            return ConnectMcpCatalogResponse(
                ok=bool(result.get("ok")),
                catalog_id=catalog_id,
                server_id=result.get("serverId"),
                enabled=result.get("enabled"),
                tool_count=result.get("toolCount"),
                message=result.get("message"),
                tools=list(result.get("tools") or []),
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown MCP catalog entry") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.delete(
        "/v1/mcp-servers/catalog/{catalog_id}/connect",
        response_model=ConnectMcpCatalogResponse,
    )
    async def disconnect_mcp_catalog(catalog_id: str) -> ConnectMcpCatalogResponse:
        try:
            result = await asyncio.to_thread(mcp_service.disconnect, catalog_id)
            return ConnectMcpCatalogResponse(
                ok=True,
                catalog_id=catalog_id,
                enabled=False,
                message="Disconnected — credentials cleared and MCP disabled",
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown MCP catalog entry") from None

    @app.patch(
        "/v1/mcp-servers/catalog/{catalog_id}",
        response_model=ConnectMcpCatalogResponse,
    )
    async def update_mcp_catalog(
        catalog_id: str,
        payload: UpdateMcpCatalogRequest,
    ) -> ConnectMcpCatalogResponse:
        try:
            result = await asyncio.to_thread(
                mcp_service.set_enabled,
                catalog_id,
                payload.enabled,
            )
            return ConnectMcpCatalogResponse(
                ok=bool(result.get("ok")),
                catalog_id=catalog_id,
                server_id=result.get("serverId"),
                enabled=result.get("enabled"),
                message=(
                    "Enabled" if result.get("enabled") else "Disabled"
                ),
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown MCP catalog entry") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @app.post(
        "/v1/mcp-servers/catalog/{catalog_id}/validate",
        response_model=ValidateMcpResponse,
    )
    async def validate_mcp_catalog(catalog_id: str) -> ValidateMcpResponse:
        try:
            result = await asyncio.to_thread(mcp_service.validate, catalog_id, None)
            return ValidateMcpResponse(
                ok=bool(result.get("ok")),
                tool_count=int(result.get("toolCount") or 0),
                message=str(result.get("message") or ""),
                tools=list(result.get("tools") or []),
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown MCP catalog entry") from None

    @app.get("/v1/mcp-servers/oauth/callback")
    async def mcp_oauth_callback(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
    ) -> Response:
        if error:
            detail = error_description or error
            html = f"""<!doctype html><html><body style="font-family:system-ui;padding:2rem">
              <h2>MCP OAuth failed</h2><p>{detail}</p>
              <p>You can close this window and return to FastFold.</p>
              <script>window.opener&&window.opener.postMessage({{type:'fastfold-mcp-oauth',ok:false,error:{json.dumps(detail)}}},'*');</script>
              </body></html>"""
            return Response(content=html, media_type="text/html")
        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state")
        try:
            result = await asyncio.to_thread(
                mcp_service.complete_oauth,
                code=code,
                state=state,
            )
        except Exception as exc:  # noqa: BLE001
            html = f"""<!doctype html><html><body style="font-family:system-ui;padding:2rem">
              <h2>MCP OAuth failed</h2><p>{exc}</p>
              <script>window.opener&&window.opener.postMessage({{type:'fastfold-mcp-oauth',ok:false,error:{json.dumps(str(exc))}}},'*');</script>
              </body></html>"""
            return Response(content=html, media_type="text/html", status_code=400)

        payload = json.dumps(
            {
                "type": "fastfold-mcp-oauth",
                "ok": bool(result.get("ok")),
                "catalogId": result.get("catalogId"),
                "enabled": result.get("enabled"),
                "toolCount": result.get("toolCount"),
                "message": result.get("message"),
            }
        )
        html = f"""<!doctype html><html><body style="font-family:system-ui;padding:2rem">
          <h2>{"Connected" if result.get("ok") else "Connected with errors"}</h2>
          <p>{result.get("message") or ""}</p>
          <p>You can close this window and return to FastFold.</p>
          <script>window.opener&&window.opener.postMessage({payload},'*');setTimeout(()=>window.close(),800);</script>
          </body></html>"""
        return Response(content=html, media_type="text/html")

    @app.post("/v1/mcp-servers", response_model=McpServer, status_code=201)
    async def create_mcp_server(payload: CreateMcpServerRequest) -> McpServer:
        if payload.transport == "stdio" and not payload.command:
            raise HTTPException(status_code=400, detail="stdio MCP servers require a command.")
        if payload.transport != "stdio" and not payload.url:
            raise HTTPException(status_code=400, detail="Remote MCP servers require a URL.")

        def _create() -> McpServer:
            server = store.create_mcp_server(
                name=payload.name,
                transport=payload.transport,
                command=payload.command,
                args=payload.args,
                url=payload.url,
                enabled=payload.enabled,
                catalog_id=payload.catalog_id,
                description=payload.description,
                oauth_client_id=payload.oauth_client_id,
                oauth_server_url=payload.oauth_server_url,
                oauth_scopes=payload.oauth_scopes,
                headers_helper_command=payload.headers_helper_command,
            )
            if payload.headers is not None:
                set_custom_headers(server.id, payload.headers)
            return enrich_mcp_server(server)

        return await asyncio.to_thread(_create)

    @app.patch("/v1/mcp-servers/{server_id}", response_model=McpServer)
    async def update_mcp_server(
        server_id: str,
        payload: UpdateMcpServerRequest,
    ) -> McpServer:
        def _update() -> McpServer | None:
            changes = payload.model_dump(exclude_unset=True)
            headers = changes.pop("headers", None)
            headers_provided = "headers" in payload.model_fields_set
            server = store.update_mcp_server(server_id, **changes)
            if server is None:
                return None
            if headers_provided:
                set_custom_headers(server.id, headers)
            return enrich_mcp_server(server)

        server = await asyncio.to_thread(_update)
        if server is None:
            raise HTTPException(status_code=404, detail="MCP server not found.")
        return server

    @app.post(
        "/v1/mcp-servers/{server_id}/validate",
        response_model=ValidateMcpResponse,
    )
    async def validate_mcp_server(server_id: str) -> ValidateMcpResponse:
        try:
            result = await asyncio.to_thread(mcp_service.validate, None, server_id)
            return ValidateMcpResponse(
                ok=bool(result.get("ok")),
                tool_count=int(result.get("toolCount") or 0),
                message=str(result.get("message") or ""),
                tools=list(result.get("tools") or []),
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="MCP server not found") from None

    @app.delete("/v1/mcp-servers/{server_id}", response_model=DeleteSessionResponse)
    async def delete_mcp_server(server_id: str) -> DeleteSessionResponse:
        def _delete() -> bool:
            deleted = store.delete_mcp_server(server_id)
            if deleted:
                clear_custom_headers(server_id)
            return deleted

        if not await asyncio.to_thread(_delete):
            raise HTTPException(status_code=404, detail="MCP server not found.")
        return DeleteSessionResponse()

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
            return await asyncio.to_thread(
                integrations_service.update,
                integration_key,
                values,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Integration not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/v1/integrations/{integration_key}", response_model=IntegrationProvider)
    async def remove_integration(integration_key: str) -> IntegrationProvider:
        try:
            return await asyncio.to_thread(integrations_service.remove, integration_key)
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

    @app.get("/v1/account", response_model=AccountSummary)
    async def get_account(check_updates: bool = Query(default=False)) -> AccountSummary:
        return await asyncio.to_thread(
            account_service.get,
            version=__version__,
            check_updates=check_updates,
        )

    @app.post("/v1/account/logout", response_model=AccountSummary)
    async def logout_account() -> AccountSummary:
        return await asyncio.to_thread(account_service.logout)

    @app.get("/v1/models", response_model=AgentModelList)
    async def list_models(
        enabled_only: bool = Query(default=False),
        discover: bool = Query(default=True),
    ) -> AgentModelList:
        return await asyncio.to_thread(
            models_service.list_models,
            enabled_only=enabled_only,
            discover=discover,
        )

    @app.post("/v1/models", response_model=AgentModel, status_code=201)
    async def create_custom_model(payload: CreateAgentModelRequest) -> AgentModel:
        try:
            return await asyncio.to_thread(models_service.create_custom_model, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/v1/models/{model_id:path}", response_model=AgentModel)
    async def update_model(
        model_id: str,
        payload: UpdateAgentModelRequest,
    ) -> AgentModel:
        try:
            return await asyncio.to_thread(models_service.update_model, model_id, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/v1/models/{model_id:path}")
    async def delete_custom_model(model_id: str) -> dict[str, bool]:
        removed = await asyncio.to_thread(models_service.delete_custom_model, model_id)
        if not removed:
            raise HTTPException(
                status_code=404,
                detail=f"Custom model '{model_id}' was not found.",
            )
        return {"ok": True}

    @app.get("/v1/datasets", response_model=DatasetList)
    async def list_datasets() -> DatasetList:
        return await asyncio.to_thread(datasets_service.list_datasets)

    @app.post("/v1/datasets/{dataset_id}/install", response_model=DatasetInstallResponse)
    async def install_dataset(dataset_id: str) -> DatasetInstallResponse:
        try:
            return await asyncio.to_thread(datasets_service.install, dataset_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Unknown dataset '{dataset_id}'."
            ) from exc

    @app.get("/v1/tools", response_model=ToolList)
    async def list_tools(
        enabled_only: bool = Query(default=False),
    ) -> ToolList:
        return await asyncio.to_thread(
            tools_service.list_tools, enabled_only=enabled_only
        )

    @app.post("/v1/tools/batch", response_model=ToolBatchActionResponse)
    async def batch_tools(
        payload: ToolBatchActionRequest,
    ) -> ToolBatchActionResponse:
        return await asyncio.to_thread(
            tools_service.batch_action, payload.action, payload.ids
        )

    @app.patch("/v1/tools/{tool_id:path}", response_model=ToolSummary)
    async def update_tool(tool_id: str, payload: UpdateToolRequest) -> ToolSummary:
        try:
            return await asyncio.to_thread(tools_service.update_tool, tool_id, payload)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Unknown tool '{tool_id}'."
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/model-profiles", response_model=ModelProfileList)
    async def list_model_profiles(
        include_cloud: bool = Query(default=True),
    ) -> ModelProfileList:
        return await asyncio.to_thread(
            models_service.list_profiles,
            include_cloud=include_cloud,
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

    @app.get("/v1/projects", response_model=ProjectList)
    async def list_projects() -> ProjectList:
        return ProjectList(data=await asyncio.to_thread(store.list_projects))

    @app.post("/v1/projects", response_model=AgentProject, status_code=201)
    async def create_project(payload: CreateProjectRequest) -> AgentProject:
        try:
            return await asyncio.to_thread(
                store.create_project,
                name=payload.name,
                description=payload.description,
                agent_context=payload.agent_context,
                pinned=payload.pinned,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/projects/{project_id}", response_model=AgentProject)
    async def get_project(project_id: str) -> AgentProject:
        project = await asyncio.to_thread(store.get_project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return project

    @app.patch("/v1/projects/{project_id}", response_model=AgentProject)
    async def update_project(
        project_id: str,
        payload: UpdateProjectRequest,
    ) -> AgentProject:
        try:
            project = await asyncio.to_thread(
                store.update_project,
                project_id,
                name=payload.name,
                description=payload.description,
                update_description=payload.description is not None
                or payload.clear_description,
                agent_context=payload.agent_context,
                update_agent_context=payload.agent_context is not None
                or payload.clear_agent_context,
                pinned=payload.pinned,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return project

    @app.delete("/v1/projects/{project_id}", response_model=DeleteProjectResponse)
    async def delete_project(project_id: str) -> DeleteProjectResponse:
        deleted = await asyncio.to_thread(store.delete_project, project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found.")
        return DeleteProjectResponse(deleted=True)

    @app.get("/v1/sessions", response_model=SessionList)
    async def list_sessions(
        project_id: str | None = Query(default=None, alias="projectId"),
    ) -> SessionList:
        return SessionList(
            data=await asyncio.to_thread(store.list_sessions, project_id=project_id)
        )

    @app.get("/v1/sessions/search", response_model=SessionList)
    async def search_sessions(
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> SessionList:
        return SessionList(
            data=await asyncio.to_thread(store.search_sessions, q, limit=limit)
        )

    @app.post("/v1/sessions", response_model=AgentSession, status_code=201)
    async def create_session(payload: CreateSessionRequest) -> AgentSession:
        try:
            return await asyncio.to_thread(
                service.create_session,
                title=payload.title,
                workspace_path=payload.workspace_path,
                project_id=payload.project_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/sessions/{session_id}", response_model=AgentSession)
    async def get_session(session_id: str) -> AgentSession:
        session = await asyncio.to_thread(store.get_session, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return session

    @app.patch("/v1/sessions/{session_id}", response_model=AgentSession)
    async def update_session(
        session_id: str,
        payload: UpdateSessionRequest,
    ) -> AgentSession:
        update_label = payload.organize_label is not None or payload.clear_organize_label
        update_project = payload.project_id is not None or payload.clear_project_id
        try:
            return await asyncio.to_thread(
                service.update_session,
                session_id=session_id,
                title=payload.title,
                organize_label=payload.organize_label,
                update_organize_label=update_label,
                project_id=None if payload.clear_project_id else payload.project_id,
                update_project_id=update_project,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/sessions/{session_id}/title/auto", response_model=AgentSession)
    async def auto_title_session(
        session_id: str,
        payload: AutoTitleSessionRequest | None = None,
    ) -> AgentSession:
        body = payload or AutoTitleSessionRequest()
        try:
            return await asyncio.to_thread(
                service.auto_title_session,
                session_id,
                force=body.force,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.delete("/v1/sessions/{session_id}", response_model=DeleteSessionResponse)
    async def delete_session(session_id: str) -> DeleteSessionResponse:
        if not await service.delete_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found.")
        return DeleteSessionResponse()

    @app.get("/v1/sessions/{session_id}/messages", response_model=MessageList)
    async def list_messages(session_id: str) -> MessageList:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return MessageList(
            data=await asyncio.to_thread(store.list_messages, session_id),
            feedback=await asyncio.to_thread(store.get_session_feedback, session_id),
        )

    @app.post(
        "/v1/sessions/{session_id}/messages/{message_id}/feedback",
        response_model=MessageFeedbackResponse,
    )
    async def update_message_feedback(
        session_id: str,
        message_id: str,
        payload: MessageFeedbackRequest,
    ) -> MessageFeedbackResponse:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        saved = await asyncio.to_thread(
            store.set_message_feedback,
            message_id,
            payload.reaction,
        )
        if not saved:
            raise HTTPException(status_code=404, detail="Message not found.")
        return MessageFeedbackResponse(
            message_id=message_id,
            reaction=payload.reaction,
        )

    @app.post(
        "/v1/sessions/{session_id}/messages",
        response_model=StartRunResponse,
        status_code=202,
    )
    async def send_message(
        session_id: str,
        payload: SendMessageRequest,
    ) -> StartRunResponse:
        try:
            return service.submit_message(session_id=session_id, content=payload.content)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except SessionBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/v1/sessions/{session_id}/interrupt",
        response_model=InterruptRunResponse,
    )
    async def interrupt_session(session_id: str) -> InterruptRunResponse:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return InterruptRunResponse(interrupted=service.interrupt(session_id))

    @app.get(
        "/v1/sessions/{session_id}/files",
        response_model=WorkspaceFileList,
    )
    async def list_workspace_files(
        session_id: str,
        path: str = Query(default=""),
        recursive: bool = Query(default=True),
    ) -> WorkspaceFileList:
        workspace = session_workspace(session_id)
        try:
            data = await asyncio.to_thread(workspace.list, path, recursive=recursive)
            return WorkspaceFileList(data=data)
        except Exception as exc:
            raise _workspace_http_error(exc) from exc

    @app.get(
        "/v1/sessions/{session_id}/files/content",
        response_model=WorkspaceFileContent,
    )
    async def read_workspace_file(
        session_id: str,
        path: str = Query(min_length=1),
    ) -> WorkspaceFileContent:
        workspace = session_workspace(session_id)
        try:
            return await asyncio.to_thread(workspace.read, path)
        except Exception as exc:
            raise _workspace_http_error(exc) from exc

    @app.put(
        "/v1/sessions/{session_id}/files/content",
        response_model=WorkspaceFileContent,
    )
    async def write_workspace_file(
        session_id: str,
        payload: WriteWorkspaceFileRequest,
    ):
        workspace = session_workspace(session_id)
        try:
            return await asyncio.to_thread(
                workspace.write,
                payload.path,
                content=payload.content,
                encoding=payload.encoding,
                base_version=payload.base_version,
            )
        except WorkspaceConflictError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "detail": str(exc),
                    "current": exc.current.model_dump(mode="json", by_alias=True),
                },
            )
        except Exception as exc:
            raise _workspace_http_error(exc) from exc

    @app.get("/v1/sessions/{session_id}/files/download")
    async def download_workspace_file(
        session_id: str,
        path: str = Query(min_length=1),
    ) -> FileResponse:
        workspace = session_workspace(session_id)
        try:
            file_path = workspace.resolve(path, must_exist=True)
            if not file_path.is_file():
                raise IsADirectoryError(path)
            return FileResponse(file_path, filename=file_path.name)
        except Exception as exc:
            raise _workspace_http_error(exc) from exc

    @app.post(
        "/v1/sessions/{session_id}/files/upload",
        response_model=WorkspaceFileContent,
    )
    async def upload_workspace_file(
        session_id: str,
        file: UploadFile = File(...),
        relative_dir: str = Form(default="uploads"),
    ) -> WorkspaceFileContent:
        workspace = session_workspace(session_id)
        data = await file.read(MAX_FILE_SIZE + 1)
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds the 40MB limit.")
        relative_path = str(Path(relative_dir) / (file.filename or "upload.bin"))
        try:
            return await asyncio.to_thread(workspace.upload, relative_path, data)
        except Exception as exc:
            raise _workspace_http_error(exc) from exc

    @app.post(
        "/v1/sessions/{session_id}/files/folders",
        response_model=WorkspaceMutationResponse,
    )
    async def create_workspace_folder(
        session_id: str,
        payload: CreateWorkspaceFolderRequest,
    ) -> WorkspaceMutationResponse:
        workspace = session_workspace(session_id)
        try:
            path = await asyncio.to_thread(workspace.create_folder, payload.path)
            return WorkspaceMutationResponse(path=path)
        except Exception as exc:
            raise _workspace_http_error(exc) from exc

    @app.post(
        "/v1/sessions/{session_id}/files/move",
        response_model=WorkspaceMutationResponse,
    )
    async def move_workspace_file(
        session_id: str,
        payload: MoveWorkspaceFileRequest,
    ) -> WorkspaceMutationResponse:
        workspace = session_workspace(session_id)
        try:
            path = await asyncio.to_thread(
                workspace.move,
                payload.source_path,
                payload.target_path,
            )
            return WorkspaceMutationResponse(path=path)
        except Exception as exc:
            raise _workspace_http_error(exc) from exc

    @app.delete(
        "/v1/sessions/{session_id}/files",
        response_model=WorkspaceMutationResponse,
    )
    async def delete_workspace_file(
        session_id: str,
        path: str = Query(min_length=1),
        recursive: bool = Query(default=False),
    ) -> WorkspaceMutationResponse:
        workspace = session_workspace(session_id)
        try:
            await asyncio.to_thread(workspace.delete, path, recursive=recursive)
            return WorkspaceMutationResponse(path=path)
        except Exception as exc:
            raise _workspace_http_error(exc) from exc

    @app.get("/v1/sessions/{session_id}/pty", response_model=PtySessionList)
    async def list_pty_sessions(session_id: str) -> PtySessionList:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return PtySessionList(
            data=[
                PtySessionInfo(**info.to_dict())
                for info in pty_manager.list(session_id)
            ]
        )

    @app.post(
        "/v1/sessions/{session_id}/pty",
        response_model=PtySessionInfo,
        status_code=201,
    )
    async def create_pty_session(
        session_id: str,
        payload: CreatePtyRequest | None = None,
    ) -> PtySessionInfo:
        session = service.ensure_workspace(session_id)
        if not session.workspace_path:
            raise HTTPException(status_code=409, detail="Session has no workspace.")
        body = payload or CreatePtyRequest()
        info = await pty_manager.create(
            session_id=session_id,
            cwd=session.workspace_path,
            title=body.title,
            cols=body.cols,
            rows=body.rows,
        )
        return PtySessionInfo(**info.to_dict())

    @app.put(
        "/v1/sessions/{session_id}/pty/{pty_id}",
        response_model=PtySessionInfo,
    )
    async def update_pty_session(
        session_id: str,
        pty_id: str,
        payload: UpdatePtyRequest,
    ) -> PtySessionInfo:
        info = pty_manager.get(session_id, pty_id)
        if info is None:
            raise HTTPException(status_code=404, detail="Terminal not found.")
        if payload.title is not None:
            updated = await pty_manager.update_title(session_id, pty_id, payload.title)
            if updated is None:
                raise HTTPException(status_code=404, detail="Terminal not found.")
            info = updated
        if payload.cols is not None and payload.rows is not None:
            updated = await pty_manager.resize(
                session_id,
                pty_id,
                cols=payload.cols,
                rows=payload.rows,
            )
            if updated is None:
                raise HTTPException(status_code=404, detail="Terminal not found.")
            info = updated
        return PtySessionInfo(**info.to_dict())

    @app.delete("/v1/sessions/{session_id}/pty/{pty_id}", status_code=204)
    async def delete_pty_session(session_id: str, pty_id: str) -> None:
        deleted = await pty_manager.remove(session_id, pty_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Terminal not found.")

    @app.websocket("/v1/sessions/{session_id}/pty/{pty_id}/connect")
    async def connect_pty_session(
        websocket: WebSocket,
        session_id: str,
        pty_id: str,
    ) -> None:
        if api_key:
            authorization = websocket.headers.get("authorization", "")
            scheme, _, candidate = authorization.partition(" ")
            query_token = websocket.query_params.get("token", "")
            valid = (
                scheme.lower() == "bearer"
                and bool(candidate)
                and secrets.compare_digest(candidate, api_key)
            ) or (
                bool(query_token) and secrets.compare_digest(query_token, api_key)
            )
            if not valid:
                await websocket.close(code=4401)
                return
        if await asyncio.to_thread(store.get_session, session_id) is None:
            await websocket.close(code=4404)
            return
        if pty_manager.get(session_id, pty_id) is None:
            await websocket.close(code=4404)
            return
        await websocket.accept()
        await pty_manager.attach(session_id, pty_id, websocket)

    @app.get("/v1/sessions/{session_id}/events")
    async def stream_events(
        request: Request,
        session_id: str,
        after_sequence: int = Query(default=0, ge=0),
    ) -> StreamingResponse:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")

        header_sequence = request.headers.get("last-event-id", "").strip()
        cursor = after_sequence
        if header_sequence.isdigit():
            cursor = max(cursor, int(header_sequence))

        async def event_source() -> AsyncIterator[str]:
            nonlocal cursor
            heartbeat_ticks = 0
            while not await request.is_disconnected():
                events = await asyncio.to_thread(
                    store.list_events,
                    session_id,
                    after_sequence=cursor,
                )
                if events:
                    heartbeat_ticks = 0
                    for event in events:
                        cursor = event.sequence
                        data = json.dumps(
                            event.model_dump(mode="json", by_alias=True),
                            separators=(",", ":"),
                        )
                        yield f"id: {event.sequence}\nevent: {event.type}\ndata: {data}\n\n"
                else:
                    heartbeat_ticks += 1
                    if heartbeat_ticks >= 15:
                        heartbeat_ticks = 0
                        yield ": heartbeat\n\n"
                    await asyncio.sleep(1)

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app
