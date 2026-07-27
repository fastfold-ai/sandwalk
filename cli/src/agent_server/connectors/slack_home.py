"""Slack App Home tab (relay / distributed app).

Content is pushed with ``views.publish`` when the user opens the Home tab.
Sessions and status come from the local desktop — nothing is fetched over
HTTPS except the one static outbound link (the Fastfold integration page).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timezone

INTEGRATION_URL = "https://cloud.fastfold.ai/integrations/sandwalk"
RECENT_LIMIT = 5

_RELAY_LABEL = {
    "live": (":white_check_mark:", "Connected to Fastfold"),
    "reconnecting": (":large_yellow_circle:", "Reconnecting…"),
    "signed_out": (":warning:", "Fastfold account not linked"),
    "auth_expired": (":warning:", "Fastfold sign-in expired"),
    "off": (":black_circle:", "Not connected"),
}


@dataclass(frozen=True)
class HomeSessionRow:
    title: str
    source_label: str | None = None
    updated_at: datetime | None = None
    # Session id, used to link the title to the local web UI. Omitted for
    # rows built before this field existed — the title just isn't a link then.
    id: str | None = None


@dataclass(frozen=True)
class HomeStatus:
    """Relay + Fastfold account state, as :meth:`ConnectorService.status` sees it."""

    relay_state: str = "off"
    relay_detail: str | None = None
    team_name: str | None = None
    account_email: str | None = None
    account_user_id: str | None = None


def is_home_opened(event: dict) -> bool:
    return (
        isinstance(event, dict)
        and str(event.get("type") or "") == "app_home_opened"
        and str(event.get("tab") or "") == "home"
    )


def user_ref(event: dict) -> str | None:
    if not isinstance(event, dict):
        return None
    return str(event.get("user") or "").strip() or None


def _relative(when: datetime | None) -> str:
    if when is None:
        return ""
    stamp = when if when.tzinfo is not None else when.replace(tzinfo=UTC)
    seconds = max(0, int((datetime.now(UTC) - stamp.astimezone(UTC)).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def dashboard_base_url() -> str:
    """Base URL of the local Sandwalk web UI.

    The menubar app sets ``SANDWALK_DASHBOARD_BASE_URL`` to wherever it is
    actually serving the dashboard — the bundled build on the API port in
    production, or the separate Vite dev server (default ``8969``) in
    development. Falls back to the API host/port when that is unset (e.g.
    running ``sandwalk serve`` directly), which only works if the dashboard
    happens to be bundled into that same process.

    This only resolves for the person whose own desktop published this Home
    view, which is exactly who is looking at it.
    """
    override = os.environ.get("SANDWALK_DASHBOARD_BASE_URL", "").strip()
    if override:
        return override.rstrip("/")
    host = os.environ.get("FASTFOLD_SERVE_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("FASTFOLD_SERVE_PORT", "8787").strip() or "8787"
    return f"http://{host}:{port}"


def session_url(session_id: str) -> str:
    """Local web UI link for a specific session."""
    return f"{dashboard_base_url()}/agents/{session_id}"


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _context(text: str) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}


def status_lines(status: HomeStatus | None) -> list[str]:
    """Sazabi-style status block: bold headline, then plain labeled rows.

    Public so `/sandwalk status` renders the exact same lines as the Home
    tab's Integration status section.
    """
    status = status or HomeStatus()
    icon, label = _RELAY_LABEL.get(status.relay_state, _RELAY_LABEL["off"])
    lines = [f"{icon} *{label}*"]
    if status.team_name:
        lines.append(f"Slack workspace: `{status.team_name}`")
    account = status.account_email or status.account_user_id
    if account:
        lines.append(f"Fastfold account: `{account}`")
    if status.relay_detail and status.relay_state != "live":
        lines.append(f"_{status.relay_detail}_")
    return lines


def build_home_blocks(
    sessions: list[HomeSessionRow],
    *,
    bot_name: str | None = None,
    status: HomeStatus | None = None,
) -> list[dict]:
    """Block Kit for the Home tab — welcome, how-to, status, recent Slack sessions."""
    handle = (bot_name or "Sandwalk").lstrip("@")
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Welcome to Sandwalk :wave:", "emoji": True},
        },
        _context("Your research agent, in your Slack threads."),
        {"type": "divider"},
        _section("*Getting started with Sandwalk*"),
        _section(
            f"• Message *@{handle}* in a DM — no @mention needed\n"
            f"• Or `@{handle}` in a channel the bot has joined\n"
            "• Keep replying in the same thread without tagging again"
        ),
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "Open Sandwalk", "emoji": True},
                    "url": f"{dashboard_base_url()}/",
                    "action_id": "sandwalk_open_app",
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Fastfold Integration",
                        "emoji": True,
                    },
                    "url": INTEGRATION_URL,
                    "action_id": "sandwalk_open_integration",
                },
            ],
        },
        {"type": "divider"},
        _section("*Integration status*"),
        _section("\n".join(status_lines(status))),
        {"type": "divider"},
        _section("*Recent threads*"),
    ]

    recent = sessions[:RECENT_LIMIT]
    if not recent:
        blocks.append(_context("No Slack sessions yet. Send a DM or mention the bot to start one."))
        return blocks

    for item in recent:
        title = (item.title or "Untitled").strip() or "Untitled"
        if len(title) > 80:
            title = title[:77] + "…"
        # Plain link, no bold — Slack does not combine `*<url|text>*` cleanly.
        title_text = f"<{session_url(item.id)}|{title}>" if item.id else title
        meta = item.source_label or "Slack"
        when = _relative(item.updated_at)
        suffix = f" · Updated {when}" if when else ""
        blocks.append(_section(title_text))
        blocks.append(_context(f"{meta}{suffix}"))

    blocks.append(_context("Click a thread above to open it in the Sandwalk app."))
    return blocks


def build_home_view(
    sessions: list[HomeSessionRow],
    *,
    bot_name: str | None = None,
    status: HomeStatus | None = None,
) -> dict:
    return {
        "type": "home",
        "blocks": build_home_blocks(sessions, bot_name=bot_name, status=status),
    }
