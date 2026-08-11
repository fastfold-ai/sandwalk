"""Messaging connectors (currently Slack) for the agent server."""

from __future__ import annotations

from agent_server.connectors.addressing import (
    CONNECTOR,
    SlackTarget,
    format_channel,
    format_target,
    is_slack_target,
    parse_target,
    resolve_channel_input,
    thread_ts_from_permalink,
)

__all__ = [
    "CONNECTOR",
    "SlackTarget",
    "format_channel",
    "format_target",
    "is_slack_target",
    "parse_target",
    "resolve_channel_input",
    "thread_ts_from_permalink",
]
