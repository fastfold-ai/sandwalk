"""Pure mapping from raw Slack event payloads to :class:`InboundMessage`.

Both inbound paths deliver the same Slack event shape — Socket Mode hands it over
a websocket, the cloud relay forwards it from the Events API — so this mapper is
shared and deliberately free of any SDK import, which also makes it testable with
plain dicts.
"""

from __future__ import annotations

import re

from agent_server.connectors.gateway import InboundMessage

# Slack encodes an @-mention as <@U0123>, legacy form <@U0123|display>.
_MENTION = re.compile(r"<@([UWB][A-Z0-9]+)(?:\|([^>]*))?>", re.IGNORECASE)

# Subtypes that are edits, joins, deletions and similar — never a user request.
# `file_share` is a genuine user message with an attachment, so it is allowed.
_ALLOWED_SUBTYPES = {None, "", "file_share", "thread_broadcast"}


def mentions_user(text: str, user_id: str | None) -> bool:
    """Whether the raw text @-mentions ``user_id``."""
    if not user_id:
        return False
    return any(
        match.group(1).upper() == user_id.upper() for match in _MENTION.finditer(text or "")
    )


def rewrite_mentions(text: str, names: dict[str, str] | None = None) -> str:
    """Turn ``<@U0123>`` tokens into readable ``@name`` for the agent transcript."""
    lookup = {key.upper(): value for key, value in (names or {}).items()}

    def replace(match: re.Match[str]) -> str:
        user_id = match.group(1).upper()
        inline = (match.group(2) or "").strip()
        return f"@{lookup.get(user_id) or inline or user_id}"

    return _MENTION.sub(replace, text or "")


def event_to_inbound(
    event: dict,
    *,
    team_id: str,
    bot_user_id: str | None = None,
    channel_names: dict[str, str] | None = None,
    user_names: dict[str, str] | None = None,
    user_avatars: dict[str, str] | None = None,
) -> InboundMessage | None:
    """Map a Slack ``message``/``app_mention`` event, or ``None`` to skip it."""
    if not isinstance(event, dict):
        return None

    # Bot echoes would otherwise loop straight back into the agent.
    if event.get("bot_id"):
        return None
    subtype = event.get("subtype")
    if subtype not in _ALLOWED_SUBTYPES:
        return None

    user_id = str(event.get("user") or "").strip()
    channel_id = str(event.get("channel") or "").strip()
    ts = str(event.get("ts") or "").strip()
    raw_text = str(event.get("text") or "")
    if not user_id or not channel_id or not ts or not raw_text.strip():
        return None
    if bot_user_id and user_id.upper() == bot_user_id.upper():
        return None

    # Mention detection runs on the raw token form, before rewriting for display.
    mentions_me = event.get("type") == "app_mention" or mentions_user(
        raw_text, bot_user_id
    )

    thread_ts = str(event.get("thread_ts") or "").strip() or None
    # Slack sets thread_ts == ts on the parent; treat that as "not in a thread".
    if thread_ts == ts:
        thread_ts = None

    return InboundMessage(
        team_id=str(team_id or "").strip(),
        channel_id=channel_id,
        user_id=user_id,
        text=rewrite_mentions(raw_text, user_names).strip(),
        ts=ts,
        thread_ts=thread_ts,
        channel_name=(channel_names or {}).get(channel_id),
        user_name=(user_names or {}).get(user_id),
        user_avatar_url=(user_avatars or {}).get(user_id),
        mentions_me=mentions_me,
    )


def team_id_from_envelope(body: dict) -> str | None:
    """Pull the workspace id out of an Events API / Socket Mode envelope."""
    if not isinstance(body, dict):
        return None
    direct = str(body.get("team_id") or "").strip()
    if direct:
        return direct
    authorizations = body.get("authorizations")
    if isinstance(authorizations, list) and authorizations:
        first = authorizations[0]
        if isinstance(first, dict):
            team = str(first.get("team_id") or "").strip()
            if team:
                return team
    event = body.get("event")
    if isinstance(event, dict):
        team = str(event.get("team") or "").strip()
        if team:
            return team
    return None
