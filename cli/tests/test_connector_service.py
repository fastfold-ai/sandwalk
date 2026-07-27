"""Connector lifecycle: startup, token validation, and inbound dispatch."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

import pytest

from agent_server.connectors.gateway import InboundMessage
from agent_server.connectors.service import ConnectorService
from agent_server.connectors.slack_commands import SlashCommandRequest
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


def test_start_ignores_disabled_workspaces(store: AgentStore, service: ConnectorService) -> None:
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
        run(service.connect_socket_mode(bot_token="xoxb-real", app_token="xoxb-oops", team_id="T1"))


def test_connect_reports_a_missing_sdk_clearly(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The SDK ships in core deps, but a broken environment must say so instead
    # of failing silently the way an optional extra would.
    monkeypatch.setattr("agent_server.connectors.service.slack_sdk_available", lambda: False)
    with pytest.raises(ValueError, match="not installed"):
        run(service.connect_socket_mode(bot_token="xoxb-x", app_token="xapp-x", team_id="T1"))


def test_granted_scopes_parsing() -> None:
    from agent_server.connectors.service import _granted_scopes

    class Response:
        def __init__(self, headers: dict) -> None:
            self.headers = headers

    assert _granted_scopes(Response({"x-oauth-scopes": "chat:write, app_mentions:read"})) == {
        "chat:write",
        "app_mentions:read",
    }
    # Slack sometimes hands headers back as lists.
    assert _granted_scopes(Response({"x-oauth-scopes": ["chat:write"]})) == {"chat:write"}
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


def test_inbound_parks_unauthorized_mentions(store: AgentStore, service: ConnectorService) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="socket", bot_user_id="BBOT")

    run(service._on_inbound(message()))

    parked = store.list_slack_parked_messages()
    assert len(parked) == 1
    assert parked[0].slack_user_id == "U1"
    assert parked[0].thread_target == "slack:T1/C1:1712000000.000100"


def test_inbound_ignores_unknown_workspace(store: AgentStore, service: ConnectorService) -> None:
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


def test_status_reports_mode_and_workspaces(store: AgentStore, service: ConnectorService) -> None:
    assert service.status().mode is None

    store.upsert_slack_workspace(team_id="T1", mode="relay", team_name="Acme")
    status = service.status()
    assert status.mode == "relay"
    assert [item.team_id for item in status.workspaces] == ["T1"]
    assert status.relay_state == "off"

    # Socket Mode takes precedence — connecting one pauses relay delivery.
    store.upsert_slack_workspace(team_id="T2", mode="socket")
    assert service.status().mode == "socket"


def test_disconnect_removes_the_workspace(store: AgentStore, service: ConnectorService) -> None:
    store.upsert_slack_workspace(team_id="T1", mode="socket")
    assert run(service.disconnect_workspace("T1")) is True
    assert store.list_slack_workspaces() == []
    assert run(service.disconnect_workspace("T1")) is False


def test_reauth_import_overwrites_an_existing_stale_token(
    store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reinstall rotated the token — the reauth-targeted team must not be
    skipped just because we already have a (now stale) one on file."""
    store.upsert_slack_workspace(
        team_id="T1", mode="relay", bot_token="xoxb-old", connection_id="conn-1"
    )
    store.set_slack_workspace_reauth("T1", needs_reauth=True)

    monkeypatch.setattr("agent_server.account_service.helpers.api_key", lambda cfg=None: "sk-x")
    monkeypatch.setattr(
        "agent_server.account_service.helpers.cloud_base_url",
        lambda: "https://api.test",
    )

    async def fake_start_workspace(self, workspace):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(ConnectorService, "_start_workspace", fake_start_workspace)

    def fake_cloud_request(method, url, key, body):  # type: ignore[no-untyped-def]
        if url.endswith("/v1/slack/connections"):
            return {"data": [{"team_id": "T1", "id": "conn-1"}]}, None
        if url.endswith("/v1/slack/connections/conn-1"):
            return {"bot_token": "xoxb-new", "bot_user_id": "BBOT"}, None
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr("agent_server.connectors.service._cloud_request", fake_cloud_request)

    imported = run(service.import_one_click_connections(reauth_team_id="T1"))

    assert [w.team_id for w in imported] == ["T1"]
    bot, _app = store.get_slack_tokens("T1")
    assert bot == "xoxb-new"
    assert store.get_slack_workspace("T1").needs_reauth is False


