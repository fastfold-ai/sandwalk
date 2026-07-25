"""Slack outbound tools — replying into the thread a mention came from.

The bot token lives in the local connector store, never in the tool arguments, so
the model can only address workspaces the user has actually connected.
"""

from __future__ import annotations

import os

from tools import registry

_SLACK_API = "https://slack.com/api"


def _api_base() -> str:
    # Overridable so tests can point at a fake Slack.
    return os.environ.get("SLACK_API_URL", _SLACK_API).rstrip("/")


def _resolve_tokens(team_id: str) -> tuple[str | None, str | None]:
    from agent_server.store import AgentStore

    store = AgentStore()
    try:
        workspace = store.get_slack_workspace(team_id)
        if workspace is None:
            return None, f"Slack workspace {team_id} is not connected."
        if not workspace.enabled:
            return None, f"Slack workspace {team_id} is disabled."
        bot_token, _ = store.get_slack_tokens(team_id)
        if not bot_token:
            return None, (
                f"No Slack bot token stored for {team_id}. Reconnect the workspace."
            )
        return bot_token, None
    finally:
        store.close()


def _post(path: str, token: str, payload: dict) -> dict:
    """POST to the Slack Web API and return the parsed body.

    ``request_json`` returns ``(body, error)``; a transport failure is folded
    into Slack's own ``{ok: false, error: ...}`` shape so callers have one thing
    to check.
    """
    from tools.http_client import request_json

    body, error = request_json(
        "POST",
        f"{_api_base()}/{path}",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    if error:
        return {"ok": False, "error": error}
    if not isinstance(body, dict):
        return {"ok": False, "error": "Slack returned an unexpected response."}
    return body


@registry.register(
    name="slack.send_message",
    description="Reply into a Slack channel or thread using a reply target handle",
    category="slack",
    parameters={
        "target": (
            "Reply handle from the incoming message, e.g. "
            "slack:T0123/C0456:1712000000.000100"
        ),
        "text": "Message text (Slack mrkdwn)",
    },
    usage_guide=(
        "You are answering a Slack message and the incoming message gave you a "
        "reply→ handle. Pass that handle unchanged as `target` so the answer "
        "lands in the right thread."
    ),
)
def send_message(target: str, text: str, **kwargs) -> dict:
    """Post a message to Slack, threading it when the target names a thread."""
    from agent_server.connectors.addressing import parse_target

    body = (text or "").strip()
    if not body:
        return {"summary": "Nothing sent — the message text was empty.", "ok": False}

    try:
        parsed = parse_target(target)
    except ValueError as exc:
        return {"summary": f"Invalid Slack target: {exc}", "ok": False}

    token, error = _resolve_tokens(parsed.team_id)
    if token is None:
        return {"summary": error or "Slack is not connected.", "ok": False}

    payload: dict[str, object] = {
        "channel": parsed.channel_id,
        "text": body,
        "unfurl_links": False,
        "unfurl_media": False,
    }
    if parsed.thread_ts:
        payload["thread_ts"] = parsed.thread_ts

    response = _post("chat.postMessage", token, payload)
    if not response.get("ok"):
        detail = str(response.get("error") or response.get("summary") or "unknown error")
        if detail == "not_in_channel":
            return {
                "summary": (
                    "Slack rejected the message: the bot is not in that channel. "
                    "Invite it with /invite @Sandwalk."
                ),
                "ok": False,
                "error": detail,
            }
        return {"summary": f"Slack rejected the message: {detail}", "ok": False,
                "error": detail}

    return {
        "summary": f"Replied in Slack ({parsed.channel_id}).",
        "ok": True,
        "channel": str(response.get("channel") or parsed.channel_id),
        "ts": str(response.get("ts") or "") or None,
    }
