"""Direct coverage for auth, session-event, and MCP manage routes."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from agent_server.models import (
    AuthLoginRequest,
    EventEnvelope,
    McpServer,
    UpdateAuthSettingsRequest,
    UpdateMcpServerRequest,
)
from agent_server.routes import auth as auth_routes
from agent_server.routes import mcp_servers_manage as mcp_routes
from agent_server.routes import sessions_events as event_routes


def _endpoint(app: FastAPI, path: str, method: str):
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        if getattr(route, "path", None) == path and method in methods:
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


def _request(app: FastAPI, host: str | None = "127.0.0.1") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/v1/auth/status",
        "raw_path": b"/v1/auth/status",
        "query_string": b"",
        "headers": [],
        "client": None if host is None else (host, 9),
        "server": ("testserver", 80),
        "app": app,
    }
    return Request(scope)


def _settings(**overrides) -> SimpleNamespace:
    fields = {
        "auth_enabled": True,
        "api_key": "sk-test-key",
        "secret_key": "secret",
        "api_key_configured": True,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _register_auth(monkeypatch, settings, *, keys=("real-key",), authenticated=True):
    monkeypatch.setattr(auth_routes, "load_settings", lambda: settings)
    monkeypatch.setattr(auth_routes, "request_is_authenticated", lambda **kwargs: authenticated)
    app = FastAPI()
    deps = SimpleNamespace(
        accepted_api_keys=lambda: list(keys),
        current_secret=lambda: "secret",
        reloads=0,
    )

    def _reload():
        deps.reloads += 1

    deps.reload_auth_state = _reload
    auth_routes.register_auth_routes(app, deps)
    return app, deps


def test_loopback_host_accepts_ip_loopback_and_rejects_junk() -> None:
    assert auth_routes._is_loopback_host("127.0.0.1") is True
    assert auth_routes._is_loopback_host("::1") is True
    assert auth_routes._is_loopback_host("10.1.2.3") is False
    assert auth_routes._is_loopback_host("not a host") is False
    assert auth_routes._is_loopback_host("") is False


def test_auth_status_treats_disabled_auth_as_authenticated(monkeypatch) -> None:
    settings = _settings(auth_enabled=False, api_key_configured=False)
    app, _deps = _register_auth(monkeypatch, settings)
    status = _endpoint(app, "/v1/auth/status", "GET")

    result = asyncio.run(status(_request(app)))

    assert result.authenticated is True
    assert result.auth_enabled is False
    assert result.api_key_configured is False
    assert app.state.auth_settings is settings


def test_auth_login_rejects_a_key_that_does_not_match(monkeypatch) -> None:
    settings = _settings()
    app, _deps = _register_auth(monkeypatch, settings)
    login = _endpoint(app, "/v1/auth/login", "POST")

    with pytest.raises(HTTPException) as raised:
        asyncio.run(login(AuthLoginRequest(api_key="wrong-key")))

    assert raised.value.status_code == 401
    assert raised.value.detail == "Invalid API key."
    assert app.state.auth_settings is settings


def test_auth_reload_rejects_non_loopback_clients(monkeypatch) -> None:
    app, deps = _register_auth(monkeypatch, _settings())
    reload = _endpoint(app, "/v1/auth/reload", "POST")

    with pytest.raises(HTTPException) as remote:
        asyncio.run(reload(_request(app, host="10.1.2.3")))
    with pytest.raises(HTTPException) as missing_client:
        asyncio.run(reload(_request(app, host=None)))

    assert remote.value.status_code == 403
    assert remote.value.detail == "Auth reload is loopback-only."
    assert missing_client.value.status_code == 403
    assert deps.reloads == 0


def test_get_auth_settings_requires_a_matching_key_when_keys_exist(monkeypatch) -> None:
    settings = _settings()
    denied_app, _deps = _register_auth(monkeypatch, settings, authenticated=False)
    denied = _endpoint(denied_app, "/v1/auth/settings", "GET")
    with pytest.raises(HTTPException) as raised:
        asyncio.run(denied(_request(denied_app)))
    assert raised.value.status_code == 401
    assert raised.value.detail == "Missing or invalid backend API key."

    app, _deps = _register_auth(monkeypatch, settings, authenticated=True)
    get_settings = _endpoint(app, "/v1/auth/settings", "GET")
    result = asyncio.run(get_settings(_request(app)))
    assert result.api_key == "sk-test-key"
    assert result.auth_enabled is True
    assert result.api_key_configured is True
    assert app.state.auth_settings is settings


def test_patch_auth_settings_rejects_bad_callers_and_bad_keys(monkeypatch) -> None:
    settings = _settings()
    denied_app, _deps = _register_auth(monkeypatch, settings, authenticated=False)
    denied = _endpoint(denied_app, "/v1/auth/settings", "PATCH")
    with pytest.raises(HTTPException) as unauthorized:
        asyncio.run(denied(_request(denied_app), UpdateAuthSettingsRequest(auth_enabled=False)))
    assert unauthorized.value.status_code == 401

    app, deps = _register_auth(monkeypatch, settings, authenticated=True)
    patch = _endpoint(app, "/v1/auth/settings", "PATCH")
    with pytest.raises(HTTPException) as invalid:
        asyncio.run(patch(_request(app), UpdateAuthSettingsRequest(api_key="no")))
    assert invalid.value.status_code == 400
    assert "at least 4" in str(invalid.value.detail)
    assert deps.reloads == 0


def test_patch_auth_settings_enables_auth_and_persists_a_new_key(monkeypatch) -> None:
    settings = _settings(auth_enabled=False, api_key="", secret_key="", api_key_configured=False)
    saved: list[SimpleNamespace] = []
    ensured: list[str] = []

    def _ensure(current):
        ensured.append(current.secret_key)
        if not current.api_key:
            current.api_key = "generated-key"
            current.api_key_configured = True
            return current
        current.secret_key = current.secret_key or "generated-secret"
        return current

    app, deps = _register_auth(monkeypatch, settings, authenticated=True)
    monkeypatch.setattr(auth_routes, "ensure_api_key", _ensure)
    monkeypatch.setattr(auth_routes, "save_settings", saved.append)
    patch = _endpoint(app, "/v1/auth/settings", "PATCH")

    enabled = asyncio.run(patch(_request(app), UpdateAuthSettingsRequest(auth_enabled=True)))

    assert enabled.auth_enabled is True
    assert enabled.api_key == "generated-key"
    assert enabled.api_key_configured is True
    assert settings.secret_key == "generated-secret"
    assert ensured == ["", ""]
    assert saved == [settings]
    assert deps.reloads == 1

    keyed = _settings(api_key="old-key", secret_key="already-set")
    keyed_app, keyed_deps = _register_auth(monkeypatch, keyed, authenticated=True)

    def _ensure_unused(current):
        raise AssertionError(current)

    monkeypatch.setattr(auth_routes, "ensure_api_key", _ensure_unused)
    monkeypatch.setattr(auth_routes, "save_settings", saved.append)
    keyed_patch = _endpoint(keyed_app, "/v1/auth/settings", "PATCH")
    updated = asyncio.run(
        keyed_patch(_request(keyed_app), UpdateAuthSettingsRequest(api_key="  fresh-key  "))
    )
    assert updated.api_key == "fresh-key"
    assert keyed_deps.reloads == 1
    assert saved[-1] is keyed


class _EventRequest:
    def __init__(self, app: FastAPI, headers: dict[str, str] | None = None, *, stop_after_waits: int | None = None):
        self.app = app
        self.headers = headers or {}
        self.stop_after_waits = stop_after_waits
        self.disconnected = False
        self.waits = 0

    async def is_disconnected(self) -> bool:
        return self.disconnected

    def note_wait(self) -> None:
        self.waits += 1
        if self.stop_after_waits is not None and self.waits >= self.stop_after_waits:
            self.disconnected = True


class _Owner:
    def __init__(self) -> None:
        self.session = object()
        self.batches: list[list[EventEnvelope]] = []
        self.cursors: list[int] = []

    def get_session(self, session_id: str):
        if session_id == "missing":
            return None
        return self.session

    def list_events(self, session_id: str, after_sequence: int = 0):
        self.cursors.append(after_sequence)
        if self.batches:
            return self.batches.pop(0)
        return []


class _Obs:
    def __init__(self) -> None:
        self.opened = 0
        self.closed = 0

    def sse_opened(self) -> None:
        self.opened += 1

    def sse_closed(self) -> None:
        self.closed += 1


def _events_app(monkeypatch, owner: _Owner):
    async def _inline(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    holder: dict[str, _EventRequest] = {}

    async def _wait(session_id: str, generation: int, timeout: float) -> None:
        holder["request"].note_wait()

    monkeypatch.setattr(event_routes.asyncio, "to_thread", _inline)
    monkeypatch.setattr(event_routes.EVENT_NOTIFIER, "generation", lambda session_id: 3)
    monkeypatch.setattr(event_routes.EVENT_NOTIFIER, "async_wait_for_change", _wait)
    obs = _Obs()
    monkeypatch.setattr(event_routes, "OBSERVABILITY", obs)
    app = FastAPI()
    app.state.shutdown_event = asyncio.Event()
    deps = SimpleNamespace(store=object(), store_for_session=lambda session_id: owner)
    event_routes.register_session_event_routes(app, deps)
    return app, obs, holder


async def _chunks(response) -> list[str]:
    collected = []
    async for chunk in response.body_iterator:
        collected.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    return collected


def test_event_history_replays_events_or_404s(monkeypatch) -> None:
    owner = _Owner()
    event = EventEnvelope(
        id="evt-1",
        session_id="sess-1",
        sequence=2,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        type="run.completed",
        payload={},
    )
    owner.batches = [[event]]
    app, _obs, _holder = _events_app(monkeypatch, owner)
    history = _endpoint(app, "/v1/sessions/{session_id}/events/history", "GET")

    found = asyncio.run(history("sess-1"))
    assert [item.sequence for item in found.data] == [2]
    assert owner.cursors == [0]

    with pytest.raises(HTTPException) as raised:
        asyncio.run(history("missing"))

    assert raised.value.status_code == 404
    assert raised.value.detail == "Session not found."


def test_event_stream_replays_flushes_and_heartbeats(monkeypatch) -> None:
    owner = _Owner()
    app, obs, holder = _events_app(monkeypatch, owner)
    stream = _endpoint(app, "/v1/sessions/{session_id}/events", "GET")

    with pytest.raises(HTTPException) as missing:
        asyncio.run(stream(_EventRequest(app), "missing", 0))
    assert missing.value.status_code == 404

    app.state.shutdown_event.set()
    shutdown_request = _EventRequest(app, {"last-event-id": "4"})
    holder["request"] = shutdown_request
    async def _shutdown():
        return await _chunks(await stream(shutdown_request, "sess-1", 0))

    shutdown_chunks = asyncio.run(_shutdown())
    assert shutdown_chunks == []
    assert shutdown_request.waits == 0
    app.state.shutdown_event.clear()

    plain = _EventRequest(app, {"last-event-id": "nope"}, stop_after_waits=1)
    holder["request"] = plain
    async def _plain():
        return await _chunks(await stream(plain, "sess-1", 4))

    plain_chunks = asyncio.run(_plain())
    assert plain_chunks == []
    assert owner.cursors == [4]

    event = EventEnvelope(
        id="evt-1",
        session_id="sess-1",
        sequence=11,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        type="assistant.message",
        payload={"text": "hi"},
    )
    owner.cursors.clear()
    owner.batches = [[event]]
    live = _EventRequest(app, {"last-event-id": "9"}, stop_after_waits=15)
    holder["request"] = live

    async def _live():
        response = await stream(live, "sess-1", 4)
        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"
        return await _chunks(response)

    chunks = asyncio.run(_live())

    assert owner.cursors[0] == 9
    assert owner.cursors[1:] == [11] * 15
    payload = json.loads(chunks[0].split("data: ", 1)[1])
    assert chunks[0].startswith("id: 11\n")
    assert payload["sequence"] == 11
    assert payload["type"] == "assistant.message"
    pad = ":" + (" " * 8192) + "\n\n"
    assert chunks[1] == pad
    assert chunks[2] == pad
    assert chunks[3] == ": heartbeat\n\n"
    assert obs.opened == obs.closed == 3


def _server(**overrides) -> McpServer:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    fields = {
        "id": "srv-1",
        "name": "Remote",
        "transport": "streamable_http",
        "url": "http://example.test/mcp",
        "enabled": False,
        "catalog_id": None,
        "created_at": now,
        "updated_at": now,
    }
    fields.update(overrides)
    return McpServer(**fields)


class _McpStore:
    def __init__(self, servers, updated=None, deleted=True):
        self.servers = servers
        self.updated = updated
        self.deleted = deleted
        self.changes = None

    def list_mcp_servers(self):
        return self.servers

    def update_mcp_server(self, server_id: str, **changes):
        self.changes = changes
        return self.updated

    def delete_mcp_server(self, server_id: str) -> bool:
        return self.deleted


class _McpService:
    def __init__(self) -> None:
        self.validated: list[str] = []

    def validate(self, server_id: str) -> None:
        self.validated.append(server_id)


def _manage(monkeypatch, store: _McpStore, *, creds_ok: bool = True):
    async def _inline(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    calls = {
        "headers": [],
        "export": 0,
        "cleared": [],
        "removed": [],
        "caches": 0,
        "ttl": [],
    }
    monkeypatch.setattr(mcp_routes.asyncio, "to_thread", _inline)
    monkeypatch.setattr(
        mcp_routes,
        "set_custom_headers",
        lambda server_id, headers: calls["headers"].append((server_id, headers)),
    )
    monkeypatch.setattr(mcp_routes, "custom_server_credentials_configured", lambda server: creds_ok)
    monkeypatch.setattr(
        mcp_routes,
        "get_or_export_mcp_json",
        lambda _store: calls.__setitem__("export", calls["export"] + 1),
    )
    monkeypatch.setattr(mcp_routes, "enrich_mcp_server", lambda server: server)
    monkeypatch.setattr(
        mcp_routes,
        "clear_custom_headers",
        lambda server_id: calls["cleared"].append(server_id),
    )
    monkeypatch.setattr(
        mcp_routes,
        "mark_catalog_removed",
        lambda catalog_id: calls["removed"].append(catalog_id),
    )
    monkeypatch.setattr(
        "agent.deepagents_runtime.mcp_tools.clear_mcp_tool_caches",
        lambda: calls.__setitem__("caches", calls["caches"] + 1),
    )
    monkeypatch.setattr(
        "agent_server.ttl_cache.invalidate",
        lambda prefix: calls["ttl"].append(prefix),
    )
    app = FastAPI()
    service = _McpService()
    mcp_routes.register_mcp_server_manage_routes(app, SimpleNamespace(store=store, mcp_service=service))
    update = _endpoint(app, "/v1/mcp-servers/{server_id}", "PATCH")
    delete = _endpoint(app, "/v1/mcp-servers/{server_id}", "DELETE")
    return update, delete, calls, service


def test_update_mcp_server_missing_unauthorized_and_vanished(monkeypatch) -> None:
    missing_update, _delete, calls, service = _manage(monkeypatch, _McpStore([]))
    with pytest.raises(HTTPException) as missing:
        asyncio.run(missing_update("srv-1", UpdateMcpServerRequest(name="x")))
    assert missing.value.status_code == 404
    assert missing.value.detail == "MCP server not found."

    blocked_store = _McpStore([_server(transport="sse")])
    blocked, _delete, calls, service = _manage(monkeypatch, blocked_store, creds_ok=False)
    with pytest.raises(HTTPException) as blocked_call:
        asyncio.run(
            blocked(
                "srv-1",
                UpdateMcpServerRequest(enabled=True, headers={"Authorization": "Bearer x"}),
            )
        )
    assert blocked_call.value.status_code == 400
    assert blocked_call.value.detail == "Authenticate this MCP server before enabling it."
    assert calls["headers"] == [("srv-1", {"Authorization": "Bearer x"})]
    assert blocked_store.changes is None
    assert calls["export"] == 0
    assert service.validated == []

    vanished = _McpStore([_server(transport="stdio", enabled=True)], updated=None)
    update, _delete, calls, service = _manage(monkeypatch, vanished)
    with pytest.raises(HTTPException) as gone:
        asyncio.run(update("srv-1", UpdateMcpServerRequest(name="Renamed")))
    assert gone.value.status_code == 404
    assert vanished.changes == {"name": "Renamed"}
    assert service.validated == []


def test_update_mcp_server_validates_enabled_remote_and_skips_local(monkeypatch) -> None:
    remote = _server(enabled=True, url="http://example.test/mcp")
    store = _McpStore([_server()], updated=remote)
    update, _delete, calls, service = _manage(monkeypatch, store, creds_ok=True)
    result = asyncio.run(
        update(
            "srv-1",
            UpdateMcpServerRequest(enabled=True, headers_helper_command="helper"),
        )
    )
    assert result is remote
    assert store.changes["enabled"] is True
    assert store.changes["headers_helper_command"] == "helper"
    assert service.validated == ["srv-1"]
    assert calls["export"] == 1
    assert calls["caches"] == 1
    assert calls["ttl"] == ["mcp:"]

    local = _server(transport="stdio", enabled=True, url=None, command="echo")
    local_store = _McpStore([local], updated=local)
    local_update, _delete, calls, service = _manage(monkeypatch, local_store, creds_ok=False)
    saved = asyncio.run(local_update("srv-1", UpdateMcpServerRequest(enabled=True)))
    assert saved is local
    assert service.validated == []

    no_url = _server(transport="sse", enabled=True, url=None)
    quiet_store = _McpStore([_server(transport="sse", url="http://example.test/mcp")], updated=no_url)
    quiet_update, _delete, _calls, service = _manage(monkeypatch, quiet_store, creds_ok=True)
    asyncio.run(quiet_update("srv-1", UpdateMcpServerRequest(enabled=True)))
    assert service.validated == []

    catalog = _server(catalog_id="cat", enabled=True)
    catalog_store = _McpStore([catalog], updated=catalog)
    catalog_update, _delete, _calls, service = _manage(monkeypatch, catalog_store, creds_ok=False)
    asyncio.run(catalog_update("srv-1", UpdateMcpServerRequest(enabled=True)))
    assert service.validated == []


def test_delete_mcp_server_missing_noop_and_catalog_cleanup(monkeypatch) -> None:
    missing_update, missing_delete, calls, _service = _manage(monkeypatch, _McpStore([]))
    assert missing_update is not None
    with pytest.raises(HTTPException) as missing:
        asyncio.run(missing_delete("srv-1"))
    assert missing.value.status_code == 404
    assert calls["cleared"] == []

    kept = _McpStore([_server()], deleted=False)
    _update, keep_delete, calls, _service = _manage(monkeypatch, kept)
    with pytest.raises(HTTPException) as still_there:
        asyncio.run(keep_delete("srv-1"))
    assert still_there.value.status_code == 404
    assert calls["cleared"] == []
    assert calls["export"] == 0

    plain = _McpStore([_server(catalog_id=None)], deleted=True)
    _update, plain_delete, calls, _service = _manage(monkeypatch, plain)
    removed = asyncio.run(plain_delete("srv-1"))
    assert removed.deleted is True
    assert calls["cleared"] == ["srv-1"]
    assert calls["removed"] == []
    assert calls["export"] == 1
    assert calls["caches"] == 1
    assert calls["ttl"] == ["mcp:"]

    catalog = _McpStore([_server(catalog_id="cat-9")], deleted=True)
    _update, catalog_delete, calls, _service = _manage(monkeypatch, catalog)
    asyncio.run(catalog_delete("srv-1"))
    assert calls["cleared"] == ["srv-1"]
    assert calls["removed"] == ["cat-9"]
    assert calls["caches"] == 1
