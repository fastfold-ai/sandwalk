"""Routing policy for inbound Slack messages.

Both event sources — Socket Mode and the cloud relay — hand messages to the same
gateway, so the rules about who may trigger the agent and which session answers
live in exactly one place.

:meth:`SlackGateway.route` only reads state and returns a decision, which keeps
the policy testable without a Slack connection. Acting on the decision is the
caller's job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from agent_server.connectors.addressing import format_channel, format_target
from agent_server.store import AgentStore

CONNECTOR = "slack"

RouteAction = Literal["ignore", "park", "deliver", "spawn"]


@dataclass(frozen=True)
class InboundMessage:
    """A channel or DM message as both event sources normalize it."""

    team_id: str
    channel_id: str
    user_id: str
    text: str
    ts: str
    thread_ts: str | None = None
    channel_name: str | None = None
    channel_type: str | None = None
    user_name: str | None = None
    user_avatar_url: str | None = None
    mentions_me: bool = False

    @property
    def channel(self) -> str:
        return format_channel(self.team_id, self.channel_id)

    @property
    def is_direct_message(self) -> bool:
        """1:1 or group DM — no @mention required to address the bot."""
        if self.channel_type in {"im", "mpim"}:
            return True
        # Socket Mode / older envelopes sometimes omit channel_type.
        return self.channel_id[:1].upper() == "D"

    @property
    def thread_target(self) -> str:
        """Replies thread under the parent when there is one, else this message."""
        return format_target(
            self.team_id, self.channel_id, self.thread_ts or self.ts
        )


@dataclass(frozen=True)
class RouteDecision:
    action: RouteAction
    reason: str
    session_ids: list[str] = field(default_factory=list)
    thread_target: str | None = None
    channel: str | None = None


class SlackGateway:
    def __init__(self, store: AgentStore) -> None:
        self.store = store

    def route(self, message: InboundMessage) -> RouteDecision:
        workspace = self.store.get_slack_workspace(message.team_id)
        if workspace is None:
            return RouteDecision("ignore", "unknown workspace")
        if not workspace.enabled:
            return RouteDecision("ignore", "workspace disabled")
        if workspace.bot_user_id and message.user_id == workspace.bot_user_id:
            return RouteDecision("ignore", "own message")
        if not message.text.strip():
            return RouteDecision("ignore", "empty message")

        channel = message.channel
        thread_target = message.thread_target
        listeners = self._listening_sessions(channel)
        existing = self.store.get_slack_mention_session(thread_target)

        # Mentions, DMs, and replies in a thread we already opened are addressed
        # to the agent. Random channel chatter still needs a subscription.
        addressed = (
            message.mentions_me
            or message.is_direct_message
            or existing is not None
        )

        if not addressed:
            # Ambient traffic is never parked — queuing strangers' chatter would
            # bury real approval requests.
            if not listeners:
                return RouteDecision("ignore", "no subscription")
            if not self._is_allowed(message):
                return RouteDecision("ignore", "sender not allowed")
            return RouteDecision(
                "deliver",
                "subscription",
                session_ids=listeners,
                thread_target=thread_target,
                channel=channel,
            )

        # Addressed traffic from an unknown sender is queued for approval.
        if not self._is_allowed(message):
            return RouteDecision(
                "park",
                "sender not allowed",
                thread_target=thread_target,
                channel=channel,
            )

        if listeners:
            return RouteDecision(
                "deliver",
                "subscription",
                session_ids=listeners,
                thread_target=thread_target,
                channel=channel,
            )

        if existing is not None:
            if self.store.is_session_connector_muted(
                session_id=existing, connector=CONNECTOR
            ):
                return RouteDecision("ignore", "session muted")
            return RouteDecision(
                "deliver",
                "agent thread",
                session_ids=[existing],
                thread_target=thread_target,
                channel=channel,
            )

        return RouteDecision(
            "spawn",
            "new dm" if message.is_direct_message else "new mention",
            thread_target=thread_target,
            channel=channel,
        )

    def _is_allowed(self, message: InboundMessage) -> bool:
        return self.store.is_slack_user_allowed(
            team_id=message.team_id, slack_user_id=message.user_id
        )

    def _listening_sessions(self, channel: str) -> list[str]:
        subscriptions = self.store.list_slack_subscriptions(channel=channel)
        return [
            item.session_id
            for item in subscriptions
            if not self.store.is_session_connector_muted(
                session_id=item.session_id, connector=CONNECTOR
            )
        ]

    def source_label(self, message: InboundMessage) -> str:
        """Human-readable origin for the session badge, e.g. ``#dev-ops · Acme``."""
        workspace = self.store.get_slack_workspace(message.team_id)
        team = (workspace.team_name if workspace else None) or message.team_id
        if message.is_direct_message:
            return f"DM · {team}"
        channel = message.channel_name or message.channel_id
        return f"#{channel} · {team}"
