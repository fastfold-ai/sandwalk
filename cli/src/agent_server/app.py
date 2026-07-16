"""FastAPI transport for the FastFold agent application service."""

from __future__ import annotations

import asyncio
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from _version import __version__
from agent_server.account_service import AccountService
from agent_server.app_deps import AppDeps
from agent_server.auth_settings import load_settings, resolve_effective_api_key
from agent_server.datasets_service import DatasetsService
from agent_server.integrations_service import IntegrationsService
from agent_server.mcp_service import McpService
from agent_server.models_service import ModelsService
from agent_server.pty_manager import PtyManager
from agent_server.routes import register_all_routes
from agent_server.routes.auth import register_auth_middleware
from agent_server.sandbox_events import sandbox_event_bus
from agent_server.sandbox_settings_service import SandboxSettingsService
from agent_server.service import AgentService
from agent_server.settings_service import SettingsService
from agent_server.skills_service import SkillsService
from agent_server.specialists_service import SpecialistsService
from agent_server.store import AgentStore
from agent_server.tools_service import ToolsService

DEFAULT_LOCAL_ORIGINS = [
    "http://127.0.0.1:8969",
    "http://localhost:8969",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


def create_app(
    *,
    store_path: Path | None = None,
    api_key: str | None = None,
    allowed_origins: list[str] | None = None,
    allowed_hosts: list[str] | None = None,
) -> FastAPI:
    store = AgentStore(store_path, exclusive=True)
    if store.last_heal_note:
        import logging

        logging.getLogger("agent_server").warning("%s", store.last_heal_note)
    service = AgentService(store)
    integrations_service = IntegrationsService()
    pty_manager = PtyManager()
    public_base = (
        os.environ.get("FASTFOLD_SERVER_URL")
        or os.environ.get("FASTFOLD_AGENT_URL")
        or "http://127.0.0.1:8787"
    ).rstrip("/")
    mcp_service = McpService(store, public_base_url=public_base)
    backend_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(store.path.resolve())))

    # Persisted auth settings; CLI/env --api-key overrides the effective key.
    auth_settings = load_settings(create_if_missing=False)
    if not auth_settings.secret_key:
        auth_settings.secret_key = secrets.token_urlsafe(32)
    effective_api_key = resolve_effective_api_key(
        cli_api_key=api_key,
        settings=auth_settings,
    )
    # When caller passes an explicit key (tests / --api-key), always enforce it.
    enforce_auth = bool((api_key or "").strip()) or bool(
        auth_settings.auth_enabled and effective_api_key
    )
    runtime_api_key = effective_api_key if enforce_auth else None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Re-sync on startup in case config changed while the process was idle,
        # or tests construct the app without going through run_server().
        try:
            from agent.config import sync_process_env_from_config

            sync_process_env_from_config()
        except Exception:
            pass
        sandbox_event_bus.bind_loop(asyncio.get_running_loop())
        yield
        await pty_manager.shutdown()
        await service.shutdown()
        store.close()

    app = FastAPI(
        title="sandwalk",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.agent_service = service
    app.state.auth_settings = auth_settings
    app.state.runtime_api_key = runtime_api_key

    deps = AppDeps(
        app=app,
        store=store,
        service=service,
        skills_service=SkillsService(),
        specialists_service=SpecialistsService(store),
        integrations_service=integrations_service,
        settings_service=SettingsService(),
        sandbox_settings_service=SandboxSettingsService(),
        account_service=AccountService(integrations=integrations_service),
        models_service=ModelsService(),
        datasets_service=DatasetsService(),
        tools_service=ToolsService(),
        pty_manager=pty_manager,
        mcp_service=mcp_service,
        backend_id=backend_id,
        cli_api_key=api_key,
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts or ["127.0.0.1", "localhost", "testserver"],
    )

    register_auth_middleware(app, deps)

    # CORS must be outermost so early 401s from require_api_key still get
    # Access-Control-* headers (otherwise the browser surfaces "Failed to fetch").
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or DEFAULT_LOCAL_ORIGINS,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type", "last-event-id", "x-api-key", "cookie"],
    )

    register_all_routes(app, deps)

    # Optional production UI (Vite dist/). Registered last so /v1/* stays first.
    from agent_server.static_ui import mount_static_ui, resolve_ui_dist

    ui_dist = resolve_ui_dist()
    if ui_dist is not None:
        mount_static_ui(app, ui_dist)

    return app
