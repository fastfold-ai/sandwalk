from __future__ import annotations

from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class AgentModel(ApiModel):
    id: str
    label: str
    description: str | None = None
    provider: str
    source: Literal["cloud", "profile", "custom"]
    profile_id: str | None = None
    backend: str | None = None
    enabled: bool = True
    health: str | None = None
    supports_reasoning_effort: bool = False
    reasoning_effort_options: list[str] = Field(default_factory=list)
    # Per-model Effort/Fast (only meaningful when supports_reasoning_effort).
    reasoning_effort: str | None = None
    reasoning_fast: bool = False
    # Multimodal user-input capabilities (LangChain/Deep Agents content blocks).
    supports_image_inputs: bool = False
    supports_pdf_inputs: bool = False
    supports_audio_inputs: bool = False
    supports_video_inputs: bool = False


class AgentModelList(ApiModel):
    data: list[AgentModel] = Field(default_factory=list)
    count: int = 0


class CreateAgentModelRequest(ApiModel):
    id: str
    provider: str = "openai"
    label: str | None = None


class UpdateAgentModelRequest(ApiModel):
    enabled: bool | None = None
