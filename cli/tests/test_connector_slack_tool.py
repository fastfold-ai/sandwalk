"""slack.send_message tool and its approval gate."""

from __future__ import annotations

from pathlib import Path

import pytest

import agent.config as agent_config
from agent.hitl.config import (
    SLACK_SEND_TOOL,
    grant_key_for_slack_target,
    slack_send_when,
    slack_target_is_trusted,
)
from agent.hitl.grants import grant_key_for_action
from agent_server.store import AgentStore
from tools import slack as slack_tool


class Request:
    """Minimal stand-in for the Deep Agents interrupt request object."""

    def __init__(self, **args: object) -> None:
        self.tool_call = {"name": SLACK_SEND_TOOL, "args": args}


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AgentStore:
    monkeypatch.setattr(agent_config, "CONFIG_DIR", tmp_path)
    store = AgentStore(tmp_path / "agent-server.db")
    store.upsert_slack_workspace(
        team_id="T1", mode="socket", bot_token="xoxb-secret", bot_user_id="BBOT"
    )
    return store


@pytest.fixture()
def posted(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []

    def fake_post(path: str, token: str, payload: dict) -> dict:
        calls.append({"path": path, "token": token, "payload": payload})
        return {"ok": True, "channel": payload["channel"], "ts": "1712000111.000200"}

    monkeypatch.setattr(slack_tool, "_post", fake_post)
    return calls


def test_send_threads_the_reply(store: AgentStore, posted: list[dict]) -> None:
    result = slack_tool.send_message(
        target="slack:T1/C1:1712000000.000100", text="Here you go"
    )

    assert result["ok"] is True
    assert posted[0]["token"] == "xoxb-secret"
    payload = posted[0]["payload"]
    assert payload["channel"] == "C1"
    assert payload["thread_ts"] == "1712000000.000100"
    assert payload["text"] == "Here you go"


def test_send_to_a_channel_omits_thread_ts(
    store: AgentStore, posted: list[dict]
) -> None:
    slack_tool.send_message(target="slack:T1/C1", text="hi")
    assert "thread_ts" not in posted[0]["payload"]


def test_send_rejects_a_malformed_target(store: AgentStore, posted: list[dict]) -> None:
    result = slack_tool.send_message(target="not-a-target", text="hi")
    assert result["ok"] is False
    assert "Invalid Slack target" in result["summary"]
    assert posted == []


def test_send_rejects_empty_text(store: AgentStore, posted: list[dict]) -> None:
    result = slack_tool.send_message(target="slack:T1/C1", text="   ")
    assert result["ok"] is False
    assert posted == []


def test_send_to_an_unconnected_workspace(
    store: AgentStore, posted: list[dict]
) -> None:
    result = slack_tool.send_message(target="slack:T-other/C1", text="hi")
    assert result["ok"] is False
    assert "not connected" in result["summary"]
    assert posted == []


def test_send_from_a_disabled_workspace(store: AgentStore, posted: list[dict]) -> None:
    store.set_slack_workspace_flags("T1", enabled=False)
    result = slack_tool.send_message(target="slack:T1/C1", text="hi")
    assert result["ok"] is False
    assert "disabled" in result["summary"]


def test_send_without_a_stored_token(store: AgentStore, posted: list[dict]) -> None:
    store.clear_slack_bot_token("T1")
    result = slack_tool.send_message(target="slack:T1/C1", text="hi")
    assert result["ok"] is False
    assert "Reconnect" in result["summary"]


def test_not_in_channel_gives_an_actionable_message(
    store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        slack_tool, "_post", lambda *_a, **_k: {"ok": False, "error": "not_in_channel"}
    )
    result = slack_tool.send_message(target="slack:T1/C1", text="hi")
    assert result["ok"] is False
    assert "/invite" in result["summary"]


def test_slack_api_errors_surface(
    store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        slack_tool, "_post", lambda *_a, **_k: {"ok": False, "error": "rate_limited"}
    )
    result = slack_tool.send_message(target="slack:T1/C1", text="hi")
    assert result["ok"] is False
    assert "rate_limited" in result["summary"]


def test_post_unpacks_the_http_client_contract(
    store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`request_json` returns (body, error) — not a body.

    The earlier tests stubbed `_post` itself, so nothing exercised this seam and
    a tuple reached `.get("ok")` in production.
    """
    calls: list[dict] = []

    def fake_request_json(method, url, **kwargs):  # type: ignore[no-untyped-def]
        calls.append({"method": method, "url": url, **kwargs})
        return {"ok": True, "channel": "C1", "ts": "1712000111.000200"}, None

    monkeypatch.setattr("tools.http_client.request_json", fake_request_json)

    result = slack_tool.send_message(
        target="slack:T1/C1:1712000000.000100", text="Here you go"
    )

    assert result["ok"] is True
    assert result["ts"] == "1712000111.000200"
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"].endswith("/chat.postMessage")
    assert calls[0]["json"]["thread_ts"] == "1712000000.000100"


def test_post_folds_transport_errors_into_the_slack_shape(
    store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "tools.http_client.request_json",
        lambda *a, **k: (None, "connection refused"),
    )
    result = slack_tool.send_message(target="slack:T1/C1", text="hi")
    assert result["ok"] is False
    assert "connection refused" in result["summary"]


def test_post_rejects_a_non_dict_body(
    store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "tools.http_client.request_json", lambda *a, **k: (["nope"], None)
    )
    result = slack_tool.send_message(target="slack:T1/C1", text="hi")
    assert result["ok"] is False


# --- block kit rendering ---------------------------------------------------


def test_send_posts_block_kit_with_a_text_fallback(
    store: AgentStore, posted: list[dict]
) -> None:
    slack_tool.send_message(target="slack:T1/C1", text="**hi** there")
    payload = posted[0]["payload"]

    assert payload["blocks"][0]["text"]["text"] == "*hi* there"
    # Without `text`, Slack notifications read "This content can't be displayed".
    assert payload["text"] == "*hi* there"


def test_send_splits_a_long_reply_across_sections(
    store: AgentStore, posted: list[dict]
) -> None:
    slack_tool.send_message(target="slack:T1/C1", text="\n\n".join(["y" * 2500] * 3))
    sections = [b for b in posted[0]["payload"]["blocks"] if b["type"] == "section"]

    assert len(sections) == 3
    assert all(len(b["text"]["text"]) <= 3000 for b in sections)


def test_send_names_the_specialist_that_answered(
    store: AgentStore, posted: list[dict]
) -> None:
    specialist = store.get_specialist_by_slug("fast-computational-scientist")
    assert specialist is not None
    session = store.create_session(
        title="Slack", workspace_path=None, source="slack"
    )
    store.update_session(
        session.id, specialist_id=specialist.id, update_specialist_id=True
    )
    target = "slack:T1/C1:1712000000.000100"
    store.set_slack_mention_session(
        thread_target=target, session_id=session.id, channel="slack:T1/C1"
    )

    slack_tool.send_message(target=target, text="done")
    footer = posted[0]["payload"]["blocks"][-1]

    assert footer["type"] == "context"
    assert specialist.name in footer["elements"][0]["text"]


def test_send_omits_the_footer_without_a_specialist(
    store: AgentStore, posted: list[dict]
) -> None:
    slack_tool.send_message(target="slack:T1/C1", text="done")
    assert not any(
        b["type"] == "context" for b in posted[0]["payload"]["blocks"]
    )


# --- approval gating -------------------------------------------------------


def test_own_mention_thread_is_trusted(store: AgentStore) -> None:
    session = store.create_session(title="Slack", workspace_path=None, source="slack")
    target = "slack:T1/C1:1712000000.000100"
    store.set_slack_mention_session(
        thread_target=target, session_id=session.id, channel="slack:T1/C1"
    )

    assert slack_target_is_trusted(target, session.id) is True


def test_another_sessions_thread_is_not_trusted(store: AgentStore) -> None:
    mine = store.create_session(title="Mine", workspace_path=None)
    theirs = store.create_session(title="Theirs", workspace_path=None)
    target = "slack:T1/C1:1712000000.000100"
    store.set_slack_mention_session(
        thread_target=target, session_id=theirs.id, channel="slack:T1/C1"
    )

    assert slack_target_is_trusted(target, mine.id) is False


def test_unknown_target_is_not_trusted(store: AgentStore) -> None:
    session = store.create_session(title="Slack", workspace_path=None)
    assert slack_target_is_trusted("slack:T1/C-other", session.id) is False
    assert slack_target_is_trusted("", session.id) is False
    assert slack_target_is_trusted("slack:T1/C1", None) is False


def test_reply_in_own_thread_skips_approval(
    store: AgentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = store.create_session(title="Slack", workspace_path=None, source="slack")
    target = "slack:T1/C1:1712000000.000100"
    store.set_slack_mention_session(
        thread_target=target, session_id=session.id, channel="slack:T1/C1"
    )

    from agent.hitl.context import reset_hitl_context, set_hitl_context

    token = set_hitl_context(session_id=session.id, headless=True)
    try:
        assert slack_send_when(Request(target=target, text="hi")) is False
        # A different destination is the agent choosing where to post — still gated.
        assert slack_send_when(Request(target="slack:T1/C-other", text="hi")) is True
    finally:
        reset_hitl_context(token)


def test_send_without_a_session_context_is_gated(store: AgentStore) -> None:
    assert slack_send_when(Request(target="slack:T1/C1", text="hi")) is True


def test_grant_keys_are_scoped_per_destination() -> None:
    a = grant_key_for_slack_target("slack:T1/C1")
    b = grant_key_for_slack_target("slack:T1/C2")
    assert a != b
    assert grant_key_for_slack_target("") is None

    # Approving one channel must not authorize another.
    action = {"name": SLACK_SEND_TOOL, "args": {"target": "slack:T1/C1"}}
    assert grant_key_for_action(action) == a
