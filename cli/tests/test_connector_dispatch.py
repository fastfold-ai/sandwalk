"""Slack mention → session dispatch, using a real AgentService with a stub runner."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

import pytest

from agent_server.connectors.framing import frame_inbound, spawn_title
from agent_server.connectors.gateway import InboundMessage
from agent_server.connectors.service import ConnectorService
from agent_server.service import AgentService
from agent_server.store import AgentStore

T = TypeVar("T")


def run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AgentStore:
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    store.upsert_slack_workspace(
        team_id="T1", mode="socket", team_name="Acme", bot_user_id="BBOT"
    )
    store.allow_slack_user(team_id="T1", slack_user_id="U1", display_name="Julio")
    return store


@pytest.fixture()
def agent(store: AgentStore, monkeypatch: pytest.MonkeyPatch) -> AgentService:
    service = AgentService(store)

    # Let runs start and complete without invoking a model.
    async def _fake_execute_run(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(service, "_execute_run", _fake_execute_run)
    return service


@pytest.fixture()
def connectors(store: AgentStore, agent: AgentService) -> ConnectorService:
    return ConnectorService(store, agent)


def message(**overrides: object) -> InboundMessage:
    payload: dict[str, object] = {
        "team_id": "T1",
        "channel_id": "C1",
        "user_id": "U1",
        "user_name": "Julio",
        "channel_name": "dev-ops",
        "text": "summarize this thread",
        "ts": "1712000000.000100",
        "mentions_me": True,
    }
    payload.update(overrides)
    return InboundMessage(**payload)  # type: ignore[arg-type]


def test_mention_spawns_a_slack_session(
    store: AgentStore, connectors: ConnectorService
) -> None:
    run(connectors._on_inbound(message()))

    sessions = store.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].source == "slack"
    assert sessions[0].source_label == "#dev-ops · Acme"
    assert sessions[0].title == "summarize this thread"


def test_spawn_records_the_thread_mapping(
    store: AgentStore, connectors: ConnectorService
) -> None:
    run(connectors._on_inbound(message()))

    session_id = store.list_sessions()[0].id
    mapped = store.get_slack_mention_session("slack:T1/C1:1712000000.000100")
    assert mapped == session_id


class _HomeAdapter:
    """Records republish calls the way a SlackRelayWorkspace would receive them."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def publish_home_for_users(self, user_ids: list[str]) -> None:
        self.calls.append(list(user_ids))


def test_spawning_a_session_republishes_app_home(
    store: AgentStore, connectors: ConnectorService
) -> None:
    adapter = _HomeAdapter()
    connectors._sockets["T1"] = adapter

    async def _drive() -> None:
        await connectors._on_inbound(message())
        # Let the fire-and-forget republish task run once.
        await asyncio.sleep(0)

    run(_drive())

    assert adapter.calls == [["U1"]]


def test_republish_is_skipped_for_socket_mode_adapters(
    store: AgentStore, connectors: ConnectorService
) -> None:
    """Socket Mode workspaces have no App Home surface yet — no-op, not an error."""

    class _SocketAdapter:
        pass

    connectors._sockets["T1"] = _SocketAdapter()
    run(connectors._on_inbound(message()))  # must not raise


def test_relay_going_live_republishes_home_for_every_team(
    store: AgentStore, connectors: ConnectorService
) -> None:
    """Status only becomes accurate once the socket actually reports live —
    publishing eagerly right after ``relay.start()`` would show stale state."""
    adapter = _HomeAdapter()
    connectors._sockets["T1"] = adapter

    async def _drive() -> None:
        connectors._set_relay_state("reconnecting", "still trying")
        await asyncio.sleep(0)
        assert adapter.calls == []  # not live yet — no publish

        connectors._set_relay_state("live", None)
        await asyncio.sleep(0)

    run(_drive())

    assert adapter.calls == [["U1"]]


def test_first_message_carries_the_reply_handle(
    store: AgentStore, connectors: ConnectorService
) -> None:
    run(connectors._on_inbound(message()))

    session_id = store.list_sessions()[0].id
    messages = store.list_messages(session_id)
    assert len(messages) == 1
    content = messages[0].content
    assert "reply→slack:T1/C1:1712000000.000100" in content
    assert "slack.send_message" in content
    assert "summarize this thread" in content


def test_second_mention_reuses_the_same_session(
    store: AgentStore, connectors: ConnectorService, agent: AgentService
) -> None:
    run(connectors._on_inbound(message()))
    session_id = store.list_sessions()[0].id

    # Let the first run finish so the session is not busy.
    run(_drain(agent, session_id))

    run(
        connectors._on_inbound(
            message(ts="1712000090.000900", thread_ts="1712000000.000100")
        )
    )

    assert len(store.list_sessions()) == 1
    messages = store.list_messages(session_id)
    assert len(messages) == 2
    # Mentions, follow-ups, and Listening all carry the reply instruction.
    assert "slack.send_message" in messages[0].content
    assert "slack.send_message" in messages[1].content


