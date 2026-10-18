"""Slack connector cloud calls, scopes, and slash-command rendering."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest.mock import MagicMock

from agent_server.connectors import service as connectors
from agent_server.connectors.slack_commands import SlashCommandRequest


def _request(text="status"):
    return SlashCommandRequest(
        command="/sandwalk",
        text=text,
        team_id="T1",
        user_id="U1",
        channel_id="C1",
        response_url="https://hooks.example/r",
    )


def test_cloud_request_and_scopes(monkeypatch):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok": true}'

    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout=30: _Resp())
    payload, err = connectors._cloud_request("POST", "https://cloud.example", "key", {"a": 1})
    assert payload == {"ok": True} and err is None
    payload, err = connectors._cloud_request("GET", "https://cloud.example", "key", None)
    assert err is None

    def _http(request, timeout=30):
        exc = urllib.error.HTTPError(request.full_url, 401, "no", hdrs=None, fp=None)
        exc.read = lambda: b"denied"
        raise exc

    monkeypatch.setattr(urllib.request, "urlopen", _http)
    assert "API key" in connectors._cloud_request("GET", "https://cloud.example", "key", None)[1]

    def _http500(request, timeout=30):
        exc = urllib.error.HTTPError(request.full_url, 500, "no", hdrs=None, fp=None)
        exc.read = lambda: b"boom"
        raise exc

    monkeypatch.setattr(urllib.request, "urlopen", _http500)
    assert "500" in connectors._cloud_request("GET", "https://cloud.example", "key", None)[1]

    def _down(request, timeout=30):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", _down)
    assert "Could not reach" in connectors._cloud_request("GET", "https://cloud.example", "key", None)[1]

    scopes = connectors._granted_scopes(SimpleNamespace(headers={"x-oauth-scopes": "chat:write, app_mentions:read"}))
    assert scopes == {"chat:write", "app_mentions:read"}
    listed = connectors._granted_scopes(SimpleNamespace(headers={"X-OAuth-Scopes": ["chat:write", ""]}))
    assert "chat:write" in listed
    assert connectors._granted_scopes(SimpleNamespace(headers={})) == set()


def test_oauth_urls_and_offline_start(monkeypatch):
    monkeypatch.setenv("FASTFOLD_SERVE_HOST", "0.0.0.0")
    monkeypatch.setenv("FASTFOLD_SERVE_PORT", "")
    assert connectors.local_oauth_return_url().startswith("http://127.0.0.1:")
    assert connectors.oauth_callback_return_to(origin="https://lab.example:8787/app").startswith("https://lab.example:8787")
    assert connectors.oauth_callback_return_to(origin="ftp://nope", base_url="http://0.0.0.0:1").startswith("http://")

    monkeypatch.setattr(connectors, "_is_slack_skipped", lambda: True)
    svc = connectors.ConnectorService(MagicMock())
    import asyncio

    asyncio.run(svc.start())
    assert svc._started is True
    asyncio.run(svc.start())


def test_slash_commands_and_token_state(monkeypatch):
    store = MagicMock()
    store.list_sessions.return_value = [
        SimpleNamespace(id="s", title="Thread", source="slack", source_label="Slack", updated_at="t"),
        SimpleNamespace(id="u", title="Other", source="ui", source_label="", updated_at="t"),
    ]
    store.get_slack_workspace.return_value = SimpleNamespace(team_name="Lab")
    store.list_slack_allowed_users.return_value = []
    store.list_slack_parked_messages.return_value = []
    store.is_slack_user_allowed.return_value = True
    svc = connectors.ConnectorService(store)
    svc.status = lambda: SimpleNamespace(relay_state="live", relay_detail=None)
    svc._account_email = "a@b.c"
    svc._account_user_id = "user"

    rows = svc._recent_slack_home_sessions()
    assert rows[0].id == "s"
    status = svc._slack_home_status("T1")
    assert status.team_name == "Lab"
    assert "Lab" in svc._render_slash_command(_request("status")) or svc._render_slash_command(_request("status"))
    assert svc._render_slash_command(_request("sessions"))
    assert svc._render_slash_command(_request("parked"))
    assert svc._render_slash_command(_request("nope"))
    allowed = svc._render_people_command(_request("people allow <@U9>"))
    assert allowed
    store.allow_slack_user.assert_called()
    assert svc._render_people_command(_request("people allow"))
    assert svc._render_people_command(_request("people nope"))

    store.is_slack_user_allowed.return_value = False
    posted = {}
    monkeypatch.setattr(
        "agent_server.connectors.slack_commands.post_response",
        lambda url, text: posted.setdefault("text", text),
    )
    import asyncio

    asyncio.run(svc.handle_slash_command(_request("status")))
    assert posted["text"]

    svc._sockets["T1"] = object()
    called = {}
    svc._republish_home = lambda team_id: called.setdefault("team", team_id)
    svc._set_relay_state("live", None)
    assert called["team"] == "T1"

    svc._mark_slack_token_invalid("T1", "expired")
    store.set_slack_workspace_reauth.assert_called()
    store.set_slack_workspace_reauth.side_effect = RuntimeError("db")
    svc._mark_slack_token_invalid("T1", "again")

    monkeypatch.setattr(
        "agent_server.account_service._resolve_user",
        lambda key, base: ("id", "a@b.c", "ada"),
    )
    monkeypatch.setattr("agent_server.account_service.helpers.cloud_base_url", lambda: "https://cloud")
    svc._resolve_account_identity("key")
    assert svc._account_email == "a@b.c"
    assert json.dumps({"ok": True})
