"""Sign in with ChatGPT routes: start, status, logout, and the loopback callback.

OpenAI's open-source flow redirects the browser to
``http://127.0.0.1:<port>/auth/callback``. The port may vary per attempt but
the path may not, so this module runs its own small loopback HTTP server on
an ephemeral port instead of reusing the API's ``/v1`` namespace. One
listener serves one sign-in attempt, then exits.
"""

from __future__ import annotations

import asyncio
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from fastapi import FastAPI, HTTPException

from agent.config import chatgpt_auth
from agent_server.app_deps import AppDeps
from agent_server.models import ChatGPTAuthStart, ChatGPTAuthStatus
from agent_server.routes.oauth_return_page import render_oauth_return_page

# Give the user long enough to finish OpenAI's consent screen.
LISTENER_TIMEOUT_S = 10 * 60

# state -> result once the callback has run. Polled by /v1/auth/chatgpt/status.
_results: dict[str, dict[str, Any]] = {}
_results_lock = threading.Lock()


def _record(state: str, payload: dict[str, Any]) -> None:
    with _results_lock:
        _results[state] = payload


def _take_result(state: str) -> dict[str, Any] | None:
    with _results_lock:
        return _results.pop(state, None)


def _peek_result(state: str) -> dict[str, Any] | None:
    with _results_lock:
        return _results.get(state)


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key) or []
    return values[0] if values else None


class _CallbackHandler(BaseHTTPRequestHandler):
    server: _LoopbackServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - BaseHTTPRequestHandler API
        return

    def _page(self, *, status: int, ok: bool, title: str, detail: str) -> None:
        html = render_oauth_return_page(
            ok=ok,
            title=title,
            detail=detail,
            tag_label="ChatGPT plan",
        )
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != chatgpt_auth.CALLBACK_PATH:
            self._page(status=404, ok=False, title="Not found", detail="Unexpected callback path.")
            return
        query = urllib.parse.parse_qs(parsed.query)
        state = str(_first(query, "state") or "")
        expected = self.server.expected_state
        if not state or state != expected:
            self._page(
                status=400,
                ok=False,
                title="Sign-in did not match",
                detail="This callback belongs to a different sign-in attempt. Close this tab and try again in Sandwalk.",
            )
            return

        error = _first(query, "error")
        if error:
            description = str(_first(query, "error_description") or "")
            message = (
                "You did not allow Sandwalk to use your ChatGPT plan."
                if error == "access_denied"
                else (description or str(error))
            )
            _record(state, {"ok": False, "error": message})
            self._page(status=200, ok=False, title="Sign-in cancelled", detail=message)
            self.server.finished.set()
            return

        code = str(_first(query, "code") or "")
        if not code:
            _record(state, {"ok": False, "error": "OpenAI returned no authorization code."})
            self._page(status=400, ok=False, title="Sign-in failed", detail="OpenAI returned no authorization code.")
            self.server.finished.set()
            return

        try:
            creds = chatgpt_auth.complete_login(
                code=code,
                state=state,
                callback_client_id=str(_first(query, "client_id") or "") or None,
            )
        except chatgpt_auth.ChatGPTAuthError as exc:
            _record(state, {"ok": False, "error": str(exc)})
            self._page(status=400, ok=False, title=exc.title, detail=str(exc))
            self.server.finished.set()
            return
        except Exception as exc:  # noqa: BLE001
            _record(state, {"ok": False, "error": f"Unexpected error: {exc}"})
            self._page(status=500, ok=False, title="Sign-in failed", detail=str(exc))
            self.server.finished.set()
            return

        # Models were auto-hidden while disconnected; make them visible now,
        # the same way saving an API key does for other providers.
        try:
            from agent.config import Config
            from agent_server.models_service.mutate import enable_models_for_provider

            cfg = Config.load()
            if enable_models_for_provider(cfg, chatgpt_auth.PROVIDER_KEY):
                cfg.save()
        except Exception:  # noqa: BLE001 - visibility is secondary to the login itself
            pass

        _record(state, {"ok": True, "email": creds.email})
        self._page(
            status=200,
            ok=True,
            title="Connected to ChatGPT",
            detail=(
                f"Signed in as {creds.email}. You can close this tab and return to Sandwalk."
                if creds.email
                else "You can close this tab and return to Sandwalk."
            ),
        )
        self.server.finished.set()


