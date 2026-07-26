"""The relay client for one-click workspaces.

The point of the relay is that it changes the transport and nothing else, so
the load-bearing test here is that a relayed event yields exactly the
InboundMessage the Socket Mode path would have produced.
"""

from __future__ import annotations

import asyncio
import json

from agent_server.connectors.slack_events import event_to_inbound
from agent_server.connectors.slack_relay import (
    SlackRelayClient,
    SlackRelayWorkspace,
    _is_auth_failure,
    _relay_url,
    _team_id_from_envelope,
)


def run(coro):
    return asyncio.run(coro)


def envelope(**event):
    base = {"type": "app_mention", "text": "hi <@BBOT>", "user": "U1", "channel": "C1", "ts": "1.1"}
    base.update(event)
    return {"type": "event_callback", "team_id": "T1", "event_id": "Ev1", "event": base}


def workspace(**kwargs) -> SlackRelayWorkspace:
    space = SlackRelayWorkspace(
        team_id=kwargs.get("team_id", "T1"),
        bot_token=kwargs.get("bot_token", "xoxb-x"),
        bot_user_id=kwargs.get("bot_user_id", "BBOT"),
    )
    space.user_names = kwargs.get("user_names", {"U1": "Ada"})
    space.channel_names = kwargs.get("channel_names", {"C1": "dev-ops"})
    space.user_avatars = kwargs.get("user_avatars", {"U1": "https://x/a.png"})
    return space


def client_with(space, received) -> SlackRelayClient:
    async def handler(message):
        received.append(message)

    relay = SlackRelayClient(base_url="https://api.test", api_key="sk-x", on_message=handler)
    relay.add_workspace(space)
    return relay


class TestUrl:
    def test_https_becomes_wss(self):
        assert _relay_url("https://api.fastfold.ai") == "wss://api.fastfold.ai/v1/slack/relay"

    def test_http_becomes_ws(self):
        assert _relay_url("http://127.0.0.1:8000") == "ws://127.0.0.1:8000/v1/slack/relay"

    def test_trailing_slash_does_not_double_up(self):
        assert _relay_url("https://api.test/") == "wss://api.test/v1/slack/relay"


class TestTeamRouting:
    def test_reads_the_top_level_team(self):
        assert _team_id_from_envelope({"team_id": "T9"}) == "T9"

    def test_falls_back_to_authorizations(self):
        assert _team_id_from_envelope({"authorizations": [{"team_id": "T8"}]}) == "T8"

    def test_none_when_absent(self):
        assert _team_id_from_envelope({}) is None

    def test_an_unknown_team_is_dropped(self):
        received: list = []
        relay = client_with(workspace(team_id="T1"), received)
        payload = envelope()
        payload["team_id"] = "T-other"
        run(relay._handle_frame(json.dumps(payload)))
        assert received == []

    def test_each_team_gets_its_own_adapter(self):
        received: list = []
        relay = client_with(workspace(team_id="T1"), received)
        relay.add_workspace(workspace(team_id="T2", bot_user_id="BTWO"))
        assert sorted(relay.teams) == ["T1", "T2"]
        assert relay.get("T2").bot_user_id == "BTWO"


class TestFrameHandling:
    def test_matches_what_socket_mode_would_produce(self):
        """The transport changes; the resulting message must not."""
        space = workspace()
        received: list = []
        relay = client_with(space, received)
        payload = envelope()

        run(relay._handle_frame(json.dumps(payload)))

        expected = event_to_inbound(
            payload["event"],
            team_id="T1",
            bot_user_id="BBOT",
            channel_names=space.channel_names,
            user_names=space.user_names,
            user_avatars=space.user_avatars,
        )
        assert received == [expected]

    def test_resolves_names_and_avatar(self):
        received: list = []
        run(client_with(workspace(), received)._handle_frame(json.dumps(envelope())))
        assert received[0].user_name == "Ada"
        assert received[0].channel_name == "dev-ops"
        assert received[0].user_avatar_url == "https://x/a.png"

    def test_ready_frame_is_not_a_message(self):
        received: list = []
        run(client_with(workspace(), received)._handle_frame('{"type":"relay.ready"}'))
        assert received == []

    def test_unparseable_frames_are_ignored(self):
        received: list = []
        relay = client_with(workspace(), received)
        run(relay._handle_frame("not json"))
        run(relay._handle_frame("[1,2,3]"))
        assert received == []

    def test_bot_echo_is_filtered(self):
        """Same rule as Socket Mode - the agent must not answer itself."""
        received: list = []
        payload = envelope(bot_id="B1")
        run(client_with(workspace(), received)._handle_frame(json.dumps(payload)))
        assert received == []

    def test_a_handler_failure_does_not_escape(self):
        async def boom(_message):
            raise RuntimeError("handler exploded")

        relay = SlackRelayClient(
            base_url="https://api.test", api_key="sk-x", on_message=boom
        )
        relay.add_workspace(workspace())
        run(relay._handle_frame(json.dumps(envelope())))


class TestState:
    def test_reports_liveness_to_its_workspaces(self):
        space = workspace()
        relay = client_with(space, [])
        assert space.connected is False
        relay._set_live(True)
        assert space.connected is True

    def test_a_workspace_added_later_inherits_liveness(self):
        relay = client_with(workspace(), [])
        relay._set_live(True)
        late = workspace(team_id="T3")
        relay.add_workspace(late)
        assert late.connected is True

    def test_a_rejected_key_is_distinguished_from_a_blip(self):
        """Retrying will not fix a bad key, so it must not read as reconnecting."""
        assert _is_auth_failure(RuntimeError("server rejected: HTTP 401 Unauthorized"))
        assert _is_auth_failure(RuntimeError("closed with code 4401"))
        assert not _is_auth_failure(RuntimeError("connection reset by peer"))

    def test_stop_clears_everything(self):
        states: list = []
        relay = SlackRelayClient(
            base_url="https://api.test",
            api_key="sk-x",
            on_message=lambda _m: asyncio.sleep(0),
            on_state=lambda state, detail: states.append((state, detail)),
        )
        relay.add_workspace(workspace())
        run(relay.stop())
        assert relay.teams == []
        assert relay.connected is False
        assert states[-1] == ("off", None)