def test_busy_session_drops_rather_than_crashing(
    store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = AgentService(store)
    connectors = ConnectorService(store, agent)

    async def _drive() -> str:
        release = asyncio.Event()

        async def _blocking_run(**_kwargs: object) -> None:
            await release.wait()

        monkeypatch.setattr(agent, "_execute_run", _blocking_run)

        await connectors._on_inbound(message())
        session_id = store.list_sessions()[0].id

        # Second mention lands while the first run is genuinely still active.
        await connectors._on_inbound(
            message(ts="1712000090.000900", thread_ts="1712000000.000100")
        )
        assert agent._active_runs.get(session_id) is not None

        release.set()
        await agent._active_runs[session_id]
        return session_id

    session_id = run(_drive())
    assert len(store.list_messages(session_id)) == 1


def test_subscription_delivers_without_spawning(
    store: AgentStore, connectors: ConnectorService, agent: AgentService
) -> None:
    listener = agent.create_session(title="Listener", workspace_path=None)
    store.add_slack_subscription(session_id=listener.id, channel="slack:T1/C1")

    run(connectors._on_inbound(message(mentions_me=False)))

    assert len(store.list_sessions()) == 1
    messages = store.list_messages(listener.id)
    assert len(messages) == 1
    assert "reply→slack:T1/C1:1712000000.000100" in messages[0].content


def test_unauthorized_mention_creates_no_session(
    store: AgentStore, connectors: ConnectorService
) -> None:
    run(connectors._on_inbound(message(user_id="U-stranger")))

    assert store.list_sessions() == []
    assert len(store.list_slack_parked_messages()) == 1


def test_message_carries_a_display_sidecar(
    store: AgentStore, connectors: ConnectorService
) -> None:
    run(connectors._on_inbound(message()))
    stored = store.list_messages(store.list_sessions()[0].id)[0]

    assert stored.source is not None
    assert stored.source.connector == "slack"
    assert stored.source.channel_name == "dev-ops"
    assert stored.source.sender_name == "Julio"
    # The card shows the raw text; the reply-handle framing stays in `content`
    # for the model only.
    assert stored.source.text == "summarize this thread"
    assert "reply→" not in stored.source.text
    assert "reply→" in stored.content


def test_dm_sidecar_uses_bot_handle(
    store: AgentStore, connectors: ConnectorService
) -> None:
    class _Adapter:
        bot_user_id = "BBOT"
        _bot_name = "sandwalk"
        user_names = {"BBOT": "sandwalk"}

    connectors._sockets["T1"] = _Adapter()
    run(
        connectors._on_inbound(
            message(
                channel_id="D1",
                channel_type="im",
                channel_name=None,
                text="hi",
                mentions_me=False,
            )
        )
    )
    stored = store.list_messages(store.list_sessions()[0].id)[0]
    assert stored.source is not None
    assert stored.source.channel_id == "D1"
    assert stored.source.channel_name == "sandwalk"


def test_locally_typed_messages_have_no_sidecar(
    store: AgentStore, agent: AgentService
) -> None:
    session = agent.create_session(title="Local", workspace_path=None)

    async def send() -> None:
        agent.submit_message(session_id=session.id, content="hello")
        await _drain(agent, session.id)

    run(send())
    assert store.list_messages(session.id)[0].source is None


def test_allow_parked_delivers_the_waiting_message(
    store: AgentStore, connectors: ConnectorService
) -> None:
    # A stranger mentions the bot, so it queues instead of answering.
    run(connectors._on_inbound(message(user_id="U-stranger", user_name="Priya")))
    parked = store.list_slack_parked_messages()
    assert len(parked) == 1
    assert store.list_sessions() == []

    # Allowing must also answer — clearing the queue silently would leave
    # Priya waiting in Slack for a reply that never arrives.
    assert run(connectors.allow_parked(parked[0].id)) is True

    assert store.list_slack_parked_messages() == []
    sessions = store.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].source == "slack"
    assert store.is_slack_user_allowed(team_id="T1", slack_user_id="U-stranger")

    # And the thread mapping points at the new session, so replies stay threaded.
    assert (
        store.get_slack_mention_session("slack:T1/C1:1712000000.000100")
        == sessions[0].id
    )


def test_allow_parked_is_404_safe(connectors: ConnectorService) -> None:
    assert run(connectors.allow_parked("nope")) is False


def test_dispatch_without_an_agent_service_is_inert(store: AgentStore) -> None:
    service = ConnectorService(store)  # no agent service wired
    run(service._on_inbound(message()))
    assert store.list_sessions() == []


async def _drain(agent: AgentService, session_id: str) -> None:
    task = agent._active_runs.get(session_id)
    if task is not None:
        await task
    await asyncio.sleep(0)


def test_framing_shows_origin_and_handle() -> None:
    framed = frame_inbound(message(), channel_label="#dev-ops · Acme")
    assert framed.startswith("[Slack · #dev-ops · Acme | from Julio | reply→")
    assert "slack.send_message" in framed
    assert "reply→slack:T1/C1:1712000000.000100" in framed


def test_framing_falls_back_to_the_user_id() -> None:
    framed = frame_inbound(message(user_name=None), channel_label="#c")
    assert "from U1" in framed


def test_spawn_title_is_trimmed() -> None:
    long_text = "word " * 40
    title = spawn_title(message(text=long_text), channel_label="#dev-ops")
    assert len(title) <= 60
    assert title.strip() == title


def test_spawn_title_falls_back_to_the_channel() -> None:
    assert spawn_title(message(text="   "), channel_label="#dev-ops") == "#dev-ops"
