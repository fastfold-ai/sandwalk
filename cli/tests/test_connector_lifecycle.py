"""Slack connector lifecycle, inbound routing, and status without a live socket."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock

from agent_server.connectors.gateway import InboundMessage, RouteDecision
from agent_server.connectors.service import ConnectorService
from agent_server.models.connectors import SlackParkedMessage, SlackWorkspace


def _svc(store=None):
    return ConnectorService(store or MagicMock())


def _ws(team_id="T1", mode="socket", enabled=True):
    now = datetime.now(UTC)
    return SlackWorkspace(
        team_id=team_id,
        mode=mode,
        enabled=enabled,
        created_at=now,
        updated_at=now,
    )


def _message():
    return InboundMessage(
        team_id="T1",
        channel_id="C1",
        user_id="U1",
        text="hello",
        ts="1.0",
        thread_ts="1.0",
        user_name="Ada",
    )


def test_start_stop_and_connect_rules(monkeypatch):
    store = MagicMock()
    disabled = _ws("off", enabled=False)
    enabled = _ws()
    store.list_slack_workspaces.return_value = [disabled, enabled]
    svc = _svc(store)
    monkeypatch.setattr("agent_server.connectors.service._is_slack_skipped", lambda: False)

    async def _boom(workspace):
        raise RuntimeError("socket")

    svc._start_workspace = _boom
    asyncio.run(svc.start())
    assert svc._started is True

    async def _cancel_me():
        await asyncio.sleep(30)

    task = asyncio.get_event_loop().create_task(_cancel_me()) if False else None

    async def _exercise():
        hanging = asyncio.create_task(asyncio.sleep(30))
        svc._progress_tasks.add(hanging)
        adapter = MagicMock()
        adapter.disconnect.side_effect = RuntimeError("down")
        svc._sockets["T1"] = adapter
        relay = MagicMock()
        relay.stop.side_effect = RuntimeError("relay")
        svc._relay = relay
        await svc.stop()

    asyncio.run(_exercise())
    assert svc._relay_state == "off"
    assert svc._sockets == {}

    async def _connect():
        try:
            await svc.connect_socket_mode(bot_token="", app_token="xapp-1")
            raise AssertionError("expected token error")
        except ValueError:
            pass
        try:
            await svc.connect_socket_mode(bot_token="xoxb-1", app_token="nope")
            raise AssertionError("expected app token error")
        except ValueError:
            pass

    asyncio.run(_connect())
    monkeypatch.setattr("agent_server.connectors.service._require_slack_sdk", lambda: None)
    store.upsert_slack_workspace.return_value = enabled
    store.get_slack_workspace.return_value = enabled

    async def _start(workspace):
        svc.started_team = workspace.team_id

    svc._start_workspace = _start

    async def _resolve(bot):
        return "T9"

    svc._resolve_team_id = _resolve
    connected = asyncio.run(svc.connect_socket_mode(bot_token="xoxb-1", app_token="xapp-1"))
    assert connected.team_id == "T1"


def test_enable_disconnect_inbound_and_status(monkeypatch):
    store = MagicMock()
    workspace = _ws(mode="relay")
    store.set_slack_workspace_flags.return_value = None
    svc = _svc(store)

    async def _missing():
        try:
            await svc.set_workspace_enabled("T1", enabled=False)
            raise AssertionError("expected missing workspace")
        except KeyError:
            pass

    asyncio.run(_missing())
    store.set_slack_workspace_flags.return_value = workspace
    store.get_slack_workspace.return_value = workspace
    stopped = {}

    async def _stop(team_id):
        stopped["id"] = team_id

    async def _start(workspace):
        stopped["started"] = workspace.team_id

    svc._stop_workspace = _stop
    svc._start_workspace = _start
    monkeypatch.setattr("agent_server.connectors.service.clear_directory_cache", lambda team_id: None)
    store.delete_slack_workspace.return_value = True
    assert asyncio.run(svc.set_workspace_enabled("T1", enabled=False)).team_id == "T1"
    assert stopped["id"] == "T1"
    assert asyncio.run(svc.set_workspace_enabled("T1", enabled=True)).team_id == "T1"
    assert asyncio.run(svc.disconnect_workspace("T1")) is True

    svc.gateway.route = lambda message: RouteDecision("ignore", "nope")
    asyncio.run(svc._on_inbound(_message()))
    svc.gateway.route = lambda message: RouteDecision("park", "stranger", thread_target="slack:T1/C1:1.000100")
    asyncio.run(svc._on_inbound(_message()))
    store.park_slack_message.assert_called()
    svc._spawn_session = lambda message, decision: "sess"
    tracked = {}
    svc._track_progress = lambda message, ids: tracked.update(ids=ids)
    svc.gateway.route = lambda message: RouteDecision("spawn", "new")
    asyncio.run(svc._on_inbound(_message()))
    assert tracked["ids"] == ["sess"]
    delivered = {}
    svc._deliver = lambda session_id, message, first_message: delivered.update(id=session_id)
    svc.gateway.route = lambda message: RouteDecision("deliver", "thread", session_ids=["s1", "s2"])
    asyncio.run(svc._on_inbound(_message()))
    assert delivered["id"] == "s2"
    assert tracked["ids"] == ["s1", "s2"]

    monkeypatch.setattr("agent_server.account_service.helpers.api_key", lambda: "")
    monkeypatch.setattr("agent_server.account_service.helpers.cloud_base_url", lambda: "https://cloud.example")
    try:
        asyncio.run(svc.start_one_click())
        raise AssertionError("expected missing key")
    except ValueError as exc:
        assert "Fastfold" in str(exc)

    monkeypatch.setattr("agent_server.account_service.helpers.api_key", lambda: "key")
    monkeypatch.setattr(
        "agent_server.connectors.service._cloud_request",
        lambda *args: (None, "rejected"),
    )
    try:
        asyncio.run(svc.start_one_click(return_to="https://lab.example/oauth/callback"))
        raise AssertionError("expected cloud error")
    except ValueError:
        pass
    monkeypatch.setattr(
        "agent_server.connectors.service._cloud_request",
        lambda *args: ({}, None),
    )
    try:
        asyncio.run(svc.start_one_click())
        raise AssertionError("expected missing url")
    except ValueError:
        pass
    monkeypatch.setattr(
        "agent_server.connectors.service._cloud_request",
        lambda *args: ({"auth_url": "https://slack.example/install"}, None),
    )
    assert asyncio.run(svc.start_one_click()).startswith("https://slack.example")

    socket = _ws()
    relay = _ws("T2", mode="relay")
    store.list_slack_workspaces.return_value = [socket, relay]
    svc._sockets["T1"] = MagicMock(connected=True)
    body = svc.status()
    assert body.mode == "socket"
    assert svc.socket_connected("T1") is True
    assert svc.socket_connected("missing") is False
    store.list_slack_workspaces.return_value = [relay]
    monkeypatch.setattr("agent_server.account_service.helpers.api_key", lambda: "")
    signed_out = svc.status()
    assert signed_out.relay_state == "signed_out"
    assert signed_out.workspaces[0].live is False


def test_progress_parked_and_idle(monkeypatch):
    store = MagicMock()
    svc = _svc(store)
    message = _message()
    adapter = MagicMock()
    adapter.assistant = None

    async def _reaction(**kwargs):
        adapter.calls.append(kwargs)

    adapter.calls = []
    adapter.set_reaction = _reaction
    svc._sockets["T1"] = adapter
    store.get_session.return_value = MagicMock(status="idle")
    base = 1_000.0
    calls = {"n": 0}

    def _clock():
        calls["n"] += 1
        return base if calls["n"] < 4 else base + 20

    monkeypatch.setattr("agent_server.connectors.service.time.monotonic", _clock)
    monkeypatch.setattr("agent_server.connectors.service.asyncio.sleep", lambda seconds: _asleep())

    async def _asleep():
        return None

    assert asyncio.run(svc._run_progress(message, ["s1"])) is None
    assert adapter.calls[-1]["add"] == "white_check_mark"

    store.get_session.return_value = None
    assert asyncio.run(svc._wait_for_idle("missing", timeout=1)) is False

    parked = SlackParkedMessage(
        id="p1",
        team_id="T1",
        channel="not a target",
        thread_target=None,
        slack_user_id="U1",
        user_name="Ada",
        text="hi",
        created_at=datetime.now(UTC),
    )
    assert ConnectorService._inbound_from_parked(parked) is None
    parked = SlackParkedMessage(
        id="p2",
        team_id="T1",
        channel="slack:T1/C1:1712000000.000100",
        thread_target="slack:T1/C1:1712000000.000100",
        slack_user_id="U1",
        user_name="Ada",
        text="hi",
        created_at=datetime.now(UTC),
    )
    replay = ConnectorService._inbound_from_parked(parked)
    assert replay is not None and replay.ts == "1712000000.000100"
    store.list_slack_parked_messages.return_value = []
    assert asyncio.run(svc.allow_parked("missing")) is False
    store.list_slack_parked_messages.return_value = [parked]
    seen = {}
    svc._on_inbound = lambda message: seen.setdefault("text", message.text) or _done()

    async def _done():
        return None

    async def _on(message):
        seen["text"] = message.text

    svc._on_inbound = _on
    assert asyncio.run(svc.allow_parked("p2")) is True
    assert seen["text"] == "hi"

    relay = MagicMock()
    relay.teams = set()

    async def _relay_stop():
        relay.stopped = True

    relay.stop = _relay_stop
    svc._relay = relay
    svc._sockets["T1"] = adapter

    async def _disc():
        raise RuntimeError("socket")

    adapter.disconnect = _disc
    asyncio.run(svc._stop_workspace("T1"))
    assert svc._relay is None
