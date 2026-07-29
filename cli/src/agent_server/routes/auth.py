"""Auth middleware and `/v1/auth/*` routes."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from agent_server.app_deps import AppDeps
from agent_server.auth_settings import (
    AUTH_EXEMPT_PATHS,
    SESSION_COOKIE,
    AuthSettingsError,
    create_session_token,
    ensure_api_key,
    key_matches,
    load_settings,
    request_is_authenticated,
    save_settings,
    validate_api_key,
)
from agent_server.models import (
    AuthLoginRequest,
    AuthSettingsResponse,
    AuthStatusResponse,
    UpdateAuthSettingsRequest,
)


def _is_site_preview_path(path: str) -> bool:
    parts = path.split("/")
    return (
        len(parts) >= 7
        and parts[1:3] == ["v1", "sites"]
        and bool(parts[3])
        and parts[4] == "preview"
        and bool(parts[5])
    )


def register_auth_middleware(app: FastAPI, deps: AppDeps) -> None:
    @app.middleware("http")
    async def require_api_key(request: Request, call_next):
        path = request.url.path
        key = deps.current_api_key()
        if (
            key
            and path.startswith("/v1/")
            and path not in AUTH_EXEMPT_PATHS
            and not _is_site_preview_path(path)
        ):
            ok = request_is_authenticated(
                headers=request.headers,
                cookies=request.cookies,
                api_key=key,
                secret_key=deps.current_secret(),
                # EventSource cannot set headers; SSE consumers pass ?token=
                # (same pattern as the sandbox/PTY WebSockets).
                query_token=request.query_params.get("token"),
            )
            if not ok:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid backend API key."},
                )
        return await call_next(request)


def register_auth_routes(app: FastAPI, deps: AppDeps) -> None:
    @app.get("/v1/auth/status", response_model=AuthStatusResponse)
    async def auth_status(request: Request) -> AuthStatusResponse:
        settings = load_settings()
        app.state.auth_settings = settings
        key = deps.current_api_key()
        authenticated = False
        if not settings.auth_enabled:
            authenticated = True
        elif key:
            authenticated = request_is_authenticated(
                headers=request.headers,
                cookies=request.cookies,
                api_key=key,
                secret_key=settings.secret_key,
            )
        return AuthStatusResponse(
            auth_enabled=bool(settings.auth_enabled),
            api_key_configured=settings.api_key_configured,
            authenticated=authenticated,
        )

    @app.post("/v1/auth/login")
    async def auth_login(payload: AuthLoginRequest) -> JSONResponse:
        settings = load_settings()
        app.state.auth_settings = settings
        expected = settings.api_key
        if not expected or not key_matches(payload.api_key.strip(), expected):
            raise HTTPException(status_code=401, detail="Invalid API key.")
        token, max_age = create_session_token(
            secret_key=settings.secret_key,
            remember=payload.remember,
        )
        response = JSONResponse(content={"ok": True, "authEnabled": settings.auth_enabled})
        response.set_cookie(
            key=SESSION_COOKIE,
            value=token,
            max_age=max_age,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return response

    @app.post("/v1/auth/logout")
    async def auth_logout() -> JSONResponse:
        response = JSONResponse(content={"ok": True})
        response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
        return response

    @app.get("/v1/auth/settings", response_model=AuthSettingsResponse)
    async def get_auth_settings(request: Request) -> AuthSettingsResponse:
        settings = load_settings()
        app.state.auth_settings = settings
        key = deps.current_api_key()
        if key:
            ok = request_is_authenticated(
                headers=request.headers,
                cookies=request.cookies,
                api_key=key,
                secret_key=settings.secret_key,
            )
            if not ok:
                raise HTTPException(status_code=401, detail="Missing or invalid backend API key.")
        return AuthSettingsResponse(
            auth_enabled=settings.auth_enabled,
            api_key=settings.api_key,
            api_key_configured=settings.api_key_configured,
        )

    @app.patch("/v1/auth/settings", response_model=AuthSettingsResponse)
    async def patch_auth_settings(
        request: Request,
        payload: UpdateAuthSettingsRequest,
    ) -> AuthSettingsResponse:
        settings = load_settings()
        key = deps.current_api_key()
        if key:
            ok = request_is_authenticated(
                headers=request.headers,
                cookies=request.cookies,
                api_key=key,
                secret_key=settings.secret_key,
            )
            if not ok:
                raise HTTPException(status_code=401, detail="Missing or invalid backend API key.")
        if payload.api_key is not None:
            try:
                settings.api_key = validate_api_key(payload.api_key)
            except AuthSettingsError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        if payload.auth_enabled is not None:
            settings.auth_enabled = bool(payload.auth_enabled)
            if settings.auth_enabled and not settings.api_key:
                settings = ensure_api_key(settings)
        if not settings.secret_key:
            settings = ensure_api_key(settings)
        save_settings(settings)
        deps.reload_auth_state()
        settings = load_settings()
        return AuthSettingsResponse(
            auth_enabled=settings.auth_enabled,
            api_key=settings.api_key,
            api_key_configured=settings.api_key_configured,
        )
