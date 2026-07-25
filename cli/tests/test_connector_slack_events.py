"""Raw Slack event payload → InboundMessage mapping."""

from __future__ import annotations

from agent_server.connectors.slack_events import (
    event_to_inbound,
    mentions_user,
    rewrite_mentions,
    team_id_from_envelope,
)

BOT = "B0BOT"


def event(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "type": "message",
        "user": "U1",
        "channel": "C1",
        "ts": "1712000000.000100",
        "text": f"<@{BOT}> summarize this",
    }
    payload.update(overrides)
    return payload


def test_maps_a_channel_mention() -> None:
    inbound = event_to_inbound(event(), team_id="T1", bot_user_id=BOT)
    assert inbound is not None
    assert inbound.team_id == "T1"
    assert inbound.channel_id == "C1"
    assert inbound.user_id == "U1"
    assert inbound.mentions_me is True
    assert inbound.thread_ts is None
    assert inbound.thread_target == "slack:T1/C1:1712000000.000100"


def test_app_mention_type_counts_as_a_mention() -> None:
    inbound = event_to_inbound(
        event(type="app_mention", text="hello there"), team_id="T1", bot_user_id=BOT
    )
    assert inbound is not None
    assert inbound.mentions_me is True


def test_plain_message_is_not_a_mention() -> None:
    inbound = event_to_inbound(event(text="just chatting"), team_id="T1", bot_user_id=BOT)
    assert inbound is not None
    assert inbound.mentions_me is False


def test_bot_echo_is_dropped() -> None:
    assert event_to_inbound(event(bot_id="B999"), team_id="T1", bot_user_id=BOT) is None
    assert event_to_inbound(event(user=BOT), team_id="T1", bot_user_id=BOT) is None


def test_edits_and_joins_are_dropped() -> None:
    for subtype in ("message_changed", "message_deleted", "channel_join"):
        assert (
            event_to_inbound(event(subtype=subtype), team_id="T1", bot_user_id=BOT)
            is None
        )


def test_file_share_is_kept() -> None:
    inbound = event_to_inbound(
        event(subtype="file_share"), team_id="T1", bot_user_id=BOT
    )
    assert inbound is not None


def test_incomplete_events_are_dropped() -> None:
    assert event_to_inbound(event(text="   "), team_id="T1", bot_user_id=BOT) is None
    assert event_to_inbound(event(user=""), team_id="T1", bot_user_id=BOT) is None
    assert event_to_inbound(event(channel=""), team_id="T1", bot_user_id=BOT) is None
    assert event_to_inbound({}, team_id="T1", bot_user_id=BOT) is None


def test_parent_thread_ts_is_not_treated_as_a_thread() -> None:
    # Slack sets thread_ts == ts on the parent message of a thread.
    inbound = event_to_inbound(
        event(thread_ts="1712000000.000100"), team_id="T1", bot_user_id=BOT
    )
    assert inbound is not None
    assert inbound.thread_ts is None


def test_reply_keeps_parent_thread_ts() -> None:
    inbound = event_to_inbound(
        event(ts="1712000090.000900", thread_ts="1712000000.000100"),
        team_id="T1",
        bot_user_id=BOT,
    )
    assert inbound is not None
    assert inbound.thread_ts == "1712000000.000100"
    assert inbound.thread_target == "slack:T1/C1:1712000000.000100"


def test_mention_tokens_are_rewritten_for_the_transcript() -> None:
    inbound = event_to_inbound(
        event(text=f"<@{BOT}> ask <@U2|priya> about it"),
        team_id="T1",
        bot_user_id=BOT,
        user_names={"U1": "Julio", BOT: "Sandwalk"},
    )
    assert inbound is not None
    assert inbound.text == "@Sandwalk ask @priya about it"
    assert inbound.user_name == "Julio"


def test_rewrite_falls_back_through_inline_name_then_id() -> None:
    assert rewrite_mentions("<@U2|priya> hi") == "@priya hi"
    assert rewrite_mentions("<@U2> hi") == "@U2 hi"
    assert rewrite_mentions("<@U2> hi", {"U2": "Priya"}) == "@Priya hi"
    assert rewrite_mentions("") == ""


def test_mentions_user_is_case_insensitive_and_safe() -> None:
    assert mentions_user("<@b0bot> hey", BOT) is True
    assert mentions_user("<@U9> hey", BOT) is False
    assert mentions_user("hey", BOT) is False
    assert mentions_user("<@B0BOT>", None) is False


def test_team_id_from_envelope_variants() -> None:
    assert team_id_from_envelope({"team_id": "T1"}) == "T1"
    assert team_id_from_envelope({"authorizations": [{"team_id": "T2"}]}) == "T2"
    assert team_id_from_envelope({"event": {"team": "T3"}}) == "T3"
    assert team_id_from_envelope({}) is None
    assert team_id_from_envelope({"authorizations": []}) is None
