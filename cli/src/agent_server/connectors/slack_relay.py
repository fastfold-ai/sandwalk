"""Relay client for one-click Slack workspaces.

Socket Mode cannot back a shared, distributed app: app-level tokens are
per-app rather than per-install, so every desktop would hold the same token and
receive every other workspace's events. One-click installs therefore deliver
through FastFold Cloud, which owns the Events API Request URL and forwards each
event over this WebSocket.

Only inbound travels this way. The bot token is handed to the desktop after
OAuth, so replies, reactions and the user directory keep using Slack directly
and behave exactly as they do in Socket Mode.

One socket carries every workspace the user installed, so this owns a registry
of per-team adapters and dispatches by ``team_id``. Each adapter presents the
same surface :class:`SlackSocketAdapter` does, which is what lets
``ConnectorService`` treat the two modes alike.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import Awaitable, Callable

from agent_server.connectors.gateway import InboundMessage
from agent_server.connectors.slack_events import event_to_inbound

logger = logging.getLogger("agent_server.connectors.slack")

InboundHandler = Callable[[InboundMessage], Awaitable[None]]

# Backoff between reconnect attempts, capped so a long outage keeps retrying
# without hammering the cloud.
_BACKOFF_START = 1.0
_BACKOFF_MAX = 60.0

# Matches the relay's own idle expectations; the cloud pings independently.
_OPEN_TIMEOUT = 20.0


def _relay_url(base_url: str) -> str:
    root = base_url.rstrip("/")
    if root.startswith("https://"):
        return "wss://" + root[len("https://") :] + "/v1/slack/relay"
    if root.startswith("http://"):
        return "ws://" + root[len("http://") :] + "/v1/slack/relay"
    return root + "/v1/slack/relay"


class SlackRelayWorkspace:
    """Per-team half of the relay, mirroring the Socket Mode adapter surface.

    ``ConnectorService`` calls ``bot_user_id``, ``connected`` and
    ``set_reaction`` on whatever is registered for a team. Reactions go straight
    to Slack with the local bot token, exactly as in Socket Mode.
    """

    def __init__(self, *, team_id: str, bot_token: str, bot_user_id: str | None) -> None:
        self.team_id = team_id
        self.bot_token = bot_token
        self._bot_user_id = bot_user_id
        self._client = None
        self.user_names: dict[str, str] = {}
        self.user_avatars: dict[str, str] = {}
        self.channel_names: dict[str, str] = {}

    @property
    def bot_user_id(self) -> str | None:
        return self._bot_user_id

    @property
    def connected(self) -> bool:
        # Liveness belongs to the shared socket, which sets this.
        return getattr(self, "_live", False)

    def _web(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            from slack_sdk.web.async_client import AsyncWebClient

            self._client = AsyncWebClient(
                token=self.bot_token,
                base_url=os.environ.get("SLACK_API_URL", "https://slack.com/api/"),
            )
        return self._client

    async def load_directory(self, *, force: bool = False) -> None:
        from agent_server.connectors.directory import fetch_directory

        try:
            people, channels = await fetch_directory(
                self.team_id, self.bot_token, force=force
            )
        except Exception as exc:  # noqa: BLE001 - names are a nicety
            logger.warning(
                "Could not load the Slack directory for %s: %s", self.team_id, exc
            )
            return
        self.user_names = {person.id: person.name for person in people}
        self.user_avatars = {
            person.id: person.avatar_url for person in people if person.avatar_url
        }
        self.channel_names = {channel.id: channel.name for channel in channels}

    async def set_reaction(
        self, *, channel_id: str, ts: str, add: str | None, remove: str | None = None
    ) -> None:
        """Best effort, same contract as the Socket Mode adapter."""
        if not channel_id or not ts:
            return
        client = self._web()
        if remove:
            with contextlib.suppress(Exception):
                await client.reactions_remove(channel=channel_id, timestamp=ts, name=remove)
        if add:
            try:
                await client.reactions_add(channel=channel_id, timestamp=ts, name=add)
            except Exception as exc:  # noqa: BLE001
                if "already_reacted" not in str(exc):
                    logger.debug("Slack reaction %s failed: %s", add, exc)

    async def disconnect(self) -> None:
        self._client = None


class SlackRelayClient:
    """The shared WebSocket to FastFold Cloud, plus its per-team adapters."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        on_message: InboundHandler,
        on_state: Callable[[str, str | None], None] | None = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self._on_message = on_message
        self._on_state = on_state
        self._workspaces: dict[str, SlackRelayWorkspace] = {}
        self._task: asyncio.Task | None = None
        self._closing = False
        self._live = False

    # --- workspace registry ---------------------------------------------

    def add_workspace(self, workspace: SlackRelayWorkspace) -> None:
        workspace._live = self._live  # type: ignore[attr-defined]
        self._workspaces[workspace.team_id] = workspace

    def remove_workspace(self, team_id: str) -> None:
        self._workspaces.pop(team_id, None)

    def get(self, team_id: str) -> SlackRelayWorkspace | None:
        return self._workspaces.get(team_id)

    @property
    def teams(self) -> list[str]:
        return list(self._workspaces)

    @property
    def connected(self) -> bool:
        return self._live

    # --- lifecycle --------------------------------------------------------

    async def start(self) -> None:
        if self._task is not None:
            return
        self._closing = False
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._closing = True
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None
        for workspace in self._workspaces.values():
            await workspace.disconnect()
        self._workspaces.clear()
        self._set_live(False)
        self._state("off", None)

    def _set_live(self, live: bool) -> None:
        self._live = live
        for workspace in self._workspaces.values():
            workspace._live = live  # type: ignore[attr-defined]

    def _state(self, state: str, detail: str | None) -> None:
        if self._on_state is not None:
            self._on_state(state, detail)

    async def _run(self) -> None:
        backoff = _BACKOFF_START
        while not self._closing:
            try:
                await self._session()
                backoff = _BACKOFF_START
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                if self._closing:
                    return
                self._set_live(False)
                # An API key the cloud rejects will not fix itself by retrying,
                # so say so rather than looping silently behind "reconnecting".
                if _is_auth_failure(exc):
                    self._state("auth_expired", "FastFold rejected the API key.")
                else:
                    self._state("reconnecting", str(exc)[:200])
                logger.warning("Slack relay disconnected: %s", exc)
            if self._closing:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)

    async def _session(self) -> None:
        import websockets

        url = _relay_url(self.base_url)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        # The header kwarg was renamed between websockets releases; support both
        # so this does not depend on which one the environment resolved.
        try:
            connect = websockets.connect(url, additional_headers=headers, open_timeout=_OPEN_TIMEOUT)
        except TypeError:
            connect = websockets.connect(url, extra_headers=headers, open_timeout=_OPEN_TIMEOUT)

        async with connect as socket:
            self._set_live(True)
            self._state("live", None)
            logger.info("Slack relay connected for %s workspace(s)", len(self._workspaces))
            async for raw in socket:
                await self._handle_frame(raw)

    async def _handle_frame(self, raw) -> None:  # type: ignore[no-untyped-def]
        try:
            payload = json.loads(raw)
        except Exception:  # noqa: BLE001
            logger.debug("Ignoring unparseable relay frame")
            return
        if not isinstance(payload, dict):
            return
        if payload.get("type") == "relay.ready":
            return

        team_id = _team_id_from_envelope(payload)
        workspace = self._workspaces.get(team_id or "")
        if workspace is None:
            # An install this desktop does not know about yet - the user may
            # have connected it elsewhere.
            logger.debug("Relay event for unknown team %s", team_id)
            return

        event = payload.get("event")
        if not isinstance(event, dict):
            return
        if not _known(event, workspace):
            await workspace.load_directory(force=True)

        inbound = event_to_inbound(
            event,
            team_id=team_id or workspace.team_id,
            bot_user_id=workspace.bot_user_id,
            channel_names=workspace.channel_names,
            user_names=workspace.user_names,
            user_avatars=workspace.user_avatars,
        )
        if inbound is None:
            return
        try:
            await self._on_message(inbound)
        except Exception:
            logger.exception("Slack relay handler failed for team %s", team_id)


def _known(event: dict, workspace: SlackRelayWorkspace) -> bool:
    user_id = str(event.get("user") or "").strip()
    channel_id = str(event.get("channel") or "").strip()
    return (not user_id or user_id in workspace.user_names) and (
        not channel_id or channel_id in workspace.channel_names
    )


def _team_id_from_envelope(payload: dict) -> str | None:
    """Same shape the cloud parsed; re-derived here rather than trusted blindly."""
    direct = str(payload.get("team_id") or "").strip()
    if direct:
        return direct
    authorizations = payload.get("authorizations")
    if isinstance(authorizations, list) and authorizations:
        first = authorizations[0]
        if isinstance(first, dict):
            team = str(first.get("team_id") or "").strip()
            if team:
                return team
    event = payload.get("event")
    if isinstance(event, dict):
        team = str(event.get("team") or "").strip()
        if team:
            return team
    return None


def _is_auth_failure(exc: Exception) -> bool:
    text = str(exc).lower()
    return "4401" in text or "401" in text or "unauthorized" in text
