"""Cover relay and Socket Mode branches the other Slack tests leave closed.

Sockets, Web API clients, and sleeps are fakes. Nothing here dials Slack or
FastFold Cloud.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent_server.connectors.directory import SlackChannelEntry, SlackPerson
from agent_server.connectors.gateway import InboundMessage
from agent_server.connectors.slack_relay import (
    _BACKOFF_MAX,
    _BACKOFF_START,
    _OPEN_TIMEOUT,
    SlackRelayClient,
    SlackRelayWorkspace,
    _relay_url,
    _team_id_from_envelope,
)
from agent_server.connectors.slack_socket import SlackSocketAdapter

Inbound = Callable[[InboundMessage], Awaitable[None]]


def run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


async def _noop(_message: InboundMessage) -> None:
    return None


def workspace(**overrides: object) -> SlackRelayWorkspace:
    space = SlackRelayWorkspace(
        team_id=str(overrides.get("team_id", "T1")),
        bot_token=str(overrides.get("bot_token", "xoxb-test")),
        bot_user_id=overrides.get("bot_user_id", "B1"),  # type: ignore[arg-type]
    )
    space.user_names = {"U1": "Ada"}
    space.channel_names = {"C1": "lab"}
    return space


def relay_of(
    space: SlackRelayWorkspace | None = None,
    *,
    on_message: Inbound | None = None,
    on_state: Callable[[str, str | None], None] | None = None,
) -> SlackRelayClient:
    client = SlackRelayClient(
        base_url="https://api.test",
        api_key="test-key",
        on_message=on_message or _noop,
        on_state=on_state,
    )
    if space is not None:
        client.add_workspace(space)
    return client


def socket_adapter(on_message: Inbound = _noop, **kwargs: object) -> SlackSocketAdapter:
    return SlackSocketAdapter(
        team_id="T1",
        bot_token="xoxb-test",
        app_token="xapp-test",
        on_message=on_message,
        **kwargs,  # type: ignore[arg-type]
    )


class _ReactionWeb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def reactions_remove(self, **kwargs: str) -> None:
        name = kwargs["name"]
        self.calls.append(("remove", name))
        if name == "explode":
            raise RuntimeError("remove failed")

    async def reactions_add(self, **kwargs: str) -> None:
        name = kwargs["name"]
        self.calls.append(("add", name))
        if name == "eyes":
            raise RuntimeError("already_reacted")
        if name == "boom":
            raise RuntimeError("missing_scope")


class _FrameSocket:
    def __init__(self, frames: list[str]) -> None:
        self._frames = list(frames)

    def __aiter__(self) -> _FrameSocket:
        return self

    async def __anext__(self) -> str:
        if not self._frames:
            raise StopAsyncIteration
        return self._frames.pop(0)


class _Connect:
    def __init__(self, frames: list[str]) -> None:
        self._socket = _FrameSocket(frames)

    async def __aenter__(self) -> _FrameSocket:
        return self._socket

    async def __aexit__(self, *_exc: object) -> bool:
        return False


def _mention() -> dict[str, str]:
    return {
        "type": "app_mention",
        "user": "U1",
        "channel": "C1",
        "ts": "1.1",
        "text": "<@B1> hi",
    }


# --- relay helpers and workspace surface ------------------------------------


def test_relay_url_passes_a_non_http_base_through() -> None:
    assert _relay_url("wss://cloud.example/") == "wss://cloud.example/v1/slack/relay"


def test_team_id_falls_back_to_the_event_when_authorizations_are_unusable() -> None:
    event = {"event": {"team": "T-event"}}
    assert _team_id_from_envelope({"authorizations": ["nope"], **event}) == "T-event"
    assert _team_id_from_envelope({"authorizations": [{"team_id": "  "}], **event}) == "T-event"
    assert _team_id_from_envelope(event) == "T-event"
    assert _team_id_from_envelope({"event": {"team": "  "}}) is None


def test_web_client_is_built_once_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_API_URL", "http://slack.test/api/")
    created: list[tuple[str, str]] = []

    class Marker:
        def __init__(self, token: str, base_url: str) -> None:
            created.append((token, base_url))

    space = workspace()
    with patch("slack_sdk.web.async_client.AsyncWebClient", Marker):
        first = space._web()
        second = space._web()
    assert first is second
    assert created == [("xoxb-test", "http://slack.test/api/")]


def test_load_directory_failure_is_swallowed() -> None:
    async def fetch(*_args: object, **_kwargs: object) -> tuple[list[object], list[object]]:
        raise RuntimeError("users.list down")

    space = workspace()
    space.user_names = {}
    with patch("agent_server.connectors.directory.fetch_directory", fetch):
        run(space.load_directory())
    assert space.user_names == {}


def test_load_directory_skips_bot_name_when_it_is_blank() -> None:
    async def fetch(*_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        return (
            [SlackPerson(id="U1", name="Ada", avatar_url="https://cdn.example/a.png")],
            [SlackChannelEntry(id="C1", name="lab")],
        )

    space = workspace()
    space.user_names = {}
    space._bot_name = ""
    with patch("agent_server.connectors.directory.fetch_directory", fetch):
        run(space.load_directory())
    assert space.user_names == {"U1": "Ada"}
    assert "B1" not in space.user_names
    assert space.channel_names["C1"] == "lab"


def test_set_reaction_is_best_effort() -> None:
    space = workspace()
    web = _ReactionWeb()

    async def exercise() -> None:
        # Missing target returns before a client exists.
        await space.set_reaction(channel_id="", ts="", add="eyes", remove="white_check_mark")
        assert space._client is None
        space._client = web
        await space.set_reaction(channel_id="C1", ts="1.1", add=None, remove="white_check_mark")
        await space.set_reaction(channel_id="C1", ts="1.1", add="ok", remove="white_check_mark")
        await space.set_reaction(channel_id="C1", ts="1.1", add="eyes", remove="explode")
        await space.set_reaction(channel_id="C1", ts="1.1", add="boom")

    run(exercise())
    assert ("remove", "white_check_mark") in web.calls
    assert ("add", "boom") in web.calls
    assert ("add", "eyes") in web.calls


def test_publish_home_requires_a_user_and_fans_out() -> None:
    class Web:
        def __init__(self) -> None:
            self.users: list[str] = []

        async def views_publish(self, **kwargs: object) -> dict[str, bool]:
            self.users.append(str(kwargs["user_id"]))
            return {"ok": True}

    space = workspace()
    web = Web()
    space._client = web

    async def exercise() -> None:
        assert await space.publish_home("") is False
        await space.publish_home_for_users(["U1", "U2"])

    run(exercise())
    assert web.users == ["U1", "U2"]


def test_assistant_event_edges_return_without_a_web_call() -> None:
    space = workspace()

    async def exercise() -> None:
        await space.on_assistant_event({"type": "app_home_opened", "tab": "home"})
        await space.on_assistant_event({"type": "app_home_opened", "tab": "messages"})

    run(exercise())
    assert space._client is None
    assert space._assistant is None


def test_remove_workspace_and_state_without_a_callback() -> None:
    space = workspace()
    client = relay_of(space)
    client.remove_workspace("T1")
    client.remove_workspace("T-missing")
    assert client.get("T1") is None
    client._state("live", None)


# --- relay session loop -------------------------------------------------------


def test_start_is_idempotent_and_stop_cancels_the_run() -> None:
    states: list[tuple[str, str | None]] = []
    client = relay_of(workspace(), on_state=lambda state, detail: states.append((state, detail)))
    entered = asyncio.Event()

    async def session() -> None:
        entered.set()
        await asyncio.Event().wait()

    async def exercise() -> None:
        with patch.object(client, "_session", session):
            await client.start()
            first = client._task
            await client.start()
            assert client._task is first
            await entered.wait()
            await client.stop()
        assert client._task is None
        assert client.teams == []
        assert client.connected is False
        assert states[-1] == ("off", None)

    run(exercise())


def test_stop_swallows_a_failed_run_task() -> None:
    client = relay_of(workspace())

    async def died() -> None:
        raise RuntimeError("relay task died")

    async def exercise() -> None:
        client._task = asyncio.create_task(died())
        done = asyncio.Event()

        def mark_done(_task: asyncio.Task[None]) -> None:
            done.set()

        client._task.add_done_callback(mark_done)
        await done.wait()
        await client.stop()
        assert client._task is None

    run(exercise())


def test_run_reports_auth_failure_then_resets_backoff_on_success() -> None:
    states: list[tuple[str, str | None]] = []
    client = relay_of(workspace(), on_state=lambda state, detail: states.append((state, detail)))
    client._set_live(True)
    steps = {"n": 0}
    sleeps: list[float] = []

    async def session() -> None:
        steps["n"] += 1
        if steps["n"] == 1:
            raise RuntimeError("HTTP 401 Unauthorized")
        client._closing = True

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    async def exercise() -> None:
        with (
            patch.object(client, "_session", session),
            patch("agent_server.connectors.slack_relay.asyncio.sleep", sleep),
        ):
            await client._run()

    run(exercise())
    assert states == [("auth_expired", "FastFold rejected the API key.")]
    assert sleeps == [_BACKOFF_START]
    assert client.connected is False


def test_run_backs_off_and_truncates_a_long_disconnect_reason() -> None:
    states: list[tuple[str, str | None]] = []
    client = relay_of(on_state=lambda state, detail: states.append((state, detail)))
    sleeps: list[float] = []

    async def session() -> None:
        raise RuntimeError("x" * 250)

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) == 2:
            client._closing = True

    async def exercise() -> None:
        with (
            patch.object(client, "_session", session),
            patch("agent_server.connectors.slack_relay.asyncio.sleep", sleep),
        ):
            await client._run()

    run(exercise())
    assert [state for state, _detail in states] == ["reconnecting", "reconnecting"]
    assert states[0][1] is not None
    assert len(states[0][1] or "") == 200
    assert sleeps == [_BACKOFF_START, min(_BACKOFF_START * 2, _BACKOFF_MAX)]


def test_run_returns_when_shutdown_starts_during_the_failure() -> None:
    client = relay_of()
    sleeps: list[float] = []

    async def session() -> None:
        client._closing = True
        raise RuntimeError("going away")

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    async def exercise() -> None:
        with (
            patch.object(client, "_session", session),
            patch("agent_server.connectors.slack_relay.asyncio.sleep", sleep),
        ):
            await client._run()

    run(exercise())
    assert sleeps == []


def test_run_returns_when_the_state_callback_requests_close() -> None:
    client = relay_of()
    sleeps: list[float] = []

    def on_state(_state: str, _detail: str | None) -> None:
        client._closing = True

    client._on_state = on_state

    async def session() -> None:
        raise RuntimeError("connection reset by peer")

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    async def exercise() -> None:
        with (
            patch.object(client, "_session", session),
            patch("agent_server.connectors.slack_relay.asyncio.sleep", sleep),
        ):
            await client._run()

    run(exercise())
    assert sleeps == []
    assert client.connected is False


def test_run_reraises_cancellation() -> None:
    client = relay_of()

    async def session() -> None:
        raise asyncio.CancelledError

    async def exercise() -> None:
        with patch.object(client, "_session", session):
            with pytest.raises(asyncio.CancelledError):
                await client._run()

    run(exercise())


def test_session_reads_frames_with_additional_headers() -> None:
    space = workspace()
    client = relay_of(space)
    calls: list[dict[str, object]] = []

    def connect(url: str, **kwargs: object) -> _Connect:
        calls.append({"url": url, **kwargs})
        if "additional_headers" not in kwargs:
            raise AssertionError("expected additional_headers")
        return _Connect(['{"type":"relay.ready"}'])

    async def exercise() -> None:
        with patch("websockets.connect", connect):
            await client._session()

    run(exercise())
    assert calls[0]["url"] == "wss://api.test/v1/slack/relay"
    assert calls[0]["open_timeout"] == _OPEN_TIMEOUT
    headers = calls[0]["additional_headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer test-key"
    assert client.connected is True
    assert space.connected is True


def test_session_falls_back_to_extra_headers() -> None:
    client = relay_of(workspace())
    calls: list[str] = []

    def connect(_url: str, **kwargs: object) -> _Connect:
        if "additional_headers" in kwargs:
            calls.append("additional")
            raise TypeError("websockets renamed the header argument")
        calls.append("extra")
        assert "extra_headers" in kwargs
        return _Connect(['{"type":"relay.ready"}'])

    async def exercise() -> None:
        with patch("websockets.connect", connect):
            await client._session()

    run(exercise())
    assert calls == ["additional", "extra"]
    assert client.connected is True


def test_handle_frame_ignores_a_non_dict_event() -> None:
    seen: list[InboundMessage] = []

    async def on_message(message: InboundMessage) -> None:
        seen.append(message)

    client = relay_of(workspace(), on_message=on_message)
    payload = {"type": "event_callback", "team_id": "T1", "event": "nope"}
    run(client._handle_frame(json.dumps(payload)))
    assert seen == []


def test_assistant_handler_failure_does_not_escape() -> None:
    space = workspace()

    async def boom(_event: dict[str, str]) -> None:
        raise RuntimeError("assistant failed")

    space.on_assistant_event = boom  # type: ignore[method-assign]
    client = relay_of(space)
    payload = {
        "type": "event_callback",
        "team_id": "T1",
        "event": {"type": "app_home_opened", "tab": "home", "user": "U1"},
    }
    run(client._handle_frame(json.dumps(payload)))


def test_unknown_sender_refreshes_the_directory() -> None:
    space = workspace()
    space.user_names = {}
    refreshed: list[bool] = []

    async def load_directory(*, force: bool = False) -> None:
        refreshed.append(force)

    space.load_directory = load_directory  # type: ignore[method-assign]
    seen: list[InboundMessage] = []

    async def on_message(message: InboundMessage) -> None:
        seen.append(message)

    client = relay_of(space, on_message=on_message)
    payload = {"type": "event_callback", "team_id": "T1", "event": _mention()}
    run(client._handle_frame(json.dumps(payload)))
    assert refreshed == [True]
    assert len(seen) == 1


# --- socket mode --------------------------------------------------------------


def test_bot_user_id_property() -> None:
    subject = socket_adapter()
    assert subject.bot_user_id is None
    subject._bot_user_id = "B1"
    assert subject.bot_user_id == "B1"


def test_connected_swallows_probe_errors() -> None:
    class Boom:
        def is_connected(self) -> bool:
            raise RuntimeError("probe failed")

    subject = socket_adapter()
    subject._socket = SimpleNamespace(client=Boom())
    assert subject.connected is False


def test_async_connected_probe() -> None:
    class Probe:
        def __init__(self, value: bool) -> None:
            self.value = value

        def is_connected(self) -> Awaitable[bool]:
            async def inner() -> bool:
                return self.value

            return inner()

    class Boom:
        def is_connected(self) -> bool:
            raise RuntimeError("probe failed")

    subject = socket_adapter()

    async def exercise() -> None:
        subject._socket = SimpleNamespace(client=None)
        assert await subject._connected() is False
        subject._socket = SimpleNamespace(client=Probe(True))
        assert await subject._connected() is True
        subject._socket = SimpleNamespace(client=Probe(False))
        assert await subject._connected() is False
        subject._socket = SimpleNamespace(client=Boom())
        assert await subject._connected() is False

    run(exercise())


def test_connect_registers_handlers_and_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_API_URL", "http://slack.test/api/")
    seen: list[InboundMessage] = []
    apps: list[FakeApp] = []
    webs: list[FakeWeb] = []
    handlers: list[FakeHandler] = []

    class FakeWeb:
        def __init__(self, token: str, base_url: str) -> None:
            self.token = token
            self.base_url = base_url
            webs.append(self)

        async def auth_test(self) -> dict[str, str]:
            return {"user_id": "B1", "user": "sandwalk"}

    class FakeApp:
        def __init__(self, client: FakeWeb) -> None:
            self.client = client
            self.events: dict[str, Callable[..., Awaitable[None]]] = {}
            apps.append(self)

        def event(self, name: str) -> Callable[[Callable[..., Awaitable[None]]], Callable[..., Awaitable[None]]]:
            def deco(fn: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
                self.events[name] = fn
                return fn

            return deco

    class FakeSocketClient:
        def __init__(self) -> None:
            self.auto_reconnect_enabled = True

        def is_connected(self) -> bool:
            return True

    class FakeHandler:
        def __init__(self, app: FakeApp, app_token: str) -> None:
            self.app = app
            self.app_token = app_token
            self.client = FakeSocketClient()
            self.closed = False
            handlers.append(self)

        async def start_async(self) -> None:
            await asyncio.Event().wait()

        async def close_async(self) -> None:
            self.closed = True

    async def fetch(*_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        return (
            [SlackPerson(id="U1", name="Ada", avatar_url="https://cdn.example/a.png")],
            [SlackChannelEntry(id="C1", name="lab")],
        )

    async def parked(_delay: float) -> None:
        await asyncio.Event().wait()

    async def on_message(message: InboundMessage) -> None:
        seen.append(message)

    subject = socket_adapter(on_message, watchdog_interval=3600, auto_reconnect=False)

    async def exercise() -> None:
        with (
            patch("slack_sdk.web.async_client.AsyncWebClient", FakeWeb),
            patch("slack_bolt.async_app.AsyncApp", FakeApp),
            patch(
                "slack_bolt.adapter.socket_mode.async_handler.AsyncSocketModeHandler",
                FakeHandler,
            ),
            patch("agent_server.connectors.directory.fetch_directory", fetch),
            patch("agent_server.connectors.slack_socket.asyncio.sleep", parked),
        ):
            try:
                assert await subject.connect() is True
                event = _mention()
                await apps[0].events["message"](event, None)
                await apps[0].events["app_mention"](event, None)
                assert subject.bot_user_id == "B1"
                assert subject._user_names["B1"] == "sandwalk"
                assert handlers[0].client.auto_reconnect_enabled is False
                assert webs[0].base_url == "http://slack.test/api/"
                assert len(seen) == 2
            finally:
                await subject.disconnect()
        assert handlers[0].closed is True
        assert subject._socket is None
        assert subject._app is None
        assert subject._task is None
        assert subject._watchdog_task is None

    run(exercise())


def test_connect_returns_false_when_auth_test_fails() -> None:
    class DeadWeb:
        def __init__(self, token: str, base_url: str) -> None:
            self.token = token
            self.base_url = base_url

        async def auth_test(self) -> dict[str, str]:
            raise RuntimeError("invalid_auth")

    class FakeApp:
        def __init__(self, client: DeadWeb) -> None:
            self.client = client

        def event(self, _name: str) -> Callable[[object], object]:
            def deco(fn: object) -> object:
                return fn

            return deco

    subject = socket_adapter()

    async def exercise() -> bool:
        with (
            patch("slack_sdk.web.async_client.AsyncWebClient", DeadWeb),
            patch("slack_bolt.async_app.AsyncApp", FakeApp),
            patch(
                "slack_bolt.adapter.socket_mode.async_handler.AsyncSocketModeHandler",
                lambda *_args, **_kwargs: None,
            ),
        ):
            return await subject.connect()

    assert run(exercise()) is False
    assert subject._task is None
    assert subject._socket is None


def test_disconnect_without_a_socket_is_a_no_op() -> None:
    subject = socket_adapter()
    run(subject.disconnect())
    assert subject._socket is None
    assert subject._app is None


def test_disconnect_swallows_task_and_close_errors() -> None:
    subject = socket_adapter()

    async def died() -> None:
        raise RuntimeError("socket task died")

    class Socket:
        async def close_async(self) -> None:
            raise RuntimeError("close failed")

    async def exercise() -> None:
        subject._watchdog_task = asyncio.create_task(died())
        done = asyncio.Event()

        def mark_done(_task: asyncio.Task[None]) -> None:
            done.set()

        assert subject._watchdog_task is not None
        subject._watchdog_task.add_done_callback(mark_done)
        await done.wait()
        subject._task = None
        subject._socket = Socket()
        subject._app = object()
        await subject.disconnect()

    run(exercise())
    assert subject._task is None
    assert subject._watchdog_task is None
    assert subject._socket is None
    assert subject._app is None


def test_socket_set_reaction_is_best_effort() -> None:
    subject = socket_adapter()
    web = _ReactionWeb()

    async def exercise() -> None:
        await subject.set_reaction(channel_id="C1", ts="1.1", add="eyes")
        subject._app = SimpleNamespace(client=None)
        await subject.set_reaction(channel_id="C1", ts="1.1", add="eyes")
        await subject.set_reaction(channel_id="", ts="", add="eyes")
        subject._app = SimpleNamespace(client=web)
        await subject.set_reaction(channel_id="C1", ts="1.1", add=None, remove="white_check_mark")
        await subject.set_reaction(channel_id="C1", ts="1.1", add="ok", remove="white_check_mark")
        await subject.set_reaction(channel_id="C1", ts="1.1", add="eyes", remove="explode")
        await subject.set_reaction(channel_id="C1", ts="1.1", add="boom")

    run(exercise())
    assert web.calls[0] == ("remove", "white_check_mark")
    assert ("add", "boom") in web.calls


def test_socket_load_directory_failure_is_swallowed() -> None:
    async def fetch(*_args: object, **_kwargs: object) -> tuple[list[object], list[object]]:
        raise RuntimeError("users.list down")

    subject = socket_adapter()
    with patch("agent_server.connectors.directory.fetch_directory", fetch):
        run(subject._load_directory())
    assert subject._user_names == {}
    assert subject._directory_loaded_at == 0.0


def test_socket_load_directory_records_the_bot_name() -> None:
    async def fetch(*_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        return (
            [SlackPerson(id="U1", name="Ada", avatar_url="https://cdn.example/a.png")],
            [SlackChannelEntry(id="C1", name="lab")],
        )

    subject = socket_adapter()
    subject._bot_user_id = "B1"
    subject._bot_name = "sandwalk"
    with patch("agent_server.connectors.directory.fetch_directory", fetch):
        run(subject._load_directory())
    assert subject._user_names["B1"] == "sandwalk"
    assert subject._user_avatars["U1"] == "https://cdn.example/a.png"
    assert subject._channel_names["C1"] == "lab"
    assert subject._directory_loaded_at > 0


def test_ensure_known_waits_out_the_refresh_interval() -> None:
    subject = socket_adapter()
    subject._directory_loaded_at = time.monotonic()

    async def fetch(*_args: object, **_kwargs: object) -> tuple[list[object], list[object]]:
        raise AssertionError("directory refresh should wait")

    with patch("agent_server.connectors.directory.fetch_directory", fetch):
        run(subject._ensure_known({"user": "U-new", "channel": "C-new"}))


def test_handle_event_ignores_a_non_dict() -> None:
    seen: list[InboundMessage] = []

    async def on_message(message: InboundMessage) -> None:
        seen.append(message)

    subject = socket_adapter(on_message)
    run(subject._handle_event("nope"))  # type: ignore[arg-type]
    assert seen == []


def test_watchdog_exits_immediately_when_already_closing() -> None:
    subject = socket_adapter()
    subject._closing = True
    run(subject._watchdog())
    assert subject.reconnects == 0


def test_watchdog_stops_when_the_socket_disappears() -> None:
    subject = socket_adapter()
    subject._socket = SimpleNamespace(client=object())

    async def drop_socket(_delay: float) -> None:
        subject._socket = None

    with patch("agent_server.connectors.slack_socket.asyncio.sleep", drop_socket):
        run(subject._watchdog())
    assert subject.reconnects == 0


def test_watchdog_survives_a_failed_reconnect() -> None:
    class Client:
        def is_connected(self) -> bool:
            return False

        async def connect_to_new_endpoint(self, force: bool = False) -> None:
            raise RuntimeError(f"endpoint down (force={force})")

    subject = socket_adapter()
    subject._socket = SimpleNamespace(client=Client())
    passes = {"n": 0}

    async def sleep_twice(_delay: float) -> None:
        passes["n"] += 1
        if passes["n"] > 1:
            subject._closing = True

    with patch("agent_server.connectors.slack_socket.asyncio.sleep", sleep_twice):
        run(subject._watchdog())
    assert subject.reconnects == 0
