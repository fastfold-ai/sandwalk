"""Slack Socket Mode adapter (manual connect path).

Slack opens the connection to us, so this works from a laptop with no public URL
and no FastFold account. ``slack-bolt`` is imported lazily inside :meth:`connect`
so the module stays importable without the optional extra installed.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import Awaitable, Callable

from agent_server.connectors.gateway import InboundMessage
from agent_server.connectors.slack_events import event_to_inbound

logger = logging.getLogger("agent_server.connectors.slack")

InboundHandler = Callable[[InboundMessage], Awaitable[None]]

# slack_sdk keeps the socket alive in background tasks and usually reconnects on
# its own, but it can give up after a transient error during Slack's periodic
# connection cycling and leave a dead socket that never recovers. Poll for that.
_WATCHDOG_INTERVAL = 20.0


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
        self.reconnects = 0
        self._user_names: dict[str, str] = {}
        self._channel_names: dict[str, str] = {}

    @property
    def bot_user_id(self) -> str | None:
        return self._bot_user_id

    @property
    def connected(self) -> bool:
        client = getattr(self._socket, "client", None)
        if client is None:
            return False
        try:
            return bool(client.is_connected())
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
        except Exception:
            logger.exception("Slack auth_test failed for team %s", self.team_id)
            return False

        @self._app.event("message")
        async def _on_message(event, _say) -> None:  # type: ignore[no-untyped-def]
            await self._handle_event(event)

        @self._app.event("app_mention")
        async def _on_app_mention(event, _say) -> None:  # type: ignore[no-untyped-def]
            await self._handle_event(event)

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

    async def _handle_event(self, event: dict) -> None:
        inbound = event_to_inbound(
            event,
            team_id=self.team_id,
            bot_user_id=self._bot_user_id,
            channel_names=self._channel_names,
            user_names=self._user_names,
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
            if self.connected:
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
