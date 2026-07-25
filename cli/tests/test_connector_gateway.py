"""Inbound Slack routing: allowlist, subscriptions, mention threads, mutes."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_server.connectors.gateway import InboundMessage, SlackGateway
from agent_server.store import AgentStore


@pytest.fixture()
def store(tmp_path: Path) -> AgentStore:
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    store.upsert_slack_workspace(
        team_id="T1", mode="socket", team_name="Acme", bot_user_id="BBOT"
    )
    return store


@pytest.fixture()
def gateway(store: AgentStore) -> SlackGateway:
    return SlackGateway(store)


def message(**overrides: object) -> InboundMessage:
    payload: dict[str, object] = {
        "team_id": "T1",
        "channel_id": "C1",
        "user_id": "U1",
        "text": "hey @Sandwalk",
        "ts": "1712000000.000100",
        "mentions_me": True,
    }
    payload.update(overrides)
    return InboundMessage(**payload)  # type: ignore[arg-type]


def test_thread_target_prefers_parent_thread() -> None:
    standalone = message()
    assert standalone.thread_target == "slack:T1/C1:1712000000.000100"

    reply = message(ts="1712000009.000900", thread_ts="1712000000.000100")
    assert reply.thread_target == "slack:T1/C1:1712000000.000100"
    assert reply.channel == "slack:T1/C1"


def test_unknown_workspace_is_ignored(gateway: SlackGateway) -> None:
    decision = gateway.route(message(team_id="T-other"))
    assert decision.action == "ignore"
    assert decision.reason == "unknown workspace"


def test_disabled_workspace_is_ignored(
    store: AgentStore, gateway: SlackGateway
) -> None:
    store.set_slack_workspace_flags("T1", enabled=False)
    assert gateway.route(message()).action == "ignore"


def test_own_messages_never_loop(store: AgentStore, gateway: SlackGateway) -> None:
    store.allow_slack_user(team_id="T1", slack_user_id="BBOT")
    decision = gateway.route(message(user_id="BBOT"))
    assert decision.action == "ignore"
    assert decision.reason == "own message"


def test_empty_message_is_ignored(store: AgentStore, gateway: SlackGateway) -> None:
    store.allow_slack_user(team_id="T1", slack_user_id="U1")
    assert gateway.route(message(text="   ")).action == "ignore"


def test_mention_from_unknown_sender_is_parked(gateway: SlackGateway) -> None:
    decision = gateway.route(message())
    assert decision.action == "park"
    assert decision.thread_target == "slack:T1/C1:1712000000.000100"


def test_mention_from_allowed_sender_spawns(
    store: AgentStore, gateway: SlackGateway
) -> None:
    store.allow_slack_user(team_id="T1", slack_user_id="U1")
    decision = gateway.route(message())
    assert decision.action == "spawn"
    assert decision.channel == "slack:T1/C1"


def test_second_mention_in_thread_reuses_session(
    store: AgentStore, gateway: SlackGateway
) -> None:
    store.allow_slack_user(team_id="T1", slack_user_id="U1")
    session = store.create_session(title="Slack", workspace_path=None, source="slack")
    store.set_slack_mention_session(
        thread_target="slack:T1/C1:1712000000.000100",
        session_id=session.id,
        channel="slack:T1/C1",
    )

    decision = gateway.route(message(ts="1712000050.000900", thread_ts="1712000000.000100"))
    assert decision.action == "deliver"
    assert decision.session_ids == [session.id]
    assert decision.reason == "mention thread"


def test_muted_session_stops_thread_delivery(
    store: AgentStore, gateway: SlackGateway
) -> None:
    store.allow_slack_user(team_id="T1", slack_user_id="U1")
    session = store.create_session(title="Slack", workspace_path=None, source="slack")
    store.set_slack_mention_session(
        thread_target="slack:T1/C1:1712000000.000100",
        session_id=session.id,
        channel="slack:T1/C1",
    )
    store.set_session_connector_mute(
        session_id=session.id, connector="slack", muted=True
    )

    decision = gateway.route(
        message(ts="1712000050.000900", thread_ts="1712000000.000100")
    )
    assert decision.action == "ignore"
    assert decision.reason == "session muted"


def test_subscription_wins_over_spawning(
    store: AgentStore, gateway: SlackGateway
) -> None:
    store.allow_slack_user(team_id="T1", slack_user_id="U1")
    listener = store.create_session(title="Listener", workspace_path=None)
    store.add_slack_subscription(session_id=listener.id, channel="slack:T1/C1")

    decision = gateway.route(message())
    assert decision.action == "deliver"
    assert decision.session_ids == [listener.id]
    assert decision.reason == "subscription"


def test_non_mention_reaches_subscribers_only(
    store: AgentStore, gateway: SlackGateway
) -> None:
    store.allow_slack_user(team_id="T1", slack_user_id="U1")
    assert gateway.route(message(mentions_me=False)).action == "ignore"

    listener = store.create_session(title="Listener", workspace_path=None)
    store.add_slack_subscription(session_id=listener.id, channel="slack:T1/C1")
    decision = gateway.route(message(mentions_me=False))
    assert decision.action == "deliver"
    assert decision.session_ids == [listener.id]


def test_ambient_traffic_is_never_parked(gateway: SlackGateway) -> None:
    # A non-mention from a stranger is not a request; parking it would bury the
    # real approvals under channel chatter.
    decision = gateway.route(message(mentions_me=False))
    assert decision.action == "ignore"


def test_muted_subscriber_is_skipped(
    store: AgentStore, gateway: SlackGateway
) -> None:
    store.allow_slack_user(team_id="T1", slack_user_id="U1")
    active = store.create_session(title="Active", workspace_path=None)
    muted = store.create_session(title="Muted", workspace_path=None)
    store.add_slack_subscription(session_id=active.id, channel="slack:T1/C1")
    store.add_slack_subscription(session_id=muted.id, channel="slack:T1/C1")
    store.set_session_connector_mute(
        session_id=muted.id, connector="slack", muted=True
    )

    decision = gateway.route(message())
    assert decision.session_ids == [active.id]


def test_allowlist_does_not_leak_across_workspaces(
    store: AgentStore, gateway: SlackGateway
) -> None:
    store.upsert_slack_workspace(team_id="T2", mode="socket", bot_user_id="BBOT")
    store.allow_slack_user(team_id="T1", slack_user_id="U1")

    assert gateway.route(message(team_id="T2")).action == "park"


def test_source_label_uses_workspace_name(
    store: AgentStore, gateway: SlackGateway
) -> None:
    label = gateway.source_label(message(channel_name="dev-ops"))
    assert label == "#dev-ops · Acme"

    # Falls back to raw ids when names are unavailable.
    store.upsert_slack_workspace(team_id="T3", mode="socket")
    assert gateway.source_label(message(team_id="T3")) == "#C1 · T3"
