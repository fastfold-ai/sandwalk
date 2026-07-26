"""Slack connector API models (workspaces, allowlist, subscriptions, parked)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel

# relay = inbound via FastFold Cloud; socket = inbound via Slack Socket Mode.
SlackMode = Literal["relay", "socket"]

ConnectorName = Literal["slack"]


class SlackWorkspace(ApiModel):
    team_id: str
    team_name: str | None = None
    domain: str | None = None
    mode: SlackMode
    bot_user_id: str | None = None
    connection_id: str | None = None
    # Whether this workspace supports Slack's Agents & AI Apps container.
    assistant_enabled: bool = False
    enabled: bool = True
    # True when a usable bot token is stored locally; the token itself is never
    # returned over the API.
    has_bot_token: bool = False
    has_app_token: bool = False
    created_at: datetime
    updated_at: datetime


class SlackWorkspaceList(ApiModel):
    data: list[SlackWorkspace]


class SlackAllowedUser(ApiModel):
    team_id: str
    slack_user_id: str
    display_name: str | None = None
    created_at: datetime


class SlackSubscription(ApiModel):
    session_id: str
    channel: str
    created_at: datetime


class SlackParkedMessage(ApiModel):
    id: str
    team_id: str
    channel: str
    thread_target: str | None = None
    slack_user_id: str
    user_name: str | None = None
    text: str
    created_at: datetime


class SessionConnectorMute(ApiModel):
    session_id: str
    connector: ConnectorName
    muted: bool


class ConnectSlackManualRequest(ApiModel):
    bot_token: str = Field(min_length=1)
    app_token: str = Field(min_length=1)


class StartSlackOneClickRequest(ApiModel):
    return_to: str | None = None


class SlackOneClickStart(ApiModel):
    """Where to send the browser to install the Sandwalk Slack app."""

    auth_url: str


class AllowSlackUserRequest(ApiModel):
    team_id: str = Field(min_length=1)
    slack_user_id: str = Field(min_length=1)
    display_name: str | None = None


class AddSlackSubscriptionRequest(ApiModel):
    session_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)


class SetConnectorMuteRequest(ApiModel):
    muted: bool


class SlackDirectoryPerson(ApiModel):
    id: str
    name: str
    handle: str | None = None
    avatar_url: str | None = None


class SlackDirectoryChannel(ApiModel):
    id: str
    name: str
    is_private: bool = False


class SlackDirectory(ApiModel):
    people: list[SlackDirectoryPerson] = []
    channels: list[SlackDirectoryChannel] = []


class SlackManifestResponse(ApiModel):
    app_name: str
    manifest: str
    steps: list[str]


class SlackParkedMessageList(ApiModel):
    data: list[SlackParkedMessage]


class SlackAllowedUserList(ApiModel):
    data: list[SlackAllowedUser]


class SlackSubscriptionList(ApiModel):
    data: list[SlackSubscription]


class ConnectorActionResponse(ApiModel):
    ok: bool = True


class SlackConnectorStatus(ApiModel):
    mode: SlackMode | None = None
    # signed_out / auth_expired / reconnecting / live / off
    relay_state: Literal[
        "off", "signed_out", "auth_expired", "reconnecting", "live"
    ] = "off"
    relay_detail: str | None = None
    workspaces: list[SlackWorkspace] = []
