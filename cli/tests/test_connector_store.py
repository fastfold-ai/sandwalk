"""Slack connector storage: workspaces, allowlist, subscriptions, mutes."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_server.store import AgentStore


@pytest.fixture()
def store(tmp_path: Path) -> AgentStore:
    return AgentStore(tmp_path / "agent.db", exclusive=True)


def test_session_source_round_trip(store: AgentStore) -> None:
    local = store.create_session(title="Local", workspace_path=None)
    assert local.source is None
    assert local.source_label is None

    slack = store.create_session(
        title="From Slack",
        workspace_path=None,
        source="slack",
        source_label="#dev-ops · Acme",
    )
    assert slack.source == "slack"
    assert slack.source_label == "#dev-ops · Acme"

    reloaded = store.get_session(slack.id)
    assert reloaded is not None
    assert reloaded.source == "slack"
    assert reloaded.source_label == "#dev-ops · Acme"


def test_session_source_rejects_unknown_connector(store: AgentStore) -> None:
    with pytest.raises(ValueError):
        store.create_session(title="Bad", workspace_path=None, source="telegram")


def test_workspace_upsert_preserves_tokens(store: AgentStore) -> None:
    created = store.upsert_slack_workspace(
        team_id="T123",
        mode="socket",
        team_name="Acme",
        bot_token="xoxb-secret",
        app_token="xapp-secret",
    )
    assert created.has_bot_token is True
    assert created.has_app_token is True
    # Tokens are never exposed on the API model.
    assert "xoxb-secret" not in created.model_dump_json()

    # A later upsert that omits tokens must not wipe them.
    updated = store.upsert_slack_workspace(team_id="T123", mode="socket", domain="acme")
    assert updated.has_bot_token is True
    assert updated.domain == "acme"

    bot, app = store.get_slack_tokens("T123")
    assert bot == "xoxb-secret"
    assert app == "xapp-secret"


def test_needs_reauth_defaults_false_and_can_be_set(store: AgentStore) -> None:
    workspace = store.upsert_slack_workspace(team_id="T1", mode="relay")
    assert workspace.needs_reauth is False

    flagged = store.set_slack_workspace_reauth("T1", needs_reauth=True)
    assert flagged is not None
    assert flagged.needs_reauth is True
    assert store.get_slack_workspace("T1").needs_reauth is True


def test_set_reauth_on_an_unknown_workspace_is_a_no_op(store: AgentStore) -> None:
    assert store.set_slack_workspace_reauth("T-missing", needs_reauth=True) is None


def test_a_fresh_token_clears_needs_reauth(store: AgentStore) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="relay", bot_token="xoxb-old")
    store.set_slack_workspace_reauth("T1", needs_reauth=True)
    assert store.get_slack_workspace("T1").needs_reauth is True

    # Reconnecting supplies a new bot_token - that alone clears the flag.
    updated = store.upsert_slack_workspace(team_id="T1", mode="relay", bot_token="xoxb-new")
    assert updated.needs_reauth is False


def test_an_upsert_without_a_token_does_not_clear_the_flag(store: AgentStore) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="relay", bot_token="xoxb-old")
    store.set_slack_workspace_reauth("T1", needs_reauth=True)

    # e.g. just refreshing team_name - no token supplied, flag must survive.
    updated = store.upsert_slack_workspace(team_id="T1", mode="relay", team_name="Acme")
    assert updated.needs_reauth is True
    assert updated.team_name == "Acme"


def test_clear_bot_token_on_revocation(store: AgentStore) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="relay", bot_token="xoxb-cached")
    store.clear_slack_bot_token("T1")
    bot, _ = store.get_slack_tokens("T1")
    assert bot is None


def test_allowlist_is_closed_by_default(store: AgentStore) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="relay")
    assert store.is_slack_user_allowed(team_id="T1", slack_user_id="U1") is False

    store.allow_slack_user(team_id="T1", slack_user_id="U1", display_name="Julio")
    assert store.is_slack_user_allowed(team_id="T1", slack_user_id="U1") is True
    assert store.is_slack_user_allowed(team_id="T1", slack_user_id="U2") is False

    listed = store.list_slack_allowed_users("T1")
    assert [item.slack_user_id for item in listed] == ["U1"]
    assert listed[0].display_name == "Julio"

    assert store.disallow_slack_user(team_id="T1", slack_user_id="U1") is True
    assert store.is_slack_user_allowed(team_id="T1", slack_user_id="U1") is False


def test_allowlist_is_scoped_per_workspace(store: AgentStore) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="relay")
    store.upsert_slack_workspace(team_id="T2", mode="relay")
    store.allow_slack_user(team_id="T1", slack_user_id="U1")

    assert store.is_slack_user_allowed(team_id="T2", slack_user_id="U1") is False


def test_subscriptions_lookup_by_channel(store: AgentStore) -> None:
    first = store.create_session(title="One", workspace_path=None)
    second = store.create_session(title="Two", workspace_path=None)
    store.add_slack_subscription(session_id=first.id, channel="slack:T1/C1")
    store.add_slack_subscription(session_id=second.id, channel="slack:T1/C1")
    store.add_slack_subscription(session_id=second.id, channel="slack:T1/C2")

    listeners = store.list_slack_subscriptions(channel="slack:T1/C1")
    assert {item.session_id for item in listeners} == {first.id, second.id}

    for_session = store.list_slack_subscriptions(session_id=second.id)
    assert {item.channel for item in for_session} == {"slack:T1/C1", "slack:T1/C2"}

    assert store.remove_slack_subscription(session_id=first.id, channel="slack:T1/C1") is True
    assert len(store.list_slack_subscriptions(channel="slack:T1/C1")) == 1


def test_subscriptions_are_idempotent(store: AgentStore) -> None:
    session = store.create_session(title="One", workspace_path=None)
    store.add_slack_subscription(session_id=session.id, channel="slack:T1/C1")
    store.add_slack_subscription(session_id=session.id, channel="slack:T1/C1")
    assert len(store.list_slack_subscriptions(session_id=session.id)) == 1


def test_mention_thread_maps_to_one_session(store: AgentStore) -> None:
    session = store.create_session(title="Thread", workspace_path=None)
    target = "slack:T1/C1:1712000000.000100"
    assert store.get_slack_mention_session(target) is None

    store.set_slack_mention_session(
        thread_target=target, session_id=session.id, channel="slack:T1/C1"
    )
    assert store.get_slack_mention_session(target) == session.id

    # Re-pointing the same thread replaces rather than duplicating.
    other = store.create_session(title="Other", workspace_path=None)
    store.set_slack_mention_session(
        thread_target=target, session_id=other.id, channel="slack:T1/C1"
    )
    assert store.get_slack_mention_session(target) == other.id


def test_parked_messages_queue_and_resolve(store: AgentStore) -> None:
    parked = store.park_slack_message(
        team_id="T1",
        channel="slack:T1/C1",
        slack_user_id="U9",
        text="hey @Sandwalk",
        user_name="Priya",
    )
    listed = store.list_slack_parked_messages()
    assert [item.id for item in listed] == [parked.id]
    assert listed[0].user_name == "Priya"

    assert store.delete_slack_parked_message(parked.id) is True
    assert store.list_slack_parked_messages() == []


def test_session_connector_mute_defaults_off(store: AgentStore) -> None:
    session = store.create_session(title="Muted", workspace_path=None)
    assert store.is_session_connector_muted(session_id=session.id, connector="slack") is False

    store.set_session_connector_mute(session_id=session.id, connector="slack", muted=True)
    assert store.is_session_connector_muted(session_id=session.id, connector="slack") is True

    store.set_session_connector_mute(session_id=session.id, connector="slack", muted=False)
    assert store.is_session_connector_muted(session_id=session.id, connector="slack") is False


def test_deleting_workspace_cascades_allowlist(store: AgentStore) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="relay")
    store.allow_slack_user(team_id="T1", slack_user_id="U1")

    assert store.delete_slack_workspace("T1") is True
    assert store.list_slack_allowed_users("T1") == []
