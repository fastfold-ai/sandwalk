"""Remaining connector-service and sites-cloud coverage, with Slack and HTTP mocked."""

from __future__ import annotations

import asyncio
import sys
import urllib.error
import urllib.request
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypeVar

import pytest

from agent_server.connectors.directory import SlackChannelEntry, SlackPerson
from agent_server.connectors.gateway import InboundMessage, RouteDecision
from agent_server.connectors.service import ConnectorService
from agent_server.connectors.slack_assistant import THINKING_STATUS
from agent_server.connectors.slack_home import RECENT_LIMIT
from agent_server.models.connectors import SlackParkedMessage
from agent_server.service import SessionBusyError
from agent_server.sites_service.cloud import FastFoldSitesClient
from agent_server.store import AgentStore

T = TypeVar("T")


def run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path: Path) -> AgentStore:
    return AgentStore(tmp_path / "agent.db", exclusive=True)


@pytest.fixture()
def service(store: AgentStore) -> ConnectorService:
    return ConnectorService(store)


def message(**overrides: object) -> InboundMessage:
    payload: dict[str, object] = {
        "team_id": "T1",
        "channel_id": "C1",
        "user_id": "U1",
        "text": "hey",
        "ts": "1712000000.000100",
    }
    payload.update(overrides)
    return InboundMessage(**payload)  # type: ignore[arg-type]


def patch_cloud(monkeypatch: pytest.MonkeyPatch, *, key: str = "sk-test") -> None:
    monkeypatch.setattr(
        "agent_server.account_service.helpers.api_key",
        lambda cfg=None: key,
    )
    monkeypatch.setattr(
        "agent_server.account_service.helpers.cloud_base_url",
        lambda: "https://cloud.test",
    )


class _HTTPResponse:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _HTTPResponse:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


def _http_error(url: str, code: int, body: bytes) -> urllib.error.HTTPError:
    error = urllib.error.HTTPError(url, code, "err", hdrs=None, fp=None)

    def _read() -> bytes:
        return body

    error.read = _read  # type: ignore[method-assign]
    return error


class _RelayFakes:
    def __init__(self) -> None:
        self.clients: list[Any] = []
        self.workspaces: list[Any] = []


def install_relay_fakes(monkeypatch: pytest.MonkeyPatch) -> _RelayFakes:
    """Replace the relay client so startup never opens a socket."""
    fakes = _RelayFakes()

    class FakeRelayWorkspace:
        def __init__(self, *, team_id: str, bot_token: str, bot_user_id: str | None) -> None:
            self.team_id = team_id
            self.bot_token = bot_token
            self.bot_user_id = bot_user_id
            self.specialist_names: list[str] = []
            self.home_sessions = None
            self.home_status = None
            self.on_token_invalid = None
            self.loaded = False
            self.connected = True
            fakes.workspaces.append(self)

        async def load_directory(self) -> None:
            self.loaded = True

    class FakeRelayClient:
        def __init__(
            self,
            *,
            base_url: str,
            api_key: str,
            on_message: Any,
            on_state: Any,
            on_slash_command: Any,
        ) -> None:
            self.base_url = base_url
            self.api_key = api_key
            self.on_message = on_message
            self.on_state = on_state
            self.on_slash_command = on_slash_command
            self.connected = True
            self.started = False
            self.workspaces: list[Any] = []
            fakes.clients.append(self)

        def add_workspace(self, workspace: Any) -> None:
            self.workspaces.append(workspace)

        async def start(self) -> None:
            self.started = True

    monkeypatch.setattr(
        "agent_server.connectors.slack_relay.SlackRelayClient",
        FakeRelayClient,
    )
    monkeypatch.setattr(
        "agent_server.connectors.slack_relay.SlackRelayWorkspace",
        FakeRelayWorkspace,
    )
    return fakes


def test_slack_skip_survives_a_missing_offline_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "agent_server.offline_mode", None)
    from agent_server.connectors.service import _is_slack_skipped

    assert _is_slack_skipped() is False


