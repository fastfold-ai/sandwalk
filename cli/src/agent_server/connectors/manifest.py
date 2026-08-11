"""Slack app manifest for the manual (Socket Mode) setup path.

Handing the user a ready manifest means they never assemble a scope list by hand,
which is where manual setup usually goes wrong. Socket Mode also lets
interactivity work without a public Request URL — Slack's validator rejects
event subscriptions that have neither.
"""

from __future__ import annotations

import json

DEFAULT_APP_NAME = "Sandwalk"

BOT_SCOPES = [
    "app_mentions:read",
    "channels:history",
    "channels:join",
    "channels:read",
    "chat:write",
    "chat:write.public",
    "groups:history",
    "groups:read",
    "im:history",
    "im:read",
    "reactions:write",
    "users:read",
]

BOT_EVENTS = [
    "app_mention",
    "message.channels",
    "message.groups",
    "message.im",
]


def build_manifest(app_name: str = DEFAULT_APP_NAME) -> dict:
    name = (app_name or DEFAULT_APP_NAME).strip() or DEFAULT_APP_NAME
    return {
        "display_information": {
            "name": name,
            "description": "Your research agent, in Slack.",
            "background_color": "#101014",
        },
        "features": {
            "bot_user": {"display_name": name, "always_online": False},
            "app_home": {
                "home_tab_enabled": False,
                "messages_tab_enabled": True,
                "messages_tab_read_only_enabled": False,
            },
        },
        "oauth_config": {"scopes": {"bot": list(BOT_SCOPES)}},
        "settings": {
            "event_subscriptions": {"bot_events": list(BOT_EVENTS)},
            # Valid without a Request URL only because Socket Mode is on.
            "interactivity": {"is_enabled": True},
            "socket_mode_enabled": True,
            "org_deploy_enabled": False,
            "token_rotation_enabled": False,
        },
    }


def build_manifest_json(app_name: str = DEFAULT_APP_NAME) -> str:
    return json.dumps(build_manifest(app_name), indent=2)


SETUP_STEPS = [
    "Open api.slack.com/apps and choose Create New App → From an app manifest.",
    "Pick your workspace, paste the manifest above, and create the app.",
    "Under OAuth & Permissions, click Install to Workspace and copy the bot token (xoxb-…).",
    "Under Basic Information → App-Level Tokens, generate a token with the "
    "connections:write scope and copy it (xapp-…).",
    "Paste both tokens here to connect.",
]
