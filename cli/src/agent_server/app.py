"""FastAPI transport for the FastFold agent application service."""

from __future__ import annotations

import asyncio
import contextlib
import os
import secrets
import threading
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
from agent_server.connectors.service import ConnectorService
from agent_server.datasets_service import DatasetsService
from agent_server.integrations_service import IntegrationsService
from agent_server.library import LibraryService
from agent_server.mcp_service import McpService
from agent_server.models_service import ModelsService
from agent_server.pty_manager import PtyManager
from agent_server.routes import register_all_routes
from agent_server.routes.auth import register_auth_middleware
from agent_server.sandbox_events import sandbox_event_bus
from agent_server.sandbox_settings_service import SandboxSettingsService
from agent_server.service import AgentService
from agent_server.session_event_bus import session_event_bus
from agent_server.settings_service import SettingsService
from agent_server.sites_service import SitesService
from agent_server.skills_service import SkillsService
from agent_server.specialists_service import SpecialistsService
from agent_server.store import AgentStore
from agent_server.tools_service import ToolsService

# Cheap fingerprint poll. Full online backups only run when the live DB
# changed and at least BACKUP_MIN_INTERVAL_SECONDS have passed — so idle
# servers stay quiet, and heavy write bursts coalesce instead of copying
# the whole file every couple of minutes.
BACKUP_POLL_SECONDS = 60.0
BACKUP_MIN_INTERVAL_SECONDS = 300.0


async def _keep_backup_fresh(store: AgentStore) -> None:
    """Snapshot the database when it changes, coalesced to a few minutes."""
    import logging
    import time

    from agent_server.store_heal import database_fingerprint, refresh_healthy_backup

    logger = logging.getLogger("agent_server")
    last_backup_at = 0.0
    last_fp = database_fingerprint(store.path)
    while True:
        try:
            await asyncio.sleep(BACKUP_POLL_SECONDS)
            fp = database_fingerprint(store.path)
            if fp == last_fp:
                continue
            now = time.monotonic()
            if now - last_backup_at < BACKUP_MIN_INTERVAL_SECONDS:
                continue
            # Online backup API — safe against a live WAL database.
            wrote = await asyncio.to_thread(
                refresh_healthy_backup, store.path, force=False
            )
            if wrote is True:
                last_backup_at = now
                last_fp = database_fingerprint(store.path)
            elif wrote is False:
                last_fp = fp
            # wrote is None → failed; keep last_fp so the next eligible poll retries.
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Periodic DB backup refresh failed", exc_info=True)


DEFAULT_LOCAL_ORIGINS = [
    "http://127.0.0.1:8969",
    "http://localhost:8969",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    # Tauri desktop (dev Vite + packaged custom protocol)
    "http://127.0.0.1:1420",
    "http://localhost:1420",
    "tauri://localhost",
    "https://tauri.localhost",
    "http://tauri.localhost",
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
    library_service = LibraryService(store, service)
    connector_service = ConnectorService(store, service)
    integrations_service = IntegrationsService()
    pty_manager = PtyManager()
    public_base = (
        os.environ.get("FASTFOLD_SERVER_URL")
        or os.environ.get("FASTFOLD_AGENT_URL")
        or "http://127.0.0.1:8787"
    ).rstrip("/")
    mcp_service = McpService(store, public_base_url=public_base)
    backend_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(store.path.resolve())))
    shutdown_event = threading.Event()

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
        shutdown_event.clear()
        # Re-sync on startup in case config changed while the process was idle,
        # or tests construct the app without going through run_server().
        try:
            from agent.config import sync_process_env_from_config

            sync_process_env_from_config()
        except Exception:
            pass
        sandbox_event_bus.bind_loop(asyncio.get_running_loop())
        session_event_bus.bind_loop(asyncio.get_running_loop())
        # Inbound connectors are best-effort: a Slack outage must not stop the
        # server from booting.
        try:
            await connector_service.start()
        except Exception:
            import logging

            logging.getLogger("agent_server").exception("Connector startup failed")
        backup_task = asyncio.create_task(_keep_backup_fresh(store))
        yield
        shutdown_event.set()
        from agent_server.store.event_notifier import EVENT_NOTIFIER

        EVENT_NOTIFIER.wake_all()
        backup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await backup_task
        await connector_service.stop()
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
    app.state.shutdown_event = shutdown_event

    deps = AppDeps(
        app=app,
        store=store,
        service=service,
        skills_service=SkillsService(),
        specialists_service=SpecialistsService(store),
        integrations_service=integrations_service,
        settings_service=SettingsService(),
        sites_service=SitesService(store, public_base_url=public_base),
        sandbox_settings_service=SandboxSettingsService(),
        account_service=AccountService(integrations=integrations_service),
        models_service=ModelsService(),
        datasets_service=DatasetsService(),
        tools_service=ToolsService(),
        pty_manager=pty_manager,
        mcp_service=mcp_service,
        library_service=library_service,
        connector_service=connector_service,
        backend_id=backend_id,
        cli_api_key=api_key,
    )
    # Headless CLI (`sandwalk eval`) and tests can reuse the same wiring.
    app.state.deps = deps

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
        # Browser/Vite localhost, plus packaged Tauri origins (tauri:// / tauri.localhost).
        allow_origin_regex=(
            r"(https?://(localhost|127\.0\.0\.1|tauri\.localhost)(:\d+)?)"
            r"|(tauri://localhost)"
        ),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "authorization",
            "content-type",
            "last-event-id",
            "x-api-key",
            "cookie",
            "x-sandwalk-client",
        ],
    )

    register_all_routes(app, deps)

    # Optional production UI (Vite dist/). Registered last so /v1/* stays first.
    from agent_server.static_ui import mount_static_ui, resolve_ui_dist

    ui_dist = resolve_ui_dist()
    app.state.ui_dist = ui_dist
    if ui_dist is not None:
        mount_static_ui(app, ui_dist)

    return app