def test_import_one_click_requires_a_cloud_key(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_cloud(monkeypatch, key="")
    with pytest.raises(ValueError, match="Connect Fastfold"):
        run(service.import_one_click_connections())


def test_import_one_click_surfaces_listing_errors(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_cloud(monkeypatch)

    def fake_cloud_request(method: str, url: str, key: str, body: object) -> tuple[None, str]:
        del method, url, key, body
        return None, "FastFold returned 503: down"

    monkeypatch.setattr("agent_server.connectors.service._cloud_request", fake_cloud_request)
    with pytest.raises(ValueError, match="503"):
        run(service.import_one_click_connections())


def test_import_one_click_skips_incomplete_rows_and_token_failures(
    service: ConnectorService, store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_cloud(monkeypatch)
    fetched: list[str] = []

    def fake_cloud_request(
        method: str, url: str, key: str, body: object
    ) -> tuple[dict[str, Any] | None, str | None]:
        del method, key, body
        fetched.append(url)
        if url.endswith("/v1/slack/connections"):
            return {
                "data": [
                    {"team_id": "", "id": "conn-blank"},
                    {"team_id": "T2", "id": ""},
                    {"id": "conn-no-team"},
                    {"team_id": "T3", "id": "conn-3"},
                    {"team_id": "T4", "id": "conn-4"},
                ]
            }, None
        if url.endswith("/conn-3"):
            return None, "expired"
        if url.endswith("/conn-4"):
            return {}, None
        raise AssertionError(url)

    monkeypatch.setattr("agent_server.connectors.service._cloud_request", fake_cloud_request)
    imported = run(service.import_one_click_connections())
    assert imported == []
    assert store.list_slack_workspaces() == []
    assert any(url.endswith("/conn-3") for url in fetched)
    assert any(url.endswith("/conn-4") for url in fetched)


def test_directory_missing_workspace_sdk_and_token(
    service: ConnectorService, store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(KeyError):
        run(service.directory("T-missing"))

    store.upsert_slack_workspace(team_id="T1", mode="relay", bot_token="xoxb-1")
    monkeypatch.setattr("agent_server.connectors.service.slack_sdk_available", lambda: False)
    assert run(service.directory("T1")) == ([], [])

    monkeypatch.setattr("agent_server.connectors.service.slack_sdk_available", lambda: True)
    store.upsert_slack_workspace(team_id="T2", mode="socket")
    assert run(service.directory("T2")) == ([], [])

    seen: dict[str, object] = {}

    async def fake_fetch(team_id: str, bot_token: str, *, force: bool = False) -> tuple[list, list]:
        seen["args"] = (team_id, bot_token, force)
        return (
            [SlackPerson(id="U1", name="Ada")],
            [SlackChannelEntry(id="C1", name="general")],
        )

    monkeypatch.setattr("agent_server.connectors.service.fetch_directory", fake_fetch)
    people, channels = run(service.directory("T1", force=True))
    assert [person.name for person in people] == ["Ada"]
    assert [channel.name for channel in channels] == ["general"]
    assert seen["args"] == ("T1", "xoxb-1", True)


def test_resolve_team_id_reports_a_missing_sdk(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "slack_sdk.web.async_client", None)
    with pytest.raises(ValueError, match="not installed"):
        run(service._resolve_team_id("xoxb-x"))


def test_resolve_team_id_validates_the_auth_test_response(
    service: ConnectorService, store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SLACK_API_URL", "https://slack.test/api/")

    class Auth(dict):
        def __init__(self, fields: dict[str, str], *, headers: dict[str, str]) -> None:
            super().__init__(fields)
            self.headers = headers

    created: list[FakeClient] = []

    class FakeClient:
        mode = "ok"

        def __init__(self, token: str, base_url: str | None = None) -> None:
            self.token = token
            self.base_url = base_url
            created.append(self)

        async def auth_test(self) -> Auth:
            if FakeClient.mode == "boom":
                raise RuntimeError("invalid_auth")
            if FakeClient.mode == "noteam":
                return Auth({}, headers={"x-oauth-scopes": "app_mentions:read, chat:write"})
            if FakeClient.mode == "scopes":
                return Auth(
                    {"team_id": "T1", "team": "Acme", "user_id": "UBOT"},
                    headers={"x-oauth-scopes": "chat:write"},
                )
            return Auth(
                {"team_id": "T1", "team": "Acme", "user_id": "UBOT"},
                headers={"x-oauth-scopes": "app_mentions:read, chat:write"},
            )

    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient", FakeClient)

    FakeClient.mode = "boom"
    with pytest.raises(ValueError, match="rejected the bot token"):
        run(service._resolve_team_id("xoxb-bad"))

    FakeClient.mode = "noteam"
    with pytest.raises(ValueError, match="did not return a workspace"):
        run(service._resolve_team_id("xoxb-noteam"))

    FakeClient.mode = "scopes"
    with pytest.raises(ValueError, match="app_mentions:read"):
        run(service._resolve_team_id("xoxb-scopes"))

    FakeClient.mode = "ok"
    assert run(service._resolve_team_id("xoxb-ok")) == "T1"
    workspace = store.get_slack_workspace("T1")
    assert workspace is not None
    assert workspace.team_name == "Acme"
    assert workspace.bot_user_id == "UBOT"
    assert created[-1].base_url == "https://slack.test/api/"


def test_start_workspace_socket_edges(
    service: ConnectorService, store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    run(service._start_workspace(SimpleNamespace(mode="poll", team_id="Tx")))  # type: ignore[arg-type]
    assert service._sockets == {}

    store.upsert_slack_workspace(
        team_id="T1", mode="socket", bot_token="xoxb-1", app_token="xapp-1"
    )
    monkeypatch.setattr("agent_server.connectors.service.slack_sdk_available", lambda: False)
    workspace = store.get_slack_workspace("T1")
    assert workspace is not None
    run(service._start_workspace(workspace))
    assert "not installed" in (service._relay_detail or "")
    assert service.socket_connected("T1") is False

    state = {"ok": False, "bot": "UBOT"}

    class FakeSocket:
        def __init__(
            self, *, team_id: str, bot_token: str, app_token: str, on_message: Any
        ) -> None:
            self.team_id = team_id
            self.bot_token = bot_token
            self.app_token = app_token
            self.on_message = on_message
            self.bot_user_id = state["bot"]
            self.connected = True

        async def connect(self) -> bool:
            return bool(state["ok"])

        async def disconnect(self) -> None:
            return None

    monkeypatch.setattr("agent_server.connectors.service.slack_sdk_available", lambda: True)
    monkeypatch.setattr("agent_server.connectors.service.SlackSocketAdapter", FakeSocket)

    run(service._start_workspace(workspace))
    assert service.socket_connected("T1") is False

    state["ok"] = True
    run(service._start_workspace(store.get_slack_workspace("T1") or workspace))
    assert service.socket_connected("T1") is True
    saved = store.get_slack_workspace("T1")
    assert saved is not None and saved.bot_user_id == "UBOT"


def test_start_relay_without_a_cloud_key_or_bot_token(
    service: ConnectorService, store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = install_relay_fakes(monkeypatch)
    store.upsert_slack_workspace(
        team_id="T1", mode="relay", bot_token="xoxb-1", team_name="Acme"
    )
    patch_cloud(monkeypatch, key="")
    workspace = store.get_slack_workspace("T1")
    assert workspace is not None
    run(service._start_workspace(workspace))
    assert service._relay_state == "signed_out"
    assert "Fastfold" in (service._relay_detail or "")
    assert fakes.clients == []

    def resolve(key: str) -> None:
        service._account_email = "ada@fastfold.ai"
        service._account_user_id = "user-1"
        assert key == "sk-test"

    service._resolve_account_identity = resolve  # type: ignore[method-assign]
    patch_cloud(monkeypatch, key="sk-test")
    store.upsert_slack_workspace(team_id="T2", mode="relay", team_name="NoToken")
    missing = store.get_slack_workspace("T2")
    assert missing is not None
    run(service._start_workspace(missing))
    assert "T2" not in service._sockets
    assert fakes.clients == []
    assert service._account_email == "ada@fastfold.ai"


def test_start_relay_workspace_registers_and_republishes(
    service: ConnectorService, store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    fakes = install_relay_fakes(monkeypatch)
    patch_cloud(monkeypatch, key="sk-test")

    def resolve(key: str) -> None:
        assert key == "sk-test"
        service._account_email = "ada@fastfold.ai"
        service._account_user_id = "user-1"

    service._resolve_account_identity = resolve  # type: ignore[method-assign]
    store.upsert_slack_workspace(
        team_id="T1",
        mode="relay",
        team_name="Acme",
        bot_token="xoxb-live",
        bot_user_id="UBOT",
    )
    workspace = store.get_slack_workspace("T1")
    assert workspace is not None
    run(service._start_workspace(workspace))

    assert len(fakes.clients) == 1
    client = fakes.clients[0]
    assert client.started is True
    assert client.base_url == "https://cloud.test"
    assert client.api_key == "sk-test"
    adapter = service._sockets["T1"]
    assert adapter.loaded is True
    assert adapter.bot_token == "xoxb-live"
    assert adapter.specialist_names == [item.name for item in store.list_specialists()]
    home = adapter.home_status()
    assert home.team_name == "Acme"
    assert home.account_email == "ada@fastfold.ai"
    adapter.on_token_invalid("token_revoked")
    saved = store.get_slack_workspace("T1")
    assert saved is not None and saved.needs_reauth is True
    rows = adapter.home_sessions()
    assert rows == []


def test_recent_slack_home_sessions_stop_at_the_limit(
    service: ConnectorService, store: AgentStore
) -> None:
    store.create_session(title="Local", workspace_path=None)
    for index in range(RECENT_LIMIT + 1):
        store.create_session(
            title=f"Slack {index}",
            workspace_path=None,
            source="slack",
            source_label="#dev",
        )
    rows = service._recent_slack_home_sessions()
    assert len(rows) == RECENT_LIMIT
    assert all(row.source_label == "#dev" for row in rows)


def test_run_progress_uses_the_assistant_status(
    service: ConnectorService, store: AgentStore
) -> None:
    class Assistant:
        def __init__(self) -> None:
            self.cleared = False
            self.status: str | None = None

        async def set_status(self, **kwargs: object) -> bool:
            self.status = str(kwargs["status"])
            return True

        async def clear_status(self, **kwargs: object) -> None:
            del kwargs
            self.cleared = True

    class Adapter:
        def __init__(self) -> None:
            self.assistant = Assistant()
            self.reactions: list[dict[str, object]] = []

        async def set_reaction(self, **kwargs: object) -> None:
            self.reactions.append(kwargs)

    adapter = Adapter()
    service._sockets["T1"] = adapter
    run(service._run_progress(message(thread_ts="1712000000.000100"), ["missing-session"]))
    assert adapter.assistant.status == THINKING_STATUS
    assert adapter.assistant.cleared is True
    assert adapter.reactions == []
    assert store.get_session("missing-session") is None


def test_wait_for_idle_times_out_immediately(
    service: ConnectorService, store: AgentStore
) -> None:
    session = store.create_session(title="Busy", workspace_path=None, source="slack")
    store.set_session_status(session.id, "running")
    assert run(service._wait_for_idle(session.id, timeout=0)) is False


def test_inbound_from_parked_without_a_timestamp() -> None:
    parked = SlackParkedMessage(
        id="p1",
        team_id="T1",
        channel="slack:T1/C1",
        thread_target=None,
        slack_user_id="U1",
        text="hi",
        created_at=datetime.now(UTC),
    )
    assert ConnectorService._inbound_from_parked(parked) is None

    unstamped = parked.model_copy(update={"thread_target": "slack:T1/C1"})
    assert ConnectorService._inbound_from_parked(unstamped) is None


def test_spawn_session_logs_and_drops_when_create_fails(service: ConnectorService) -> None:
    class Agent:
        def create_session(self, **kwargs: object) -> None:
            del kwargs
            raise RuntimeError("db down")

    service.agent_service = Agent()  # type: ignore[assignment]
    decision = RouteDecision(action="spawn", reason="new mention")
    assert service._spawn_session(message(), decision) is None


def test_republish_home_skips_adapters_without_a_home_publisher(
    service: ConnectorService,
) -> None:
    service._sockets["T1"] = object()
    service._republish_home("T1")
    service._republish_home("T-missing")

    published: list[list[str]] = []

    async def publish_home_for_users(user_ids: list[str]) -> None:
        published.append(user_ids)

    service._sockets["T2"] = SimpleNamespace(publish_home_for_users=publish_home_for_users)
    service._republish_home("T2")
    assert published == []


def test_dm_channel_name_uses_the_directory_when_the_bot_handle_is_blank(
    service: ConnectorService,
) -> None:
    dm = message(channel_id="D9")
    assert service._dm_channel_name(dm) is None

    class Named:
        _bot_name = None
        bot_user_id = "B1"
        user_names = {"B1": " sandwalk "}

    service._sockets["T1"] = Named()
    assert service._dm_channel_name(dm) == "sandwalk"

    class PrivateNames:
        _bot_name = "   "
        bot_user_id = "B2"
        user_names: dict[str, str] = {}
        _user_names = {"B2": "helper"}

    service._sockets["T1"] = PrivateNames()
    assert service._dm_channel_name(dm) == "helper"

    class Blank:
        _bot_name = None
        bot_user_id = "B3"
        user_names = {"B3": "  "}

    service._sockets["T1"] = Blank()
    assert service._dm_channel_name(dm) is None


def test_deliver_drops_without_an_agent_and_swallows_submit_errors(
    service: ConnectorService,
) -> None:
    service._deliver("s1", message(), first_message=False)

    class Agent:
        def __init__(self) -> None:
            self.errors: list[BaseException] = [
                SessionBusyError("busy"),
                KeyError("missing"),
                RuntimeError("boom"),
            ]

        def submit_message(self, **kwargs: object) -> None:
            del kwargs
            raise self.errors.pop(0)

    service.agent_service = Agent()  # type: ignore[assignment]
    for _ in range(3):
        service._deliver("s1", message(channel_id="D1"), first_message=True)


def test_reconcile_returns_when_nothing_is_relaying(
    service: ConnectorService, store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_cloud(monkeypatch, key="sk-test")
    store.upsert_slack_workspace(team_id="T1", mode="socket", bot_token="xoxb-1", app_token="xapp-1")
    run(service.reconcile_fastfold_auth())
    assert service._relay is None


def test_reconcile_restarts_relay_workspaces_after_the_key_returns(
    service: ConnectorService, store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_cloud(monkeypatch, key="sk-test")
    for team_id in ("Tlive", "Tstart", "Tbad"):
        store.upsert_slack_workspace(team_id=team_id, mode="relay", bot_token="xoxb-1")
    service._sockets["Tlive"] = SimpleNamespace(connected=True)
    service._relay_state = "live"
    started: list[str] = []

    async def restart(workspace: Any) -> None:
        if workspace.team_id == "Tbad":
            raise RuntimeError("relay down")
        started.append(workspace.team_id)

    service._start_relay_workspace = restart  # type: ignore[method-assign]
    run(service.reconcile_fastfold_auth())
    assert started == ["Tstart"]


def test_status_live_flag_follows_enabled_state_and_the_cloud_key(
    service: ConnectorService, store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_cloud(monkeypatch, key="sk-test")
    store.upsert_slack_workspace(team_id="Tsock", mode="socket", team_name="Socket")
    store.upsert_slack_workspace(team_id="Trelay", mode="relay", team_name="Relay")
    service._sockets["Tsock"] = SimpleNamespace(connected=True)
    service._sockets["Trelay"] = SimpleNamespace(connected=True)
    service._relay_state = "live"
    service._relay_detail = "connected"

    status = service.status()
    by_id = {item.team_id: item for item in status.workspaces}
    assert status.mode == "socket"
    assert status.relay_state == "live"
    assert status.relay_detail == "connected"
    assert by_id["Tsock"].live is True
    assert by_id["Trelay"].live is True

    store.set_slack_workspace_flags("Tsock", enabled=False)
    store.set_slack_workspace_flags("Trelay", enabled=False)
    paused = {item.team_id: item for item in service.status().workspaces}
    assert paused["Tsock"].live is False
    assert paused["Trelay"].live is False

    store.set_slack_workspace_flags("Trelay", enabled=True)
    patch_cloud(monkeypatch, key="")
    signed_out = service.status()
    relay = next(item for item in signed_out.workspaces if item.team_id == "Trelay")
    assert signed_out.relay_state == "signed_out"
    assert relay.live is False
    assert "Fastfold" in (signed_out.relay_detail or "")


def test_sites_json_upload_and_ready_check_are_mocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "site.zip"
    artifact.write_bytes(b"PK\x03\x04site")
    client = FastFoldSitesClient(
        api_key="site-key",
        endpoint="https://api.example/v1/",
        request_timeout=5,
    )
    calls: list[tuple[str, str, bytes | None, float | None]] = []

    def urlopen(request: urllib.request.Request, timeout: float | None = None) -> _HTTPResponse:
        body = request.data if isinstance(request.data, bytes) else None
        calls.append((request.full_url, request.get_method(), body, timeout))
        if request.full_url.endswith("/denied"):
            raise _http_error(request.full_url, 403, b"nope")
        if request.full_url.endswith("/down"):
            raise urllib.error.URLError("offline")
        if request.full_url.endswith("/list"):
            return _HTTPResponse(b"[1, 2]")
        if request.full_url.endswith("/empty"):
            return _HTTPResponse(b"")
        if request.full_url.endswith("/missing"):
            raise _http_error(request.full_url, 404, b"missing")
        if request.full_url.endswith("/forbidden"):
            raise _http_error(request.full_url, 401, b"no")
        if request.full_url.endswith("/weird"):
            return _HTTPResponse(b"", status=202)
        if request.full_url.endswith("/upload-fail"):
            raise _http_error(request.full_url, 400, b"rejected")
        if "upload" in request.full_url:
            assert body is not None
            assert b'name="key"' in body
            assert b"PK\x03\x04site" in body
            return _HTTPResponse(b"", status=204)
        return _HTTPResponse(b'{"ok": true}')

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    assert client._json("GET", "/empty") == {}
    assert client._json("POST", "/sites", {"name": "Example"}) == {"ok": True}
    with pytest.raises(RuntimeError, match="HTTP 403"):
        client._json("GET", "/denied")
    with pytest.raises(RuntimeError, match="Could not reach"):
        client._json("GET", "/down")
    with pytest.raises(RuntimeError, match="invalid response"):
        client._json("GET", "/list")

    client._upload(
        artifact,
        {"url": "https://uploads.example/upload", "fields": {"key": "abc", "policy": "p"}},
    )
    with pytest.raises(RuntimeError, match="invalid upload"):
        client._upload(artifact, {})
    with pytest.raises(RuntimeError, match="invalid upload"):
        client._upload(artifact, {"url": "https://uploads.example/upload", "fields": "nope"})
    with pytest.raises(RuntimeError, match="HTTP 202"):
        client._upload(artifact, {"url": "https://uploads.example/weird", "fields": {"key": "abc"}})
    with pytest.raises(RuntimeError, match="HTTP 400"):
        client._upload(
            artifact, {"url": "https://uploads.example/upload-fail", "fields": {"key": "abc"}}
        )

    assert client._public_url_ready("https://sites.example/ok") is True
    assert client._public_url_ready("https://sites.example/missing") is False
    assert client._public_url_ready("https://sites.example/down") is False
    with pytest.raises(RuntimeError, match="unexpected HTTP 401"):
        client._public_url_ready("https://sites.example/forbidden")

    json_calls = [call for call in calls if call[0].startswith("https://api.example")]
    assert json_calls[0][2] is None
    assert json_calls[1][2] == b'{"name": "Example"}'
    assert client.endpoint == "https://api.example/v1"


def test_publish_requires_a_key_and_complete_payloads(tmp_path: Path) -> None:
    artifact = tmp_path / "site.zip"
    artifact.write_bytes(b"PK")
    client = FastFoldSitesClient(api_key="temp", endpoint="https://api.example/v1")
    client.api_key = ""
    with pytest.raises(ValueError, match="FASTFOLD_API_KEY"):
        client.publish(
            artifact=artifact,
            name="Example",
            local_site_id="local-1",
            content_sha256="abc",
            expanded_size_bytes=4,
            file_count=1,
        )

    client.api_key = "k"

    def publish_with(responses: list[dict[str, Any]]) -> None:
        queue = list(responses)

        def fake_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict:
            del method, path, payload
            if not queue:
                raise AssertionError("unexpected sites call")
            return queue.pop(0)

        client._json = fake_json  # type: ignore[method-assign]
        client._upload = lambda artifact, upload: None  # type: ignore[method-assign, assignment]
        client.publish(
            artifact=artifact,
            name="Example",
            local_site_id="local-1",
            content_sha256="abc",
            expanded_size_bytes=4,
            file_count=1,
        )

    with pytest.raises(RuntimeError, match="site id"):
        publish_with([{"id": "  "}])
    with pytest.raises(RuntimeError, match="upload details"):
        publish_with([{"id": "site-1"}, {"deployment": "no", "upload": None}])
    with pytest.raises(RuntimeError, match="deployment id"):
        publish_with(
            [
                {"id": "site-1"},
                {"deployment": {"id": ""}, "upload": {"url": "https://up", "fields": {}}},
            ]
        )


def test_publish_patch_failure_and_missing_url(tmp_path: Path) -> None:
    artifact = tmp_path / "site.zip"
    artifact.write_bytes(b"PK")
    client = FastFoldSitesClient(
        api_key="k", endpoint="https://api.example/v1", wait_timeout=30, ready_timeout=30
    )
    recorded: list[tuple[str, str, object]] = []
    get_status = {"value": "failed"}

    def fake_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict:
        recorded.append((method, path, payload))
        if method == "PATCH" and payload == {"name": "Named"}:
            return {"id": ""}
        if method == "PATCH":
            return {"id": "cloud-1"}
        if method == "POST" and path == "/sites":
            return {"id": "site-1"}
        if method == "POST" and path.endswith("/deployments"):
            return {
                "deployment": {"id": "dep-1"},
                "upload": {"url": "https://up", "fields": {"key": "k"}},
            }
        if path.endswith("/finalize"):
            return {}
        if method == "GET" and get_status["value"] == "failed":
            return {"status": "failed", "errorMessage": "build blew up"}
        if method == "GET":
            return {"status": "succeeded"}
        raise AssertionError((method, path, payload))

    uploaded: list[Path] = []

    def fake_upload(artifact_path: Path, upload: dict[str, Any]) -> None:
        del upload
        uploaded.append(artifact_path)

    client._json = fake_json  # type: ignore[method-assign]
    client._upload = fake_upload  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="site id"):
        client.publish(
            artifact=artifact,
            name="Named",
            local_site_id="local-1",
            content_sha256="abc",
            expanded_size_bytes=4,
            file_count=1,
            cloud_site_id="cloud-1",
        )
    assert recorded[0] == ("PATCH", "/sites/cloud-1", {"name": "Named"})

    recorded.clear()
    with pytest.raises(RuntimeError, match="build blew up"):
        client.publish(
            artifact=artifact,
            name="Docs",
            local_site_id="local-1",
            content_sha256="abc",
            expanded_size_bytes=4,
            file_count=1,
            slug="docs",
            cloud_site_id="cloud-1",
        )
    assert recorded[0] == ("PATCH", "/sites/cloud-1", {"name": "Docs", "slug": "docs"})
    assert uploaded == [artifact]

    recorded.clear()
    uploaded.clear()
    get_status["value"] = "succeeded"
    with pytest.raises(RuntimeError, match="did not include a URL"):
        client.publish(
            artifact=artifact,
            name="Example",
            local_site_id="local-1",
            content_sha256="abc",
            expanded_size_bytes=4,
            file_count=1,
            slug=None,
        )
    assert recorded[0][0] == "POST"
    assert uploaded == [artifact]


def test_delete_requires_a_key_and_calls_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FastFoldSitesClient(api_key="temp", endpoint="https://api.example/v1")
    client.api_key = ""
    with pytest.raises(ValueError, match="FASTFOLD_API_KEY"):
        client.delete("site-1")

    client.api_key = "k"
    seen: dict[str, object] = {}

    def fake_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict:
        seen["call"] = (method, path, payload)
        return {}

    monkeypatch.setattr(client, "_json", fake_json)
    client.delete("site-1")
    assert seen["call"] == ("DELETE", "/sites/site-1", None)
