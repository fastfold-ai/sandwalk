"""Slack workspace directory (people and channels), cached in memory.

Powers the pickers so nobody has to hand-type a ``U0123`` id. ``users.list``
is rate limited and rarely changes, so results are cached per workspace.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

logger = logging.getLogger("agent_server.connectors.directory")

_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class SlackPerson:
    id: str
    name: str
    handle: str | None = None
    avatar_url: str | None = None
    is_bot: bool = False


@dataclass(frozen=True)
class SlackChannelEntry:
    id: str
    name: str
    is_private: bool = False


@dataclass
class _Cached:
    people: list[SlackPerson]
    channels: list[SlackChannelEntry]
    fetched_at: float


_CACHE: dict[str, _Cached] = {}


def _why(exc: Exception) -> str:
    """Pull Slack's actual error out of an SDK exception.

    ``SlackApiError`` stringifies to "the request failed (status: 200)", which
    hides the part that matters — usually ``missing_scope`` plus the scope the
    call needed.
    """
    body = getattr(getattr(exc, "response", None), "data", None)
    if isinstance(body, dict):
        error = str(body.get("error") or "").strip()
        needed = str(body.get("needed") or "").strip()
        if error and needed:
            return f"{error} (needs {needed})"
        if error:
            return error
    return str(exc)


def _client(bot_token: str):  # type: ignore[no-untyped-def]
    from slack_sdk.web.async_client import AsyncWebClient

    return AsyncWebClient(
        token=bot_token,
        base_url=os.environ.get("SLACK_API_URL", "https://slack.com/api/"),
    )


def _person_from_member(member: dict) -> SlackPerson | None:
    user_id = str(member.get("id") or "").strip()
    if not user_id or member.get("deleted"):
        return None
    profile = member.get("profile") if isinstance(member.get("profile"), dict) else {}
    display = str(profile.get("display_name") or "").strip()
    real = str(profile.get("real_name") or member.get("real_name") or "").strip()
    handle = str(member.get("name") or "").strip() or None
    return SlackPerson(
        id=user_id,
        name=display or real or handle or user_id,
        handle=handle,
        avatar_url=str(profile.get("image_48") or "").strip() or None,
        is_bot=bool(member.get("is_bot")) or user_id == "USLACKBOT",
    )


async def fetch_directory(
    team_id: str, bot_token: str, *, force: bool = False
) -> tuple[list[SlackPerson], list[SlackChannelEntry]]:
    cached = _CACHE.get(team_id)
    if cached and not force and (time.time() - cached.fetched_at) < _TTL_SECONDS:
        return cached.people, cached.channels

    client = _client(bot_token)
    people: list[SlackPerson] = []
    channels: list[SlackChannelEntry] = []

    try:
        response = await client.users_list(limit=200)
        for member in response.get("members") or []:
            if not isinstance(member, dict):
                continue
            person = _person_from_member(member)
            # Bots cannot mention the agent, so keep them out of the picker.
            if person is not None and not person.is_bot:
                people.append(person)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Slack users.list failed for %s: %s", team_id, _why(exc))

    try:
        response = await client.conversations_list(
            exclude_archived=True,
            types="public_channel,private_channel",
            limit=200,
        )
        for item in response.get("channels") or []:
            if not isinstance(item, dict):
                continue
            channel_id = str(item.get("id") or "").strip()
            name = str(item.get("name") or "").strip()
            if channel_id and name:
                channels.append(
                    SlackChannelEntry(
                        id=channel_id,
                        name=name,
                        is_private=bool(item.get("is_private")),
                    )
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Slack conversations.list failed for %s: %s", team_id, _why(exc)
        )

    people.sort(key=lambda item: item.name.lower())
    channels.sort(key=lambda item: item.name.lower())
    _CACHE[team_id] = _Cached(people=people, channels=channels, fetched_at=time.time())
    return people, channels


def clear_cache(team_id: str | None = None) -> None:
    if team_id is None:
        _CACHE.clear()
    else:
        _CACHE.pop(team_id, None)