def test_import_without_reauth_still_skips_an_existing_token(
    store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unchanged behavior for the normal "add a new workspace" scan."""
    store.upsert_slack_workspace(team_id="T1", mode="relay", bot_token="xoxb-old")

    monkeypatch.setattr("agent_server.account_service.helpers.api_key", lambda cfg=None: "sk-x")
    monkeypatch.setattr(
        "agent_server.account_service.helpers.cloud_base_url",
        lambda: "https://api.test",
    )

    called: list[str] = []

    def fake_cloud_request(method, url, key, body):  # type: ignore[no-untyped-def]
        called.append(url)
        return {"data": [{"team_id": "T1", "id": "conn-1"}]}, None

    monkeypatch.setattr("agent_server.connectors.service._cloud_request", fake_cloud_request)

    imported = run(service.import_one_click_connections())

    assert imported == []
    # Never even fetched the per-connection token — skipped before that call.
    assert called == ["https://api.test/v1/slack/connections"]
    bot, _app = store.get_slack_tokens("T1")
    assert bot == "xoxb-old"


def slash_request(**overrides: object) -> SlashCommandRequest:
    payload: dict[str, object] = {
        "command": "/sandwalk",
        "text": "status",
        "team_id": "T1",
        "user_id": "U1",
        "channel_id": "C1",
        "response_url": "https://hooks.slack.test/x",
    }
    payload.update(overrides)
    return SlashCommandRequest(**payload)  # type: ignore[arg-type]


def posted_texts(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "agent_server.connectors.slack_commands.post_response",
        lambda url, text, **_kwargs: calls.append((url, text)),
    )
    return calls


class TestHandleSlashCommand:
    @pytest.fixture(autouse=True)
    def _workspace(self, store: AgentStore) -> None:
        # allow_slack_user has a foreign key on slack_workspaces — every test
        # below either allows U1 or checks the "not allowed" rejection path,
        # so the workspace row needs to exist first either way.
        store.upsert_slack_workspace(team_id="T1", mode="relay")

    def test_unauthorized_user_gets_rejected(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = posted_texts(monkeypatch)
        run(service.handle_slash_command(slash_request()))
        assert len(calls) == 1
        assert calls[0][0] == "https://hooks.slack.test/x"
        assert "People list" in calls[0][1]

    def test_status_reports_connection_state(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1")
        store.upsert_slack_workspace(team_id="T1", mode="relay", team_name="Acme")
        calls = posted_texts(monkeypatch)

        run(service.handle_slash_command(slash_request(text="status")))

        assert "Acme" in calls[0][1]

    def test_sessions_lists_recent_slack_sessions(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1")
        store.create_session(
            title="hey you", workspace_path=None, source="slack", source_label="DM · Acme"
        )
        calls = posted_texts(monkeypatch)

        run(service.handle_slash_command(slash_request(text="sessions")))

        assert "hey you" in calls[0][1]
        assert "DM · Acme" in calls[0][1]

    def test_sessions_empty_says_so(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1")
        calls = posted_texts(monkeypatch)
        run(service.handle_slash_command(slash_request(text="sessions")))
        assert "No Slack sessions yet" in calls[0][1]

    def test_people_list(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1", display_name="Julio")
        calls = posted_texts(monkeypatch)

        run(service.handle_slash_command(slash_request(text="people list")))

        assert "Julio" in calls[0][1]

    def test_people_allow_approves_the_mentioned_user(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1")
        calls = posted_texts(monkeypatch)

        run(service.handle_slash_command(slash_request(text="people allow <@U9|jane>")))

        assert store.is_slack_user_allowed(team_id="T1", slack_user_id="U9") is True
        assert "<@U9>" in calls[0][1]

    def test_people_allow_without_a_mention_shows_usage(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1")
        calls = posted_texts(monkeypatch)

        run(service.handle_slash_command(slash_request(text="people allow")))

        assert "Usage" in calls[0][1]
        # No target parsed out of the text, so nobody new got added.
        assert [p.slack_user_id for p in store.list_slack_allowed_users("T1")] == ["U1"]

    def test_people_unknown_subcommand_shows_usage(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1")
        calls = posted_texts(monkeypatch)
        run(service.handle_slash_command(slash_request(text="people frobnicate")))
        assert "Usage" in calls[0][1]

    def test_parked_lists_pending_requests(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1")
        store.park_slack_message(
            team_id="T1", channel="slack:T1/C1", slack_user_id="U2", text="what can you do?"
        )
        calls = posted_texts(monkeypatch)

        run(service.handle_slash_command(slash_request(text="parked")))

        assert "what can you do?" in calls[0][1]

    def test_parked_empty_says_so(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1")
        calls = posted_texts(monkeypatch)
        run(service.handle_slash_command(slash_request(text="parked")))
        assert "No pending approval requests" in calls[0][1]

    def test_unknown_verb(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1")
        calls = posted_texts(monkeypatch)
        run(service.handle_slash_command(slash_request(text="nonsense")))
        assert "`nonsense`" in calls[0][1]

    def test_a_handler_exception_posts_a_generic_error(
        self, store: AgentStore, service: ConnectorService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store.allow_slack_user(team_id="T1", slack_user_id="U1")
        calls = posted_texts(monkeypatch)

        def boom(self, request):  # type: ignore[no-untyped-def]
            raise RuntimeError("kaboom")

        monkeypatch.setattr(ConnectorService, "_render_slash_command", boom)

        run(service.handle_slash_command(slash_request(text="status")))

        assert "went wrong" in calls[0][1]
