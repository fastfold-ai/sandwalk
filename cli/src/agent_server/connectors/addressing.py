"""Slack channel and thread addressing.

A bare Slack channel id is ambiguous: ``C0123`` only means something inside its
workspace, and one install can span several workspaces. So every address here is
team-qualified.

Grammar (colon-delimited, matching the reply-handle form the agent passes back)::

    slack:T0123/C0456                    a channel
    slack:T0123/C0456:1712000000.000100  a thread within that channel

Team and channel join with ``/`` rather than ``:`` so the colon grammar stays
unambiguous — Slack ids never contain either character.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CONNECTOR = "slack"

# Slack message timestamps look like 1712000000.000100
_TS = re.compile(r"^\d{1,12}\.\d{1,8}$")
# Permalink form used in archive URLs: p1712000000000100
_PERMALINK_TS = re.compile(r"^p(\d{10})(\d{6})$")
_ARCHIVE_URL = re.compile(
    r"^https?://[^/]+/archives/(?P<channel>[A-Z0-9]+)(?:/(?P<ts>p\d+))?",
    re.IGNORECASE,
)
# Slack's inline channel mention: <#C0123|general>
_CHANNEL_MENTION = re.compile(r"^<#(?P<channel>[A-Z0-9]+)(\|[^>]*)?>$", re.IGNORECASE)


@dataclass(frozen=True)
class SlackTarget:
    team_id: str
    channel_id: str
    thread_ts: str | None = None

    @property
    def channel(self) -> str:
        """Channel address without any thread component."""
        return format_channel(self.team_id, self.channel_id)

    @property
    def target(self) -> str:
        """Full reply handle, including the thread when present."""
        return format_target(self.team_id, self.channel_id, self.thread_ts)


def format_channel(team_id: str, channel_id: str) -> str:
    team = str(team_id or "").strip()
    channel = str(channel_id or "").strip()
    if not team or not channel:
        raise ValueError("team_id and channel_id are required")
    return f"{CONNECTOR}:{team}/{channel}"


def format_target(
    team_id: str, channel_id: str, thread_ts: str | None = None
) -> str:
    base = format_channel(team_id, channel_id)
    thread = str(thread_ts or "").strip()
    return f"{base}:{thread}" if thread else base


def parse_target(value: str) -> SlackTarget:
    """Parse ``slack:T0123/C0456[:ts]`` back into its parts."""
    raw = str(value or "").strip()
    connector, _, remainder = raw.partition(":")
    if connector != CONNECTOR or not remainder:
        raise ValueError(
            f"invalid Slack target {value!r} (expected 'slack:TEAM/CHANNEL[:ts]')"
        )
    chat_id, _, thread = remainder.partition(":")
    team, _, channel = chat_id.partition("/")
    if not team or not channel:
        raise ValueError(
            f"invalid Slack target {value!r} (expected 'slack:TEAM/CHANNEL[:ts]')"
        )
    return SlackTarget(
        team_id=team, channel_id=channel, thread_ts=(thread.strip() or None)
    )


def is_slack_target(value: str) -> bool:
    try:
        parse_target(value)
    except ValueError:
        return False
    return True


def thread_ts_from_permalink(value: str) -> str | None:
    """``p1712000000000100`` → ``1712000000.000100``."""
    match = _PERMALINK_TS.match(str(value or "").strip())
    if match is None:
        return None
    return f"{match.group(1)}.{match.group(2)}"


def resolve_channel_input(value: str, *, default_team_id: str | None = None) -> str:
    """Turn whatever a user pasted into a canonical channel address.

    Accepts the canonical form, a bare channel id, a ``<#C0123|name>`` mention, or
    a Slack archive URL. ``default_team_id`` supplies the workspace for the forms
    that do not carry one.
    """
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Channel is required.")

    # Already canonical, or team-less canonical (slack:C0123).
    if raw.lower().startswith(f"{CONNECTOR}:"):
        remainder = raw.partition(":")[2]
        chat_id = remainder.partition(":")[0]
        if "/" in chat_id:
            team, _, channel = chat_id.partition("/")
            if team and channel:
                return format_channel(team, channel)
        elif chat_id:
            return format_channel(_require_team(default_team_id), chat_id)
        raise ValueError(f"Could not read a channel from {value!r}.")

    url_match = _ARCHIVE_URL.match(raw)
    if url_match is not None:
        return format_channel(
            _require_team(default_team_id), url_match.group("channel")
        )

    mention_match = _CHANNEL_MENTION.match(raw)
    if mention_match is not None:
        return format_channel(
            _require_team(default_team_id), mention_match.group("channel")
        )

    # Bare channel id, optionally with a leading '#'.
    candidate = raw.lstrip("#").strip()
    if re.fullmatch(r"[A-Z][A-Z0-9]+", candidate, re.IGNORECASE):
        return format_channel(_require_team(default_team_id), candidate.upper())

    raise ValueError(
        f"Could not read a Slack channel from {value!r}. "
        "Paste a channel link, a channel id, or slack:TEAM/CHANNEL."
    )


def _require_team(team_id: str | None) -> str:
    team = str(team_id or "").strip()
    if not team:
        raise ValueError(
            "This channel format has no workspace in it — connect a workspace "
            "first or paste the slack:TEAM/CHANNEL form."
        )
    return team


def is_message_ts(value: str) -> bool:
    return bool(_TS.match(str(value or "").strip()))
