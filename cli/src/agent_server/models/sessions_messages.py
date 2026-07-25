from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from agent_server.models.base import ApiModel

MessageRole = Literal["user", "assistant", "system"]


class MessageSource(ApiModel):
    """Where an inbound message came from, for display only.

    The model still sees the framed ``content``; this drives the card the UI
    renders above it so a Slack message reads as a Slack message.
    """

    connector: Literal["slack"]
    channel_id: str
    channel_name: str | None = None
    sender_id: str
    sender_name: str | None = None
    sender_avatar_url: str | None = None
    # Raw message text, without the reply-handle framing the model needs.
    text: str
    permalink: str | None = None


class AgentMessage(ApiModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    source: MessageSource | None = None
    created_at: datetime


class SendMessageRequest(ApiModel):
    content: str = Field(min_length=1)


class StartRunResponse(ApiModel):
    run_id: str


class EventEnvelope(ApiModel):
    schema_version: Literal[1] = 1
    id: str
    session_id: str
    run_id: str | None = None
    sequence: int
    timestamp: datetime
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class MessageList(ApiModel):
    data: list[AgentMessage]
    feedback: dict[str, Literal["up", "down"]] = Field(default_factory=dict)


class EventList(ApiModel):
    data: list[EventEnvelope]


class MessageFeedbackRequest(ApiModel):
    reaction: Literal["up", "down"] | None = None


class MessageFeedbackResponse(ApiModel):
    message_id: str
    reaction: Literal["up", "down"] | None = None
