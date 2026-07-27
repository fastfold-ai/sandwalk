"""``/sandwalk`` slash command parsing, rendering, and the response_url POST."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timezone

import pytest

from agent_server.connectors import slack_commands
from agent_server.connectors.slack_home import HomeSessionRow, HomeStatus
from agent_server.models.connectors import SlackAllowedUser, SlackParkedMessage


class TestParse:
    def test_builds_a_request_from_a_relay_frame(self) -> None:
        request = slack_commands.parse_slash_command(
            {
                "command": "/sandwalk",
                "text": "people allow <@U9|jane>",
                "team_id": "T1",
                "user_id": "U1",
                "channel_id": "C1",
                "response_url": "https://hooks.slack.test/x",
            }
        )
        assert request is not None
        assert request.verb == "people"
        assert request.rest == ["allow", "<@U9|jane>"]
        assert request.args == ["people", "allow", "<@U9|jane>"]

    def test_missing_team_id_is_rejected(self) -> None:
        assert (
            slack_commands.parse_slash_command({"response_url": "https://hooks.slack.test/x"})
            is None
        )

    def test_missing_response_url_is_rejected(self) -> None:
        assert slack_commands.parse_slash_command({"team_id": "T1"}) is None

    def test_non_dict_is_rejected(self) -> None:
        assert slack_commands.parse_slash_command(None) is None  # type: ignore[arg-type]

    def test_empty_text_has_no_verb(self) -> None:
        request = slack_commands.parse_slash_command(
            {"team_id": "T1", "response_url": "https://hooks.slack.test/x", "text": "  "}
        )
        assert request is not None
        assert request.verb == ""
        assert request.rest == []


class TestRenderStatus:
    def test_matches_the_home_tab_status_lines(self) -> None:
        from agent_server.connectors.slack_home import status_lines

        status = HomeStatus(relay_state="live", team_name="Acme")
        assert slack_commands.render_status(status) == "\n".join(status_lines(status))

    def test_handles_none(self) -> None:
        assert "Not connected" in slack_commands.render_status(None)


class TestRenderSessions:
    def test_empty_says_so(self) -> None:
        assert "No Slack sessions yet" in slack_commands.render_sessions([])

    def test_links_a_session_with_an_id(self) -> None:
        from agent_server.connectors.slack_home import session_url

        row = HomeSessionRow(
            id="s1",
            title="hey you",
            source_label="DM · Acme",
            updated_at=datetime.now(UTC),
        )
        text = slack_commands.render_sessions([row])
        assert f"<{session_url('s1')}|hey you>" in text
        assert "DM · Acme" in text

    def test_session_without_an_id_is_plain_text(self) -> None:
        text = slack_commands.render_sessions([HomeSessionRow(title="no id")])
        assert "no id" in text
        assert "<http" not in text

    def test_caps_at_the_recent_limit(self) -> None:
        rows = [HomeSessionRow(title=f"s{i}") for i in range(slack_commands.RECENT_LIMIT + 3)]
        text = slack_commands.render_sessions(rows)
        assert text.count("•") == slack_commands.RECENT_LIMIT


class TestRenderPeople:
    def test_empty_says_so(self) -> None:
        assert "Nobody is on the People list" in slack_commands.render_people([])

    def test_lists_display_name_and_id(self) -> None:
        people = [
            SlackAllowedUser(
                team_id="T1",
                slack_user_id="U1",
                display_name="Julio",
                created_at=datetime.now(UTC),
            )
        ]
        text = slack_commands.render_people(people)
        assert "Julio" in text
        assert "U1" in text

    def test_falls_back_to_the_id_without_a_display_name(self) -> None:
        people = [SlackAllowedUser(team_id="T1", slack_user_id="U1", created_at=datetime.now(UTC))]
        assert "U1" in slack_commands.render_people(people)


class TestRenderParked:
    def test_empty_says_so(self) -> None:
        assert "No pending approval requests" in slack_commands.render_parked([])

    def test_lists_the_sender_and_text(self) -> None:
        parked = [
            SlackParkedMessage(
                id="p1",
                team_id="T1",
                channel="slack:T1/C1",
                slack_user_id="U1",
                user_name="Priya",
                text="what can you do?",
                created_at=datetime.now(UTC),
            )
        ]
        text = slack_commands.render_parked(parked)
        assert "Priya" in text
        assert "what can you do?" in text

    def test_truncates_a_long_message(self) -> None:
        parked = [
            SlackParkedMessage(
                id="p1",
                team_id="T1",
                channel="slack:T1/C1",
                slack_user_id="U1",
                text="y" * 200,
                created_at=datetime.now(UTC),
            )
        ]
        text = slack_commands.render_parked(parked)
        assert "…" in text
        assert "y" * 200 not in text


class TestPeopleSubcommandCopy:
    def test_allow_usage_mentions_the_syntax(self) -> None:
        assert "/sandwalk people allow" in slack_commands.render_allow_usage()

    def test_allowed_names_the_user(self) -> None:
        assert "<@U9>" in slack_commands.render_allowed("U9")

    def test_people_usage_mentions_both_subcommands(self) -> None:
        text = slack_commands.render_people_usage()
        assert "people list" in text
        assert "people allow" in text


class TestMiscCopy:
    def test_unauthorized_is_actionable(self) -> None:
        assert "People list" in slack_commands.render_unauthorized()

    def test_unknown_names_the_verb(self) -> None:
        assert "`nonsense`" in slack_commands.render_unknown("nonsense")

    def test_error_is_generic_but_present(self) -> None:
        assert slack_commands.render_error()


class TestPostResponse:
    def test_posts_the_expected_json_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict] = []

        class _FakeResponse:
            def __enter__(self):  # type: ignore[no-untyped-def]
                return self

            def __exit__(self, *exc):  # type: ignore[no-untyped-def]
                return False

        def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
            calls.append(
                {
                    "url": request.full_url,
                    "body": json.loads(request.data),
                    "timeout": timeout,
                }
            )
            return _FakeResponse()

        monkeypatch.setattr(
            "agent_server.connectors.slack_commands.urllib.request.urlopen", fake_urlopen
        )

        slack_commands.post_response("https://hooks.slack.test/x", "hello")

        assert len(calls) == 1
        assert calls[0]["url"] == "https://hooks.slack.test/x"
        assert calls[0]["body"] == {
            "response_type": "ephemeral",
            "text": "hello",
            "replace_original": True,
        }

    def test_a_failed_post_does_not_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
            raise OSError("boom")

        monkeypatch.setattr(
            "agent_server.connectors.slack_commands.urllib.request.urlopen", fake_urlopen
        )

        slack_commands.post_response("https://hooks.slack.test/x", "hello")  # must not raise
