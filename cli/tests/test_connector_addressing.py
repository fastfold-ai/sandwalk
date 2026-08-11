"""Slack channel/thread address parsing and user-pasted channel resolution."""

from __future__ import annotations

import pytest

from agent_server.connectors.addressing import (
    SlackTarget,
    format_channel,
    format_target,
    is_message_ts,
    is_slack_target,
    parse_target,
    resolve_channel_input,
    thread_ts_from_permalink,
)


def test_format_and_parse_round_trip() -> None:
    channel = format_channel("T0123", "C0456")
    assert channel == "slack:T0123/C0456"

    target = format_target("T0123", "C0456", "1712000000.000100")
    assert target == "slack:T0123/C0456:1712000000.000100"

    parsed = parse_target(target)
    assert parsed == SlackTarget("T0123", "C0456", "1712000000.000100")
    assert parsed.channel == channel
    assert parsed.target == target


def test_parse_target_without_thread() -> None:
    parsed = parse_target("slack:T1/C1")
    assert parsed.thread_ts is None
    assert parsed.channel == "slack:T1/C1"
    assert parsed.target == "slack:T1/C1"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "slack:",
        "slack:C0456",  # missing team
        "telegram:T1/C1",
        "T1/C1",
    ],
)
def test_parse_target_rejects_malformed(value: str) -> None:
    with pytest.raises(ValueError):
        parse_target(value)
    assert is_slack_target(value) is False


def test_thread_ts_survives_the_dot() -> None:
    # The timestamp contains a '.' but no ':', so the colon grammar stays intact.
    parsed = parse_target("slack:T1/C1:1712000000.000100")
    assert parsed.thread_ts == "1712000000.000100"


def test_format_requires_both_parts() -> None:
    with pytest.raises(ValueError):
        format_channel("", "C1")
    with pytest.raises(ValueError):
        format_channel("T1", "")


def test_resolve_canonical_input() -> None:
    assert resolve_channel_input("slack:T1/C1") == "slack:T1/C1"
    # A thread target narrows to its channel.
    assert resolve_channel_input("slack:T1/C1:1712000000.000100") == "slack:T1/C1"


def test_resolve_bare_channel_uses_default_team() -> None:
    assert resolve_channel_input("C0456", default_team_id="T1") == "slack:T1/C0456"
    assert resolve_channel_input("#C0456", default_team_id="T1") == "slack:T1/C0456"
    assert resolve_channel_input("slack:C0456", default_team_id="T1") == "slack:T1/C0456"


def test_resolve_archive_url() -> None:
    assert (
        resolve_channel_input(
            "https://acme.slack.com/archives/C0456", default_team_id="T1"
        )
        == "slack:T1/C0456"
    )
    assert (
        resolve_channel_input(
            "https://acme.slack.com/archives/C0456/p1712000000000100",
            default_team_id="T1",
        )
        == "slack:T1/C0456"
    )


def test_resolve_channel_mention() -> None:
    assert (
        resolve_channel_input("<#C0456|general>", default_team_id="T1")
        == "slack:T1/C0456"
    )
    assert resolve_channel_input("<#C0456>", default_team_id="T1") == "slack:T1/C0456"


def test_resolve_without_team_is_a_clear_error() -> None:
    with pytest.raises(ValueError, match="workspace"):
        resolve_channel_input("C0456")


def test_resolve_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        resolve_channel_input("not a channel!", default_team_id="T1")
    with pytest.raises(ValueError):
        resolve_channel_input("", default_team_id="T1")


def test_permalink_timestamp_conversion() -> None:
    assert thread_ts_from_permalink("p1712000000000100") == "1712000000.000100"
    assert thread_ts_from_permalink("1712000000.000100") is None
    assert thread_ts_from_permalink("") is None


def test_message_ts_detection() -> None:
    assert is_message_ts("1712000000.000100") is True
    assert is_message_ts("1712000000") is False
    assert is_message_ts("nope") is False
