"""Connector lifecycle: startup, token validation, and inbound dispatch."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

import pytest

from agent_server.connectors.gateway import InboundMessage
from agent_server.connectors.service import ConnectorService
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
        "text": "hey @Sandwalk",
        "ts": "1712000000.000100",
        "mentions_me": True,
    }
    payload.update(overrides)
    return InboundMessage(**payload)  # type: ignore[arg-type]


def test_start_is_safe_with_no_workspaces(service: ConnectorService) -> None:
    run(service.start())
    run(service.stop())


def test_start_skips_socket_workspaces_missing_tokens(
    store: AgentStore, service: ConnectorService
) -> None:
    # A workspace row without tokens must not crash startup.
    store.upsert_slack_workspace(team_id="T1", mode="socket")
    run(service.start())
    assert service.socket_connected("T1") is False
    run(service.stop())


def test_start_ignores_disabled_workspaces(
    store: AgentStore, service: ConnectorService
) -> None:
    store.upsert_slack_workspace(
        team_id="T1", mode="socket", bot_token="xoxb-x", app_token="xapp-x"
    )
    store.set_slack_workspace_flags("T1", enabled=False)
    run(service.start())
    assert service.socket_connected("T1") is False
    run(service.stop())


def test_connect_requires_both_tokens(service: ConnectorService) -> None:
    with pytest.raises(ValueError, match="required"):
        run(service.connect_socket_mode(bot_token="xoxb-x", app_token=""))
    with pytest.raises(ValueError, match="required"):
        run(service.connect_socket_mode(bot_token="", app_token="xapp-x"))


def test_connect_rejects_a_bot_token_pasted_as_the_app_token(
    service: ConnectorService,
) -> None:
    # Socket Mode never connects without xapp- and Slack reports no error, so
    # this is the single most common setup failure.
    with pytest.raises(ValueError, match="xapp-"):
        run(
            service.connect_socket_mode(
                bot_token="xoxb-real", app_token="xoxb-oops", team_id="T1"
            )
        )


def test_connect_reports_a_missing_sdk_clearly(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The SDK ships in core deps, but a broken environment must say so instead
    # of failing silently the way an optional extra would.
    monkeypatch.setattr(
        "agent_server.connectors.service.slack_sdk_available", lambda: False
    )
    with pytest.raises(ValueError, match="not installed"):
        run(
            service.connect_socket_mode(
                bot_token="xoxb-x", app_token="xapp-x", team_id="T1"
            )
        )


def test_granted_scopes_parsing() -> None:
    from agent_server.connectors.service import _granted_scopes

    class Response:
        def __init__(self, headers: dict) -> None:
            self.headers = headers

    assert _granted_scopes(
        Response({"x-oauth-scopes": "chat:write, app_mentions:read"})
    ) == {"chat:write", "app_mentions:read"}
    # Slack sometimes hands headers back as lists.
    assert _granted_scopes(Response({"x-oauth-scopes": ["chat:write"]})) == {
        "chat:write"
    }
    assert _granted_scopes(Response({})) == set()
    assert _granted_scopes(object()) == set()


def test_directory_error_surfaces_the_missing_scope() -> None:
    from agent_server.connectors.directory import _why

    class Response:
        data = {"ok": False, "error": "missing_scope", "needed": "users:read"}

    class SlackApiError(Exception):
        response = Response()

        def __str__(self) -> str:  # what the SDK actually shows
            return "The request to the Slack API failed. (status: 200)"

    # The raw SDK message hides the cause; ours must not.
    assert _why(SlackApiError()) == "missing_scope (needs users:read)"
    assert _why(RuntimeError("boom")) == "boom"


def test_inbound_parks_unauthorized_mentions(
    store: AgentStore, service: ConnectorService
) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="socket", bot_user_id="BBOT")

    run(service._on_inbound(message()))

    parked = store.list_slack_parked_messages()
    assert len(parked) == 1
    assert parked[0].slack_user_id == "U1"
    assert parked[0].thread_target == "slack:T1/C1:1712000000.000100"


def test_inbound_ignores_unknown_workspace(
    store: AgentStore, service: ConnectorService
) -> None:
    run(service._on_inbound(message(team_id="T-nope")))
    assert store.list_slack_parked_messages() == []


def test_inbound_does_not_park_allowed_senders(
    store: AgentStore, service: ConnectorService
) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="socket", bot_user_id="BBOT")
    store.allow_slack_user(team_id="T1", slack_user_id="U1")

    run(service._on_inbound(message()))
    assert store.list_slack_parked_messages() == []


def test_reconnecting_updates_tokens_and_keeps_settings(
    store: AgentStore,
) -> None:
    """Re-pasting tokens must not cost the user their allowlist."""
    store.upsert_slack_workspace(
        team_id="T1", mode="socket", bot_token="xoxb-old", app_token="xapp-old"
    )
    store.allow_slack_user(team_id="T1", slack_user_id="U1", display_name="Julio")
    session = store.create_session(title="Listener", workspace_path=None)
    store.add_slack_subscription(session_id=session.id, channel="slack:T1/C1")

    store.upsert_slack_workspace(
        team_id="T1", mode="socket", bot_token="xoxb-new", app_token="xapp-new"
    )

    bot, app = store.get_slack_tokens("T1")
    assert (bot, app) == ("xoxb-new", "xapp-new")
    assert [p.slack_user_id for p in store.list_slack_allowed_users("T1")] == ["U1"]
    assert len(store.list_slack_subscriptions(session_id=session.id)) == 1


def test_disconnect_clears_the_allowlist(store: AgentStore) -> None:
    """Contrast with reconnect: disconnecting is meant to forget everything."""
    store.upsert_slack_workspace(team_id="T1", mode="socket")
    store.allow_slack_user(team_id="T1", slack_user_id="U1")

    assert run(ConnectorService(store).disconnect_workspace("T1")) is True
    assert store.list_slack_allowed_users("T1") == []


def test_status_reports_mode_and_workspaces(
    store: AgentStore, service: ConnectorService
) -> None:
    assert service.status().mode is None

    store.upsert_slack_workspace(team_id="T1", mode="relay", team_name="Acme")
    status = service.status()
    assert status.mode == "relay"
    assert [item.team_id for item in status.workspaces] == ["T1"]
    assert status.relay_state == "off"

    # Socket Mode takes precedence — connecting one pauses relay delivery.
    store.upsert_slack_workspace(team_id="T2", mode="socket")
    assert service.status().mode == "socket"


def test_disconnect_removes_the_workspace(
    store: AgentStore, service: ConnectorService
) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="socket")
    assert run(service.disconnect_workspace("T1")) is True
    assert store.list_slack_workspaces() == []
    assert run(service.disconnect_workspace("T1")) is False