class _LoopbackServer(HTTPServer):
    allow_reuse_address = False

    def __init__(self, expected_state: str):
        super().__init__(("127.0.0.1", 0), _CallbackHandler)
        self.expected_state = expected_state
        self.finished = threading.Event()


def _serve_until_done(server: _LoopbackServer) -> None:
    deadline = threading.Timer(LISTENER_TIMEOUT_S, server.finished.set)
    deadline.daemon = True
    deadline.start()
    try:
        while not server.finished.is_set():
            server.handle_request()
    finally:
        deadline.cancel()
        if _peek_result(server.expected_state) is None:
            _record(
                server.expected_state,
                {"ok": False, "error": "Sign-in timed out. Try again."},
            )
        server.server_close()


def start_login_listener() -> dict[str, Any]:
    """Bind a one-shot loopback listener and build the authorize URL.

    Shared by the ``/v1/auth/chatgpt/start`` route and ``sandwalk login
    chatgpt``. Returns ``{url, state, wait}`` where ``wait(timeout)`` blocks
    until the browser callback has been handled and returns its result dict.
    """
    server = _LoopbackServer("pending")
    port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}{chatgpt_auth.CALLBACK_PATH}"
    try:
        started = chatgpt_auth.begin_login(redirect_uri=redirect_uri)
    except chatgpt_auth.ChatGPTAuthError:
        server.server_close()
        raise
    server.expected_state = started["state"]
    server.timeout = 1.0
    thread = threading.Thread(
        target=_serve_until_done,
        args=(server,),
        name="chatgpt-oauth-callback",
        daemon=True,
    )
    thread.start()

    def wait(timeout: float | None = None) -> dict[str, Any]:
        server.finished.wait(timeout)
        thread.join(timeout=5.0)
        return _take_result(started["state"]) or {"ok": False, "error": "Sign-in timed out. Try again."}

    return {"url": started["url"], "state": started["state"], "wait": wait}


def register_chatgpt_auth_routes(app: FastAPI, deps: AppDeps) -> None:
    _ = deps

    @app.get("/v1/auth/chatgpt/status", response_model=ChatGPTAuthStatus)
    async def chatgpt_status(state: str | None = None) -> ChatGPTAuthStatus:
        """Current connection. With ``state``, also report a pending attempt."""
        summary = chatgpt_auth.status()
        if state:
            result = _peek_result(state)
            if result is not None:
                _take_result(state)
                if not result.get("ok"):
                    raise HTTPException(status_code=400, detail=str(result.get("error") or "Sign-in failed."))
                summary = chatgpt_auth.status()
        return ChatGPTAuthStatus(**summary)

    @app.post("/v1/auth/chatgpt/start", response_model=ChatGPTAuthStart)
    async def chatgpt_start() -> ChatGPTAuthStart:
        """Open a loopback listener and return the OpenAI authorize URL."""
        try:
            started = start_login_listener()
        except chatgpt_auth.ChatGPTAuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ChatGPTAuthStart(url=started["url"], state=started["state"])

    @app.post("/v1/auth/chatgpt/logout", response_model=ChatGPTAuthStatus)
    async def chatgpt_logout() -> ChatGPTAuthStatus:
        await asyncio.to_thread(chatgpt_auth.revoke_and_clear)
        from agent.config import Config
        from agent_server.models_service.mutate import disable_models_for_provider

        cfg = Config.load()
        if disable_models_for_provider(cfg, chatgpt_auth.PROVIDER_KEY):
            cfg.save()
        return ChatGPTAuthStatus(**chatgpt_auth.status())


__all__ = ["register_chatgpt_auth_routes", "start_login_listener"]
