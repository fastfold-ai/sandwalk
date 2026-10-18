"""Sandbox status websocket: auth, missing session, and one live event."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agent_server.routes import sessions_sandbox_stream as stream_routes


def _app(store, api_key=""):
    app = FastAPI()
    deps = SimpleNamespace(
        store=store,
        current_api_key=lambda: api_key,
        current_secret=lambda: "secret",
    )
    stream_routes.register_session_sandbox_stream_routes(app, deps)
    return TestClient(app)


def test_socket_helpers():
    closed = SimpleNamespace(
        client_state=stream_routes.WebSocketState.DISCONNECTED,
        application_state=stream_routes.WebSocketState.DISCONNECTED,
    )
    assert stream_routes._is_open(closed) is False

    class _Sock:
        client_state = stream_routes.WebSocketState.CONNECTED
        application_state = stream_routes.WebSocketState.CONNECTED
        sent = []

        async def send_json(self, payload):
            if payload.get("boom"):
                raise RuntimeError("closed")
            self.sent.append(payload)

        async def close(self, code=1000):
            if code == 1001:
                raise WebSocketDisconnect
            self.application_state = stream_routes.WebSocketState.DISCONNECTED

    sock = _Sock()
    assert asyncio.run(stream_routes._safe_send_json(sock, {"ok": True})) is True
    assert asyncio.run(stream_routes._safe_send_json(sock, {"boom": True})) is False
    asyncio.run(stream_routes._safe_close(sock, code=1001))
    asyncio.run(stream_routes._safe_close(sock))


def test_sandbox_stream_paths(monkeypatch):
    status = SimpleNamespace(
        status="running",
        model_dump=lambda mode="json", by_alias=True: {"status": "running"},
    )

    class _Svc:
        def __init__(self, store):
            self.store = store

        def status(self, session_id):
            if session_id == "explode":
                raise RuntimeError("status")
            return status

    monkeypatch.setattr(
        "agent_server.session_sandbox_service.SessionSandboxService",
        _Svc,
    )

    async def _subscribe(session_id):
        yield {"type": "sandbox_event", "sessionId": session_id}

    monkeypatch.setattr(stream_routes.sandbox_event_bus, "subscribe", _subscribe)

    store = SimpleNamespace(
        get_session=lambda session_id: object() if session_id in {"chat-1", "explode"} else None
    )

    def _expect_close(client, path):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(path) as ws:
                ws.receive_text()

    denied = _app(store, api_key="secret")
    _expect_close(denied, "/v1/sessions/chat-1/sandbox/stream")

    client = _app(store)
    _expect_close(client, "/v1/sessions/missing/sandbox/stream")

    def _lookup_boom(session_id):
        raise RuntimeError("db")

    store.get_session = _lookup_boom
    _expect_close(client, "/v1/sessions/chat-1/sandbox/stream")

    store.get_session = lambda session_id: object()
    _expect_close(client, "/v1/sessions/explode/sandbox/stream")

    with client.websocket_connect("/v1/sessions/chat-1/sandbox/stream") as ws:
        first = ws.receive_json()
        assert first["type"] == "sandbox_status"
        assert first["ready"] is True
        ws.send_json({"type": "bye"})
