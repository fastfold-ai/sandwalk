"""Slack Socket Mode adapter (manual connect path).

Slack opens the connection to us, so this works from a laptop with no public URL
and no FastFold account. ``slack-bolt`` is imported lazily inside :meth:`connect`
so the module stays importable without the optional extra installed.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import os
import time
from collections.abc import Awaitable, Callable

from agent_server.connectors.gateway import InboundMessage
from agent_server.connectors.slack_events import event_to_inbound

logger = logging.getLogger("agent_server.connectors.slack")

InboundHandler = Callable[[InboundMessage], Awaitable[None]]

# slack_sdk keeps the socket alive in background tasks and usually reconnects on
# its own, but it can give up after a transient error during Slack's periodic
# connection cycling and leave a dead socket that never recovers. Poll for that.
_WATCHDOG_INTERVAL = 20.0

# `users.list` is rate limited, so cap how often an unrecognised id re-fetches.
_DIRECTORY_MIN_REFRESH = 60.0


def _session_looks_alive(client: object) -> bool:
    """Sync proxy for async SocketModeClient.is_connected (no ping/pong)."""
    session = getattr(client, "current_session", None)
    return (
        not getattr(client, "closed", True)
        and not getattr(client, "stale", True)
        and session is not None
        and not getattr(session, "closed", True)
    )


class SlackSocketAdapter:
    def __init__(
        self,
        *,
        team_id: str,
        bot_token: str,
        app_token: str,
        on_message: InboundHandler,
        watchdog_interval: float = _WATCHDOG_INTERVAL,
        auto_reconnect: bool = True,
    ) -> None:
        self.team_id = team_id
        self.bot_token = bot_token
        self.app_token = app_token
        self._on_message = on_message
        self._watchdog_interval = watchdog_interval
        self._auto_reconnect = auto_reconnect
        self._app = None
        self._socket = None
        self._task: asyncio.Task | None = None
        self._watchdog_task: asyncio.Task | None = None
        self._closing = False
        self._bot_user_id: str | None = None
        self._bot_name: str | None = None
        self.reconnects = 0
        self._user_names: dict[str, str] = {}
        self._user_avatars: dict[str, str] = {}
        self._channel_names: dict[str, str] = {}
        self._directory_loaded_at = 0.0

    @property
    def bot_user_id(self) -> str | None:
        return self._bot_user_id

    @property
    def connected(self) -> bool:
        client = getattr(self._socket, "client", None)
        if client is None:
            return False
        try:
            probe = client.is_connected()
            # Async slack_sdk: is_connected() is a coroutine. Awaiting here is
            # impossible from a sync status property; use session flags instead
            # (bool(coro) is always True and would hide disconnects).
            if inspect.isawaitable(probe):
                with contextlib.suppress(Exception):
                    probe.close()
                return _session_looks_alive(client)
            return bool(probe)
        except Exception:
            return False

    async def _connected(self) -> bool:
        client = getattr(self._socket, "client", None)
        if client is None:
            return False
        try:
            probe = client.is_connected()
            if inspect.isawaitable(probe):
                return bool(await probe)
            return bool(probe)
        except Exception:
            return False

    async def connect(self) -> bool:
        try:
            from slack_bolt.adapter.socket_mode.async_handler import (
                AsyncSocketModeHandler,
            )
            from slack_bolt.async_app import AsyncApp
            from slack_sdk.web.async_client import AsyncWebClient
        except ImportError:
            logger.warning(
                "slack-bolt is not installed — run `pip install sandwalk[slack]` "
                "to use Socket Mode."
            )
            return False

        # Overridable so tests can point every Web API call, including Socket
        # Mode's apps.connections.open, at a fake Slack.
        base_url = os.environ.get("SLACK_API_URL", "https://slack.com/api/")
        client = AsyncWebClient(token=self.bot_token, base_url=base_url)
        self._app = AsyncApp(client=client)

        try:
            auth = await self._app.client.auth_test()
            self._bot_user_id = auth.get("user_id")
            # The directory omits bots, so without this the agent's own handle
            # stays a raw id in the text a mention is titled from.
            self._bot_name = str(auth.get("user") or "").strip() or None
        except Exception:
            logger.exception("Slack auth_test failed for team %s", self.team_id)
            return False

        @self._app.event("message")
        async def _on_message(event, _say) -> None:  # type: ignore[no-untyped-def]
            await self._handle_event(event)

        @self._app.event("app_mention")
        async def _on_app_mention(event, _say) -> None:  # type: ignore[no-untyped-def]
            await self._handle_event(event)

        # Load names up front so even the first mention renders as a person and
        # a channel rather than a pair of ids.
        await self._load_directory()

        self._closing = False
        self._socket = AsyncSocketModeHandler(self._app, self.app_token)
        self._socket.client.auto_reconnect_enabled = self._auto_reconnect
        self._task = asyncio.create_task(self._socket.start_async())
        self._watchdog_task = asyncio.create_task(self._watchdog())
        logger.info(
            "Slack Socket Mode connected for team %s as %s",
            self.team_id,
            self._bot_user_id,
        )
        return True

    async def disconnect(self) -> None:
        self._closing = True
        for task in (self._watchdog_task, self._task):
            if task is None:
                continue
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._watchdog_task = None
        self._task = None
        if self._socket is not None:
            with contextlib.suppress(Exception):
                await self._socket.close_async()
        self._socket = None
        self._app = None

    async def set_reaction(
        self, *, channel_id: str, ts: str, add: str | None, remove: str | None = None
    ) -> None:
        """Best-effort reaction toggle used to show progress on a mention.

        Never raises: a missing ``reactions:write`` scope, or an app installed
        before that scope existed, must not stop the agent from answering.
        """
        client = getattr(self._app, "client", None)
        if client is None or not channel_id or not ts:
            return
        if remove:
            with contextlib.suppress(Exception):
                await client.reactions_remove(
                    channel=channel_id, timestamp=ts, name=remove
                )
        if add:
            try:
                await client.reactions_add(channel=channel_id, timestamp=ts, name=add)
            except Exception as exc:  # noqa: BLE001
                # already_reacted is normal on a retry and not worth a line.
                if "already_reacted" not in str(exc):
                    logger.debug("Slack reaction %s failed: %s", add, exc)

    async def _load_directory(self, *, force: bool = False) -> None:
        """Fill the id → name maps so nobody reads a ``U0123`` in the UI."""
        from agent_server.connectors.directory import fetch_directory

        try:
            people, channels = await fetch_directory(
                self.team_id, self.bot_token, force=force
            )
        except Exception as exc:  # noqa: BLE001 - names are a nicety, not critical
            logger.warning(
                "Could not load the Slack directory for %s: %s", self.team_id, exc
            )
            return
        self._user_names = {person.id: person.name for person in people}
        if self._bot_user_id and self._bot_name:
            self._user_names[self._bot_user_id] = self._bot_name
        self._user_avatars = {
            person.id: person.avatar_url for person in people if person.avatar_url
        }
        self._channel_names = {channel.id: channel.name for channel in channels}
        self._directory_loaded_at = time.monotonic()

    async def _ensure_known(self, event: dict) -> None:
        """Refresh once when a sender or channel is new since the last fetch.

        People join workspaces and channels get created after we connect, and
        falling back to a raw id is exactly the thing this avoids. Rate limited
        so an id we genuinely cannot resolve (a shared-channel guest, say) does
        not re-fetch on every message.
        """
        user_id = str(event.get("user") or "").strip()
        channel_id = str(event.get("channel") or "").strip()
        known = (not user_id or user_id in self._user_names) and (
            not channel_id or channel_id in self._channel_names
        )
        if known:
            return
        if time.monotonic() - self._directory_loaded_at < _DIRECTORY_MIN_REFRESH:
            return
        await self._load_directory(force=True)

    async def _handle_event(self, event: dict) -> None:
        if isinstance(event, dict):
            await self._ensure_known(event)
        inbound = event_to_inbound(
            event,
            team_id=self.team_id,
            bot_user_id=self._bot_user_id,
            channel_names=self._channel_names,
            user_names=self._user_names,
            user_avatars=self._user_avatars,
        )
        if inbound is None:
            return
        try:
            await self._on_message(inbound)
        except Exception:
            # A handler failure must not tear down the socket.
            logger.exception("Slack inbound handler failed for team %s", self.team_id)

    async def _watchdog(self) -> None:
        while not self._closing:
            try:
                await asyncio.sleep(self._watchdog_interval)
            except asyncio.CancelledError:
                break
            if self._closing or self._socket is None:
                break
            if await self._connected():
                continue
            logger.warning(
                "Slack Socket Mode dropped for team %s — reconnecting", self.team_id
            )
            try:
                await self._socket.client.connect_to_new_endpoint(force=True)
                self.reconnects += 1
            except Exception:
                logger.exception(
                    "Slack Socket Mode reconnect failed for team %s", self.team_id
                )
