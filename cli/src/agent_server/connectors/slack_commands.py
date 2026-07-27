"""``/sandwalk`` slash command handling — relayed from FastFold Cloud.

The cloud has no access to a user's local Sandwalk data (sessions, allowlist,
parked requests), so it hands each command to the desktop as a
``{"type": "slash_command", ...}`` relay frame (see ``slack_relay.py``) and the
desktop posts the real answer to Slack's ``response_url`` webhook once it has
one — the same pattern Slack's own docs recommend for a command that can't
answer inside its 3-second budget.

``help`` is the one exception: the cloud answers it directly and a frame for
it should never actually reach here (see ``fastfold-cloud-backend``'s
``SlackCommandsView``).

Kept free of any store/service imports so it stays a pure, easily testable
module — the same shape as ``slack_home.py`` and ``slack_blocks.py``.
``ConnectorService`` is what actually fetches data and calls these builders.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass

from agent_server.connectors.slack_events import first_mentioned_user_id
from agent_server.connectors.slack_home import HomeSessionRow, HomeStatus, session_url, status_lines
from agent_server.models.connectors import SlackAllowedUser, SlackParkedMessage

logger = logging.getLogger("agent_server.connectors.slack")

RECENT_LIMIT = 5
PARKED_LIMIT = 10


@dataclass(frozen=True)
class SlashCommandRequest:
    command: str
    text: str
    team_id: str
    user_id: str
    channel_id: str
    response_url: str

    @property
    def args(self) -> list[str]:
        return self.text.split()

    @property
    def verb(self) -> str:
        return self.args[0].lower() if self.args else ""

    @property
    def rest(self) -> list[str]:
        return self.args[1:]


def parse_slash_command(payload: dict) -> SlashCommandRequest | None:
    """Build a request from a relay frame, or ``None`` if it is unusable."""
    if not isinstance(payload, dict):
        return None
    team_id = str(payload.get("team_id") or "").strip()
    response_url = str(payload.get("response_url") or "").strip()
    if not team_id or not response_url:
        return None
    return SlashCommandRequest(
        command=str(payload.get("command") or "").strip(),
        text=str(payload.get("text") or "").strip(),
        team_id=team_id,
        user_id=str(payload.get("user_id") or "").strip(),
        channel_id=str(payload.get("channel_id") or "").strip(),
        response_url=response_url,
    )


def render_status(status: HomeStatus | None) -> str:
    """Same lines the Home tab's Integration status section shows."""
    return "\n".join(status_lines(status))


def render_sessions(sessions: list[HomeSessionRow]) -> str:
    """Same data the Home tab's Recent Threads section shows."""
    if not sessions:
        return "No Slack sessions yet. Send a DM or mention the bot to start one."
    lines = ["*Recent threads*"]
    for item in sessions[:RECENT_LIMIT]:
        title = (item.title or "Untitled").strip() or "Untitled"
        if len(title) > 80:
            title = title[:77] + "…"
        link = f"<{session_url(item.id)}|{title}>" if item.id else title
        meta = item.source_label or "Slack"
        lines.append(f"• {link} — {meta}")
    return "\n".join(lines)


def render_people(people: list[SlackAllowedUser]) -> str:
    if not people:
        return "Nobody is on the People list yet — mentions and DMs wait for your OK first."
    lines = ["*People who can trigger Sandwalk*"]
    for person in people:
        name = person.display_name or person.slack_user_id
        lines.append(f"• {name} (`{person.slack_user_id}`)")
    return "\n".join(lines)


def render_allow_usage() -> str:
    return "Usage: `/sandwalk people allow @user`"


def render_allowed(user_id: str) -> str:
    return f"Approved <@{user_id}> — they can now trigger Sandwalk."


def render_people_usage() -> str:
    return "Usage: `/sandwalk people list` or `/sandwalk people allow @user`"


def render_parked(parked: list[SlackParkedMessage]) -> str:
    if not parked:
        return "No pending approval requests."
    lines = ["*Waiting on your approval*"]
    for item in parked[:PARKED_LIMIT]:
        who = item.user_name or item.slack_user_id
        snippet = item.text.strip()
        if len(snippet) > 80:
            snippet = snippet[:77] + "…"
        lines.append(f'• {who}: "{snippet}"')
    lines.append("_Approve from Sandwalk → Integrations → Slack._")
    return "\n".join(lines)


def render_unauthorized() -> str:
    return (
        "You're not on the People list yet, so I can't run that for you. "
        "Mention or DM Sandwalk once to get approved, then try again."
    )


def render_unknown(verb: str) -> str:
    return f"Unknown command `{verb}`. Try `/sandwalk help`."


def render_error() -> str:
    return "Something went wrong running that command."


def post_response(response_url: str, text: str, *, replace_original: bool = True) -> None:
    """POST the real answer to Slack's response_url webhook.

    Best effort - a failed webhook must not crash the relay's event loop; it
    just means the "Working on it..." placeholder never gets replaced.
    """
    body = json.dumps(
        {
            "response_type": "ephemeral",
            "text": text,
            "replace_original": replace_original,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        response_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=10)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Slack response_url POST failed: %s", exc)


__all__ = [
    "SlashCommandRequest",
    "parse_slash_command",
    "render_status",
    "render_sessions",
    "render_people",
    "render_allow_usage",
    "render_allowed",
    "render_people_usage",
    "render_parked",
    "render_unauthorized",
    "render_unknown",
    "render_error",
    "post_response",
    "first_mentioned_user_id",
]
