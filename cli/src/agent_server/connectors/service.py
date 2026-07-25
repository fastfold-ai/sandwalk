"""Connector lifecycle: connect, disconnect, and supervise inbound adapters.

Owns which adapters are running for which workspaces and enforces the
one-mode-at-a-time rule — connecting a workspace over Socket Mode pauses the
cloud relay, because two inbound sources would answer the same mention twice.
"""

from __future__ import annotations

import asyncio
import logging

from agent_server.connectors.addressing import parse_target
from agent_server.connectors.directory import (
    SlackChannelEntry,
    SlackPerson,
    fetch_directory,
)
from agent_server.connectors.directory import (
    clear_cache as clear_directory_cache,
)
from agent_server.connectors.framing import frame_inbound, spawn_title
from agent_server.connectors.gateway import InboundMessage, RouteDecision, SlackGateway
from agent_server.connectors.slack_socket import SlackSocketAdapter
from agent_server.models import MessageSource
from agent_server.models.connectors import (
    SlackConnectorStatus,
    SlackParkedMessage,
    SlackWorkspace,
)
from agent_server.service import AgentService, SessionBusyError
from agent_server.store import AgentStore

logger = logging.getLogger("agent_server.connectors")

_MISSING_SDK = (
    "Slack support is not installed in this environment. "
    "Reinstall Sandwalk, or run `pip install slack-bolt`."
)

# Without these the connector cannot do its job at all: no mention events, and
# no way to answer. Checked at connect so a useless token fails loudly.
REQUIRED_SCOPES = ("app_mentions:read", "chat:write")


def _granted_scopes(auth_response: object) -> set[str]:
    """Read the granted bot scopes off an ``auth.test`` response."""
    headers = getattr(auth_response, "headers", None) or {}
    raw = ""
    for key in ("x-oauth-scopes", "X-OAuth-Scopes"):
        value = headers.get(key) if hasattr(headers, "get") else None
        if value:
            raw = value if isinstance(value, str) else ",".join(value)
            break
    return {scope.strip() for scope in raw.split(",") if scope.strip()}


def slack_sdk_available() -> bool:
    from importlib.util import find_spec

    return find_spec("slack_bolt") is not None


def _require_slack_sdk() -> None:
    if not slack_sdk_available():
        raise ValueError(_MISSING_SDK)


