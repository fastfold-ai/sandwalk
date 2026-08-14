"""Connector lifecycle: connect, disconnect, and supervise inbound adapters.

Owns which adapters are running for which workspaces and enforces the
one-mode-at-a-time rule — connecting a workspace over Socket Mode pauses the
cloud relay, because two inbound sources would answer the same mention twice.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from typing import Any
from urllib.parse import urlparse

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
from agent_server.connectors.slack_commands import SlashCommandRequest
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

# Progress feedback on the mention itself, rather than a message in the channel.
WORKING_REACTION = "eyes"
DONE_REACTION = "white_check_mark"
FAILED_REACTION = "warning"

# Where FastFold Cloud's OAuth callback sends the browser back to once the
# token exchange is done. Served by this same process (see
# agent_server.routes.slack_oauth_return), so it works with whatever host/port
# `sandwalk serve` was actually started with rather than assuming 8787.
LOCAL_OAUTH_CALLBACK_PATH = "/oauth/callback"
_WILDCARD_BIND_HOSTS = {"0.0.0.0", "::", "[::]"}


def local_oauth_return_url() -> str:
    host = os.environ.get("FASTFOLD_SERVE_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if host in _WILDCARD_BIND_HOSTS:
        host = "127.0.0.1"
    port = os.environ.get("FASTFOLD_SERVE_PORT", "8787").strip() or "8787"
    return f"http://{host}:{port}{LOCAL_OAUTH_CALLBACK_PATH}"


def oauth_callback_return_to(*, origin: str | None = None, base_url: str | None = None) -> str:
    """Browser callback URL from the host the user actually opened.

    ``sandwalk serve --host 0.0.0.0`` (Allow Remote) must not send 0.0.0.0 to
    FastFold Cloud — that bind address is not a valid OAuth return_to host.
    """
    for candidate in (origin, base_url):
        parsed = urlparse((candidate or "").strip())
        host = (parsed.hostname or "").strip().lower()
        if parsed.scheme not in {"http", "https"} or not host:
            continue
        if host in _WILDCARD_BIND_HOSTS:
            continue
        return f"{parsed.scheme}://{parsed.netloc}{LOCAL_OAUTH_CALLBACK_PATH}"
    return local_oauth_return_url()


def _cloud_request(
    method: str, url: str, api_key: str, body: dict | None
) -> tuple[dict | None, str | None]:
    """Blocking JSON call to FastFold Cloud, returning ``(payload, error)``.

    Errors come back as readable text rather than exceptions so the UI can show
    the reason instead of a status code.
    """
    import json
    import urllib.error
    import urllib.request

    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {api_key}")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"{}"), None
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return None, "FastFold rejected the API key. Reconnect FastFold Cloud."
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        return None, f"FastFold returned {exc.code}: {detail}"
    except Exception as exc:  # noqa: BLE001
        return None, f"Could not reach FastFold Cloud: {exc}"


_BUSY_STATUSES = {"running", "queued", "starting"}
_POLL_SECONDS = 1.0
# How long to allow for a run to show up as busy before deciding it is already
# done — a fast answer can settle before the first poll.
_START_GRACE_SECONDS = 5.0

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
        # Holds socket adapters and relay workspaces alike; both present the
        # same surface, so callers need not know which mode a team uses.
        self._sockets: dict[str, Any] = {}
        self._relay: Any = None
        self._progress_tasks: set[asyncio.Task] = set()
        self._relay_state: str = "off"
        self._relay_detail: str | None = None
        # Cached once per process — resolving it hits FastFold Cloud, and the
        # signed-in account does not change while sandwalk is running.
        self._account_email: str | None = None
        self._account_user_id: str | None = None
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
                logger.exception("Failed to start Slack workspace %s", workspace.team_id)

    async def stop(self) -> None:
        self._started = False
        for task in list(self._progress_tasks):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._progress_tasks.clear()
        async with self._lock:
            adapters = list(self._sockets.values())
            self._sockets.clear()
            relay = self._relay
            self._relay = None
        if relay is not None:
            with contextlib.suppress(Exception):
                await relay.stop()
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

    async def set_workspace_enabled(self, team_id: str, *, enabled: bool) -> SlackWorkspace:
        """Pause or resume a workspace without disconnecting it.

        Keeps tokens and settings (people, channels) intact - unlike
        disconnect, this is meant to be reversible. Independent per workspace,
        so pausing "Fastfold Community" (socket) has no effect on "Fastfold"
        (relay) even though both are Slack under the hood.
        """
        workspace = self.store.set_slack_workspace_flags(team_id, enabled=enabled)
        if workspace is None:
            raise KeyError(team_id)
        if enabled:
            await self._start_workspace(workspace)
        else:
            await self._stop_workspace(team_id)
        return self.store.get_slack_workspace(team_id) or workspace

    # --- one-click (relay) ------------------------------------------------

    async def start_one_click(self, *, return_to: str | None = None) -> str:
        """Ask FastFold Cloud for a Slack install URL.

        Raises ValueError carrying something worth showing, because the common
        failure - not signed in to FastFold Cloud - is the user's to fix and a
        bare HTTP error would not say so.
        """
        from agent_server.account_service.helpers import api_key, cloud_base_url

        key = api_key()
        if not key:
            raise ValueError(
                "Connect Fastfold Cloud first — one-click Slack needs an API key "
                "so the relay knows which desktop to deliver to."
            )

        # Land the browser back on this machine rather than a cloud page: the
        # desktop is already polling for the result, so a generic cloud
        # "loading" screen would be a dead end for a flow that has nothing
        # left for the user to do.
        body: dict[str, Any] = {
            "app": "sandwalk",
            "return_to": return_to or local_oauth_return_url(),
        }
        payload, error = await asyncio.to_thread(
            _cloud_request, "POST", f"{cloud_base_url()}/v1/slack/oauth/start", key, body
        )
        if error:
            raise ValueError(error)
        url = str((payload or {}).get("auth_url") or "").strip()
        if not url:
            raise ValueError("FastFold did not return a Slack install URL.")
        return url

    async def import_one_click_connections(
        self, *, reauth_team_id: str | None = None
    ) -> list[SlackWorkspace]:
        """Adopt installs that were completed in the browser.

        The desktop never sees the OAuth callback, so after sending the user to
        Slack it polls the cloud for installs it has no token for, collects
        each one, and starts relaying. Holding the token locally is what keeps
        the outbound path identical to Socket Mode.

        ``reauth_team_id`` is the one exception to "skip if we already have a
        token": that is exactly the reconnect flow (a reinstall rotated the
        Slack-side token, ours is now stale), so for that one team the fresh
        token overwrites the old one instead of being skipped.
        """
        from agent_server.account_service.helpers import api_key, cloud_base_url

        key = api_key()
        if not key:
            raise ValueError("Connect Fastfold Cloud first.")

        base = cloud_base_url()
        listing, error = await asyncio.to_thread(
            _cloud_request, "GET", f"{base}/v1/slack/connections", key, None
        )
        if error:
            raise ValueError(error)

        imported: list[SlackWorkspace] = []
        for item in (listing or {}).get("data") or []:
            team_id = str(item.get("team_id") or "").strip()
            connection_id = str(item.get("id") or "").strip()
            if not team_id or not connection_id:
                continue
            is_reauth_target = reauth_team_id is not None and team_id == reauth_team_id
            existing_token, _ = self.store.get_slack_tokens(team_id)
            if existing_token and not is_reauth_target:
                continue

            token_payload, token_error = await asyncio.to_thread(
                _cloud_request,
                "GET",
                f"{base}/v1/slack/connections/{connection_id}",
                key,
                None,
            )
            if token_error or not token_payload:
                logger.warning("Could not fetch the Slack token for %s: %s", team_id, token_error)
                continue

            workspace = self.store.upsert_slack_workspace(
                team_id=team_id,
                mode="relay",
                team_name=str(item.get("team_name") or "") or None,
                bot_token=str(token_payload.get("bot_token") or ""),
                bot_user_id=(
                    str(token_payload.get("bot_user_id") or "")
                    or str(item.get("bot_user_id") or "")
                    or None
                ),
                connection_id=connection_id,
            )
            await self._start_workspace(workspace)
            imported.append(workspace)
        return imported

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
        if workspace.mode == "relay":
            await self._start_relay_workspace(workspace)
            return
        if workspace.mode != "socket":
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

    async def _start_relay_workspace(self, workspace: SlackWorkspace) -> None:
        """Attach a one-click workspace to the shared relay socket.

        One socket serves every relay workspace, so the first one starts it and
        the rest just register. The bot token is still local - handed over
        after OAuth - so outbound and the directory work as they do in Socket
        Mode, and only inbound comes down the wire.

        Switching an existing Socket Mode workspace to relay (the one-click
        flow lands here for a team already connected the manual way) has to
        tear down that socket first - otherwise both stay live and every
        mention gets answered twice.
        """
        from agent_server.account_service.helpers import api_key, cloud_base_url
        from agent_server.connectors.slack_relay import (
            SlackRelayClient,
            SlackRelayWorkspace,
        )

        await self._stop_workspace(workspace.team_id)

        key = api_key()
        if not key:
            # Distinct from "off": the workspace is connected, but nothing can
            # be delivered until the user signs in to FastFold Cloud.
            self._relay_state = "signed_out"
            self._relay_detail = "Connect Fastfold Cloud to receive Slack messages."
            logger.warning(
                "Slack workspace %s needs a FastFold API key to relay", workspace.team_id
            )
            return

        if self._account_email is None and self._account_user_id is None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(self._resolve_account_identity, key)

        bot_token, _ = self.store.get_slack_tokens(workspace.team_id)
        if not bot_token:
            logger.warning(
                "Slack workspace %s is in relay mode but has no bot token",
                workspace.team_id,
            )
            return

        async with self._lock:
            if self._relay is None:
                self._relay = SlackRelayClient(
                    base_url=cloud_base_url(),
                    api_key=key,
                    on_message=self._on_inbound,
                    on_state=self._set_relay_state,
                    on_slash_command=self.handle_slash_command,
                )
            relay = self._relay

        adapter = SlackRelayWorkspace(
            team_id=workspace.team_id,
            bot_token=bot_token,
            bot_user_id=workspace.bot_user_id,
        )
        # Drives the assistant container's suggested prompts.
        with contextlib.suppress(Exception):
            adapter.specialist_names = [
                specialist.name for specialist in self.store.list_specialists()
            ]
        adapter.home_sessions = self._recent_slack_home_sessions
        adapter.home_status = lambda team_id=workspace.team_id: self._slack_home_status(team_id)
        adapter.on_token_invalid = lambda detail, team_id=workspace.team_id: (
            self._mark_slack_token_invalid(team_id, detail)
        )
        await adapter.load_directory()
        relay.add_workspace(adapter)
        async with self._lock:
            # Registered in the same map as socket adapters so progress
            # reactions and status find it without caring which mode it is.
            self._sockets[workspace.team_id] = adapter
        already_live = relay.connected
        await relay.start()
        if already_live:
            # The relay was already up (e.g. a second workspace connecting) —
            # `_set_relay_state` won't fire again, so publish now while the
            # status is accurate. A cold start publishes from there instead,
            # once the socket actually reports live rather than racing it.
            self._republish_home(workspace.team_id)

    def _resolve_account_identity(self, key: str) -> None:
        from agent_server.account_service import _resolve_user
        from agent_server.account_service.helpers import cloud_base_url

        _user_id, email, _username = _resolve_user(key, cloud_base_url())
        user_id = _user_id
        self._account_email = email
        self._account_user_id = user_id

    def _set_relay_state(self, state: str, detail: str | None) -> None:
        self._relay_state = state
        self._relay_detail = detail
        if state == "live":
            # Recent Threads was correct all along — only the status line was
            # stale (published before the socket actually reported live).
            for team_id in list(self._sockets):
                self._republish_home(team_id)

    def _recent_slack_home_sessions(self) -> list:
        """Slack-originated sessions for the App Home Recent threads list."""
        from agent_server.connectors.slack_home import RECENT_LIMIT, HomeSessionRow

        rows: list[HomeSessionRow] = []
        for session in self.store.list_sessions():
            if session.source != "slack":
                continue
            rows.append(
                HomeSessionRow(
                    id=session.id,
                    title=session.title,
                    source_label=session.source_label,
                    updated_at=session.updated_at,
                )
            )
            if len(rows) >= RECENT_LIMIT:
                break
        return rows

    def _mark_slack_token_invalid(self, team_id: str, detail: str) -> None:
        """An outbound Slack call reported the bot token itself is dead.

        Distinct from relay connectivity (``_relay_state``): the socket can be
        perfectly live while the bot token is stale, e.g. after a reinstall
        rotates it - this is what turns that into a visible "reconnect" prompt
        instead of a silently failing reply.
        """
        logger.warning("Slack bot token for %s needs reconnecting: %s", team_id, detail)
        with contextlib.suppress(Exception):
            self.store.set_slack_workspace_reauth(team_id, needs_reauth=True)

    def _slack_home_status(self, team_id: str):
        """Relay/account state for the App Home Integration status section."""
        from agent_server.connectors.slack_home import HomeStatus

        status = self.status()
        workspace = self.store.get_slack_workspace(team_id)
        return HomeStatus(
            relay_state=status.relay_state,
            relay_detail=status.relay_detail,
            team_name=workspace.team_name if workspace else None,
            account_email=self._account_email,
            account_user_id=self._account_user_id,
        )

    # --- slash commands ---------------------------------------------------

    async def handle_slash_command(self, request: SlashCommandRequest) -> None:
        """Dispatch a relayed ``/sandwalk`` subcommand and post the answer.

        Runs entirely outside Slack's request/response cycle — the cloud
        already sent the "Working on it..." ack; this posts the real answer to
        ``response_url`` whenever it's ready. ``help`` never reaches here (the
        cloud answers it directly), so every subcommand here needs the
        invoking Slack user to already be on the allowlist — the same trust
        boundary an unapproved mention already runs into.
        """
        from agent_server.connectors import slack_commands

        if not self.store.is_slack_user_allowed(
            team_id=request.team_id, slack_user_id=request.user_id
        ):
            text = slack_commands.render_unauthorized()
        else:
            try:
                text = self._render_slash_command(request)
            except Exception:
                logger.exception("Slack slash command %s failed", request.verb)
                text = slack_commands.render_error()

        await asyncio.to_thread(slack_commands.post_response, request.response_url, text)

    def _render_slash_command(self, request: SlashCommandRequest) -> str:
        from agent_server.connectors import slack_commands

        if request.verb == "status":
            return slack_commands.render_status(self._slack_home_status(request.team_id))
        if request.verb == "sessions":
            return slack_commands.render_sessions(self._recent_slack_home_sessions())
        if request.verb == "people":
            return self._render_people_command(request)
        if request.verb == "parked":
            return slack_commands.render_parked(self.store.list_slack_parked_messages())
        return slack_commands.render_unknown(request.verb or "(none)")

    def _render_people_command(self, request: SlashCommandRequest) -> str:
        from agent_server.connectors import slack_commands

        sub = request.rest[0].lower() if request.rest else "list"
        if sub == "list":
            return slack_commands.render_people(
                self.store.list_slack_allowed_users(request.team_id)
            )
        if sub == "allow":
            target_id = slack_commands.first_mentioned_user_id(" ".join(request.rest[1:]))
            if not target_id:
                return slack_commands.render_allow_usage()
            self.store.allow_slack_user(team_id=request.team_id, slack_user_id=target_id)
            return slack_commands.render_allowed(target_id)
        return slack_commands.render_people_usage()

    async def _stop_workspace(self, team_id: str) -> None:
        async with self._lock:
            adapter = self._sockets.pop(team_id, None)
            relay = self._relay
        if relay is not None:
            relay.remove_workspace(team_id)
            if not relay.teams:
                await relay.stop()
                async with self._lock:
                    self._relay = None
        if adapter is not None:
            try:
                await adapter.disconnect()
            except Exception:
                logger.exception("Failed to stop Slack socket for %s", team_id)

    # --- inbound --------------------------------------------------------

    async def _on_inbound(self, message: InboundMessage) -> None:
        decision = self.gateway.route(message)
        if decision.action == "ignore":
            logger.debug("Slack inbound ignored (%s) for %s", decision.reason, message.channel)
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
            session_id = self._spawn_session(message, decision)
            if session_id:
                self._track_progress(message, [session_id])
            return
        for session_id in decision.session_ids:
            self._deliver(session_id, message, first_message=False)
        if decision.session_ids:
            self._track_progress(message, list(decision.session_ids))

    def _track_progress(self, message: InboundMessage, session_ids: list[str]) -> None:
        """Mark the Slack message as being worked on, and clear it when done.

        Answers can take a minute, and without this the person who asked has no
        signal that anything is happening. A reaction is the least intrusive
        option: it needs no extra message in the channel, and it degrades
        quietly on a workspace whose app predates the reactions scope.
        """
        task = asyncio.create_task(self._run_progress(message, session_ids))
        # Hold a reference; asyncio only keeps weak ones and will cancel a task
        # that gets collected mid-run.
        self._progress_tasks.add(task)
        task.add_done_callback(self._progress_tasks.discard)

    async def _run_progress(self, message: InboundMessage, session_ids: list[str]) -> None:
        adapter = self._sockets.get(message.team_id)
        if adapter is None:
            return

        # Inside an assistant thread Slack renders a native "is thinking"
        # indicator, which is tidier than decorating the message. It only
        # applies there, so channel mentions keep the reaction.
        assistant = getattr(adapter, "assistant", None) if message.thread_ts else None
        used_status = False
        if assistant is not None:
            from agent_server.connectors.slack_assistant import THINKING_STATUS

            used_status = await assistant.set_status(
                channel_id=message.channel_id,
                thread_ts=message.thread_ts or "",
                status=THINKING_STATUS,
            )
        if not used_status:
            await adapter.set_reaction(
                channel_id=message.channel_id, ts=message.ts, add=WORKING_REACTION
            )

        results = [await self._wait_for_idle(session_id) for session_id in session_ids]

        if used_status and assistant is not None:
            # Slack clears this itself once the app replies; doing it here too
            # covers a run that ended without one.
            await assistant.clear_status(
                channel_id=message.channel_id, thread_ts=message.thread_ts or ""
            )
            return
        await adapter.set_reaction(
            channel_id=message.channel_id,
            ts=message.ts,
            remove=WORKING_REACTION,
            add=DONE_REACTION if all(results) else FAILED_REACTION,
        )

    async def _wait_for_idle(self, session_id: str, timeout: float = 900.0) -> bool:
        """Poll until the run settles. True when it finished without erroring.

        Session events are only exposed as an SSE feed over the store, so there
        is nothing in-process to await. A short run can finish before the first
        poll, hence the grace window before concluding it never started.
        """
        deadline = time.monotonic() + timeout
        grace = time.monotonic() + _START_GRACE_SECONDS
        started = False
        while time.monotonic() < deadline:
            session = await asyncio.to_thread(self.store.get_session, session_id)
            if session is None:
                return False
            status = (session.status or "").strip().lower()
            if status in _BUSY_STATUSES:
                started = True
            elif started or time.monotonic() > grace:
                return status != "error"
            await asyncio.sleep(_POLL_SECONDS)
        return False

    async def allow_parked(self, message_id: str) -> bool:
        """Allow the sender, then actually deliver the message they sent.

        Clearing the queue without answering would leave the person in Slack
        waiting on a reply that never comes.
        """
        parked = next(
            (item for item in self.store.list_slack_parked_messages() if item.id == message_id),
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
            thread = parse_target(parked.thread_target) if parked.thread_target else None
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

    def _spawn_session(self, message: InboundMessage, decision: RouteDecision) -> str | None:
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
        # Recent threads just changed — refresh Home for whoever can see it.
        # Fire-and-forget: a slow/failed publish must not delay the reply.
        self._republish_home(message.team_id)
        return session.id

    def _republish_home(self, team_id: str) -> None:
        adapter = self._sockets.get(team_id)
        publish = getattr(adapter, "publish_home_for_users", None)
        if not callable(publish):
            # Socket Mode workspaces have no App Home surface yet.
            return
        allowed = [person.slack_user_id for person in self.store.list_slack_allowed_users(team_id)]
        if not allowed:
            return
        task = asyncio.create_task(publish(allowed))
        self._progress_tasks.add(task)
        task.add_done_callback(self._progress_tasks.discard)

    def _dm_channel_name(self, message: InboundMessage) -> str | None:
        """Bot @handle for DM cards — resolved from the live adapter's auth."""
        adapter = self._sockets.get(message.team_id)
        if adapter is None:
            return None
        bot_name = getattr(adapter, "_bot_name", None)
        if isinstance(bot_name, str) and bot_name.strip():
            return bot_name.strip()
        bot_id = getattr(adapter, "bot_user_id", None)
        names = getattr(adapter, "user_names", None) or getattr(adapter, "_user_names", None)
        if bot_id and isinstance(names, dict):
            resolved = names.get(bot_id)
            if isinstance(resolved, str) and resolved.strip():
                return resolved.strip()
        return None

    def _deliver(self, session_id: str, message: InboundMessage, *, first_message: bool) -> None:
        if self.agent_service is None:
            logger.warning("No agent service wired — dropping Slack message")
            return
        label = self.gateway.source_label(message)
        content = frame_inbound(message, channel_label=label, first_message=first_message)
        # The model reads the framed content; the UI renders a card from this.
        # DMs have no channel name in Slack's directory — use the bot handle so
        # the card can show "@sandwalk" instead of a raw D… id.
        channel_name = message.channel_name
        if message.is_direct_message:
            channel_name = self._dm_channel_name(message) or channel_name
        source = MessageSource(
            connector="slack",
            channel_id=message.channel_id,
            channel_name=channel_name,
            sender_id=message.user_id,
            sender_name=message.user_name,
            sender_avatar_url=message.user_avatar_url,
            text=message.text,
        )
        try:
            self.agent_service.submit_message(session_id=session_id, content=content, source=source)
        except SessionBusyError:
            # The agent is still working on this thread. Dropping is better than
            # queueing: by the time it finishes, the earlier question is usually
            # already covered by the answer in flight.
            logger.info("Slack message skipped — session %s is still running", session_id)
        except KeyError:
            logger.warning("Slack message for missing session %s", session_id)
        except Exception:
            logger.exception("Failed to submit a Slack message to %s", session_id)

    # --- status ---------------------------------------------------------

    async def reconcile_fastfold_auth(self) -> None:
        """Start or stop the shared relay when the FastFold Cloud key changes.

        Relay inbound requires ``FASTFOLD_API_KEY`` / ``api.fastfold_cloud_key``.
        Removing the key used to leave a live socket and a green UI until restart;
        this tears it down (or brings it back) immediately.
        """
        from agent_server.account_service.helpers import api_key

        key = api_key()
        relay_workspaces = [
            workspace
            for workspace in self.store.list_slack_workspaces()
            if workspace.mode == "relay" and workspace.enabled
        ]
        if not relay_workspaces:
            return

        if not key:
            await self._stop_relay_for_missing_key()
            return

        # Key is present again — restart any relay workspace that is not live.
        for workspace in relay_workspaces:
            if self.socket_connected(workspace.team_id) and self._relay_state == "live":
                continue
            try:
                await self._start_relay_workspace(workspace)
            except Exception:
                logger.exception(
                    "Failed to restart Slack relay workspace %s after FastFold key change",
                    workspace.team_id,
                )

    async def _stop_relay_for_missing_key(self) -> None:
        relay_ids = {
            workspace.team_id
            for workspace in self.store.list_slack_workspaces()
            if workspace.mode == "relay"
        }
        async with self._lock:
            relay = self._relay
            self._relay = None
            for team_id in list(self._sockets):
                if team_id in relay_ids:
                    self._sockets.pop(team_id, None)
        if relay is not None:
            with contextlib.suppress(Exception):
                await relay.stop()
        self._relay_state = "signed_out"
        self._relay_detail = "Connect Fastfold Cloud to receive Slack messages."
        logger.info("Stopped Slack relay — FastFold API key is not configured")

    def status(self) -> SlackConnectorStatus:
        from agent_server.account_service.helpers import api_key

        workspaces = self.store.list_slack_workspaces()
        mode = None
        if any(item.mode == "socket" for item in workspaces):
            mode = "socket"
        elif any(item.mode == "relay" for item in workspaces):
            mode = "relay"
        # Relay inbound needs a FastFold key. Even if a socket is still up after
        # the key was cleared, report signed_out / not live so the UI matches.
        key = api_key()
        has_enabled_relay = any(
            item.mode == "relay" and item.enabled for item in workspaces
        )
        relay_state = self._relay_state
        relay_detail = self._relay_detail
        if has_enabled_relay and not key:
            relay_state = "signed_out"
            relay_detail = "Connect Fastfold Cloud to receive Slack messages."
        # A paused workspace is never live regardless of what its (possibly
        # stale) adapter thinks; socket_connected covers both socket and relay
        # adapters since SlackRelayWorkspace exposes the same `.connected`.
        live_workspaces = [
            workspace.model_copy(
                update={
                    "live": workspace.enabled
                    and self.socket_connected(workspace.team_id)
                    and not (workspace.mode == "relay" and not key)
                }
            )
            for workspace in workspaces
        ]
        return SlackConnectorStatus(
            mode=mode,  # type: ignore[arg-type]
            relay_state=relay_state,  # type: ignore[arg-type]
            relay_detail=relay_detail,
            workspaces=live_workspaces,
        )

    def socket_connected(self, team_id: str) -> bool:
        adapter = self._sockets.get(team_id)
        return bool(adapter and adapter.connected)
