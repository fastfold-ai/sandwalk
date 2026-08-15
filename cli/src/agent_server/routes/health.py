"""Health, status, doctor, storage, and environment routes."""

from __future__ import annotations

import asyncio
import getpass
import os
import platform

from fastapi import FastAPI, HTTPException, Response

from _version import __version__
from agent_server.app_deps import AppDeps
from agent_server.models import (
    Capabilities,
    DiscoverResponse,
    DoctorDiagnosticsRequest,
    DoctorReport,
    EnvironmentPackageMutationResult,
    EnvironmentPackageRequest,
    EnvironmentReport,
    HealthResponse,
    ServerCacheInfo,
    ServerLifecycleResult,
    ServerStatusReport,
    StorageReport,
)
from agent_server.observability import OBSERVABILITY, thread_pool_snapshot


def local_user_name() -> str:
    try:
        import pwd

        full_name = pwd.getpwuid(os.getuid()).pw_gecos.split(",", 1)[0].strip()
        if full_name:
            return full_name.split()[0]
    except (ImportError, KeyError, OSError):
        pass
    return getpass.getuser().replace(".", " ").replace("_", " ").title()


def register_health_routes(app: FastAPI, deps: AppDeps) -> None:
    @app.get("/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            version=__version__,
            backend_id=deps.backend_id,
            user_name=local_user_name(),
            capabilities=Capabilities(
                local_filesystem=True,
                skills=True,
                integrations=True,
                mcp=True,
                terminal=True,
            ),
        )

    @app.get("/v1/debug/health")
    async def debug_health() -> dict[str, object]:
        """Concurrency + connection counters for debugging thread-pool pressure.

        Reading this endpoint costs nothing (pure in-memory counters). Compare
        `thread_pool.active_threads` vs `thread_pool.max_workers` to spot
        saturation. If `sse_streams_open` keeps climbing while chats stay
        static, a stream is leaking.
        """
        active_runs = 0
        try:
            active_runs = len(deps.service._active_runs)  # noqa: SLF001
        except Exception:
            active_runs = -1
        return {
            "connections": OBSERVABILITY.snapshot(),
            "thread_pool": thread_pool_snapshot(),
            "active_runs": active_runs,
        }

    @app.get("/v1/discover", response_model=DiscoverResponse)
    async def discover() -> DiscoverResponse:
        """Public LAN probe — service, sandwalk version, hostname, device label."""

        def _build() -> DiscoverResponse:
            from agent_server.status_service.gpu_metrics import _chip_name
            from agent_server.status_service.host_metrics import format_device_label

            return DiscoverResponse(
                # Package / CLI version so LAN scanners can identify compatible servers.
                version=__version__,
                hostname=platform.node() or "unknown",
                platform=platform.system() or "unknown",
                arch=platform.machine() or "unknown",
                device_label=format_device_label(chip_name=_chip_name()),
                auth_required=deps.current_api_key() is not None,
            )

        return await asyncio.to_thread(_build)

    @app.get("/v1/status", response_model=ServerStatusReport)
    async def server_status() -> ServerStatusReport:
        from agent_server.status_service import get_status_report

        return await asyncio.to_thread(lambda: get_status_report(version=__version__))

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
    async def doctor(scope: str = "full") -> DoctorReport:
        from agent.doctor import to_report

        normalized = str(scope or "full").strip().lower()
        if normalized not in {"full", "core"}:
            raise HTTPException(
                status_code=400,
                detail="Invalid scope. Use 'full' or 'core'.",
            )
        payload = await asyncio.to_thread(to_report, scope=normalized)
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