class ConnectorService:
    def __init__(self, store: AgentStore, agent_service: AgentService | None = None) -> None:
        self.store = store
        self.agent_service = agent_service
        self.gateway = SlackGateway(store)
        self._sockets: dict[str, SlackSocketAdapter] = {}
        self._relay_state: str = "off"
        self._relay_detail: str | None = None
        self._started = False
        self._lock = asyncio.Lock()

    # --- lifecycle ------------------------------------------------------

    async def start(self) -> None:
        """Bring up adapters for every enabled workspace. Never raises."""
        if self._started:
            return
        self._started = True
        for workspace in self.store.list_slack_workspaces():
            if not workspace.enabled:
                continue
            try:
                await self._start_workspace(workspace)
            except Exception:
                logger.exception(
                    "Failed to start Slack workspace %s", workspace.team_id
                )

    async def stop(self) -> None:
        self._started = False
        async with self._lock:
            adapters = list(self._sockets.values())
            self._sockets.clear()
        for adapter in adapters:
            try:
                await adapter.disconnect()
            except Exception:
                logger.exception("Failed to stop a Slack socket adapter")
        self._relay_state = "off"
        self._relay_detail = None

    # --- connect / disconnect -------------------------------------------

    async def connect_socket_mode(
        self, *, bot_token: str, app_token: str, team_id: str | None = None
    ) -> SlackWorkspace:
        """Connect one workspace over Socket Mode using pasted tokens."""
        bot = str(bot_token or "").strip()
        app = str(app_token or "").strip()
        if not bot or not app:
            raise ValueError("Both a bot token and an app token are required.")
        if not app.startswith("xapp-"):
            # Socket Mode silently never connects without the app-level token, and
            # Slack surfaces no error, so catch the common paste mistake up front.
            raise ValueError(
                "The app token should start with 'xapp-'. Generate one under "
                "Basic Information → App-Level Tokens with the connections:write scope."
            )

        _require_slack_sdk()

        resolved_team = str(team_id or "").strip()
        if not resolved_team:
            resolved_team = await self._resolve_team_id(bot)

        workspace = self.store.upsert_slack_workspace(
            team_id=resolved_team,
            mode="socket",
            bot_token=bot,
            app_token=app,
        )
        await self._start_workspace(workspace)
        return self.store.get_slack_workspace(resolved_team) or workspace

    async def disconnect_workspace(self, team_id: str) -> bool:
        await self._stop_workspace(team_id)
        clear_directory_cache(team_id)
        return self.store.delete_slack_workspace(team_id)

    async def directory(
        self, team_id: str, *, force: bool = False
    ) -> tuple[list[SlackPerson], list[SlackChannelEntry]]:
        """People and channels for the pickers, so nobody types raw ids."""
        if self.store.get_slack_workspace(team_id) is None:
            raise KeyError(team_id)
        if not slack_sdk_available():
            return [], []
        bot_token, _ = self.store.get_slack_tokens(team_id)
        if not bot_token:
            return [], []
        return await fetch_directory(team_id, bot_token, force=force)

    async def _resolve_team_id(self, bot_token: str) -> str:
        """Ask Slack which workspace a bot token belongs to."""
        try:
            from slack_sdk.web.async_client import AsyncWebClient
        except ImportError as exc:
            raise ValueError(_MISSING_SDK) from exc

        import os

        client = AsyncWebClient(
            token=bot_token,
            base_url=os.environ.get("SLACK_API_URL", "https://slack.com/api/"),
        )
        try:
            auth = await client.auth_test()
        except Exception as exc:
            raise ValueError(f"Slack rejected the bot token: {exc}") from exc
        team = str(auth.get("team_id") or "").strip()
        if not team:
            raise ValueError("Slack did not return a workspace for this token.")

        # A token can authenticate fine and still be useless: without
        # app_mentions:read no mention ever arrives, and the workspace would sit
        # there looking connected while doing nothing.
        granted = _granted_scopes(auth)
        missing = [scope for scope in REQUIRED_SCOPES if scope not in granted]
        if missing:
            raise ValueError(
                "This Slack app is missing required scopes: "
                f"{', '.join(missing)}. Open the app at api.slack.com/apps → "
                "App Manifest, paste the manifest from the Manual tab, then "
                "reinstall and copy the new bot token."
            )
        # Record the identity we just learned so the allowlist and echo guard work.
        self.store.upsert_slack_workspace(
            team_id=team,
            mode="socket",
            team_name=str(auth.get("team") or "").strip() or None,
            bot_user_id=str(auth.get("user_id") or "").strip() or None,
        )
        return team

    # --- adapter supervision --------------------------------------------

    async def _start_workspace(self, workspace: SlackWorkspace) -> None:
        if workspace.mode != "socket":
            # Relay-backed workspaces are driven by the shared relay client,
            # which lands in a later phase.
            return
        if not slack_sdk_available():
            self._relay_detail = _MISSING_SDK
            logger.warning("%s (workspace %s)", _MISSING_SDK, workspace.team_id)
            return
        bot_token, app_token = self.store.get_slack_tokens(workspace.team_id)
        if not bot_token or not app_token:
            logger.warning(
                "Slack workspace %s is in socket mode but has no tokens",
                workspace.team_id,
            )
            return

        await self._stop_workspace(workspace.team_id)
        adapter = SlackSocketAdapter(
            team_id=workspace.team_id,
            bot_token=bot_token,
            app_token=app_token,
            on_message=self._on_inbound,
        )
        connected = await adapter.connect()
        if not connected:
            return
        if adapter.bot_user_id:
            self.store.upsert_slack_workspace(
                team_id=workspace.team_id,
                mode="socket",
                bot_user_id=adapter.bot_user_id,
            )
        async with self._lock:
            self._sockets[workspace.team_id] = adapter

    async def _stop_workspace(self, team_id: str) -> None:
        async with self._lock:
            adapter = self._sockets.pop(team_id, None)
        if adapter is not None:
            try:
                await adapter.disconnect()
            except Exception:
                logger.exception("Failed to stop Slack socket for %s", team_id)

    # --- inbound --------------------------------------------------------

    async def _on_inbound(self, message: InboundMessage) -> None:
        decision = self.gateway.route(message)
        if decision.action == "ignore":
            logger.debug(
                "Slack inbound ignored (%s) for %s", decision.reason, message.channel
            )
            return
        if decision.action == "park":
            self.store.park_slack_message(
                team_id=message.team_id,
                channel=message.channel,
                slack_user_id=message.user_id,
                text=message.text,
                thread_target=decision.thread_target,
                user_name=message.user_name,
            )
            logger.info(
                "Parked Slack message from %s in %s (sender not allowed)",
                message.user_id,
                message.channel,
            )
            return
        if decision.action == "spawn":
            self._spawn_session(message, decision)
            return
        for session_id in decision.session_ids:
            self._deliver(session_id, message, first_message=False)

    async def allow_parked(self, message_id: str) -> bool:
        """Allow the sender, then actually deliver the message they sent.

        Clearing the queue without answering would leave the person in Slack
        waiting on a reply that never comes.
        """
        parked = next(
            (
                item
                for item in self.store.list_slack_parked_messages()
                if item.id == message_id
            ),
            None,
        )
        if parked is None:
            return False

        self.store.allow_slack_user(
            team_id=parked.team_id,
            slack_user_id=parked.slack_user_id,
            display_name=parked.user_name,
        )
        self.store.delete_slack_parked_message(message_id)

        replay = self._inbound_from_parked(parked)
        if replay is not None:
            await self._on_inbound(replay)
        return True

    @staticmethod
    def _inbound_from_parked(parked: SlackParkedMessage) -> InboundMessage | None:
        """Rebuild the original message so it can run through routing again."""
        try:
            channel = parse_target(parked.channel)
            thread = (
                parse_target(parked.thread_target) if parked.thread_target else None
            )
        except ValueError:
            logger.warning("Parked message %s has an unreadable target", parked.id)
            return None
        ts = (thread.thread_ts if thread else None) or ""
        if not ts:
            return None
        return InboundMessage(
            team_id=channel.team_id,
            channel_id=channel.channel_id,
            user_id=parked.slack_user_id,
            user_name=parked.user_name,
            text=parked.text,
            ts=ts,
            mentions_me=True,
        )

    def _spawn_session(
        self, message: InboundMessage, decision: RouteDecision
    ) -> str | None:
        if self.agent_service is None:
            logger.warning("No agent service wired — dropping Slack mention")
            return None
        label = self.gateway.source_label(message)
        try:
            session = self.agent_service.create_session(
                title=spawn_title(message, channel_label=label),
                workspace_path=None,
                source="slack",
                source_label=label,
            )
        except Exception:
            logger.exception("Failed to create a session for a Slack mention")
            return None

        # Recording the thread mapping before the run starts is what makes the
        # reply target trusted: `slack.send_message` checks this mapping instead
        # of prompting for approval on every message in a thread the user began.
        self.store.set_slack_mention_session(
            thread_target=message.thread_target,
            session_id=session.id,
            channel=message.channel,
        )
        self._deliver(session.id, message, first_message=True)
        return session.id

    def _deliver(
        self, session_id: str, message: InboundMessage, *, first_message: bool
    ) -> None:
        if self.agent_service is None:
            logger.warning("No agent service wired — dropping Slack message")
            return
        label = self.gateway.source_label(message)
        content = frame_inbound(
            message, channel_label=label, first_message=first_message
        )
        # The model reads the framed content; the UI renders a card from this.
        source = MessageSource(
            connector="slack",
            channel_id=message.channel_id,
            channel_name=message.channel_name,
            sender_id=message.user_id,
            sender_name=message.user_name,
            text=message.text,
        )
        try:
            self.agent_service.submit_message(
                session_id=session_id, content=content, source=source
            )
        except SessionBusyError:
            # The agent is still working on this thread. Dropping is better than
            # queueing: by the time it finishes, the earlier question is usually
            # already covered by the answer in flight.
            logger.info(
                "Slack message skipped — session %s is still running", session_id
            )
        except KeyError:
            logger.warning("Slack message for missing session %s", session_id)
        except Exception:
            logger.exception("Failed to submit a Slack message to %s", session_id)

    # --- status ---------------------------------------------------------

    def status(self) -> SlackConnectorStatus:
        workspaces = self.store.list_slack_workspaces()
        mode = None
        if any(item.mode == "socket" for item in workspaces):
            mode = "socket"
        elif any(item.mode == "relay" for item in workspaces):
            mode = "relay"
        return SlackConnectorStatus(
            mode=mode,  # type: ignore[arg-type]
            relay_state=self._relay_state,  # type: ignore[arg-type]
            relay_detail=self._relay_detail,
            workspaces=workspaces,
        )

    def socket_connected(self, team_id: str) -> bool:
        adapter = self._sockets.get(team_id)
        return bool(adapter and adapter.connected)
