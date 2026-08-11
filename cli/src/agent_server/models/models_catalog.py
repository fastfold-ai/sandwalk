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
    # False when Fast (thinking off) is rejected — e.g. Muse Spark mandatory reasoning.
    supports_reasoning_fast: bool = True
    reasoning_effort_options: list[str] = Field(default_factory=list)
    # Per-model Effort/Fast (only meaningful when supports_reasoning_effort).
    reasoning_effort: str | None = None
    reasoning_fast: bool = False
    # Multimodal user-input capabilities (LangChain/Deep Agents content blocks).
    supports_image_inputs: bool = False
    supports_pdf_inputs: bool = False
    supports_audio_inputs: bool = False
    supports_video_inputs: bool = False
    # Effective context window when known (e.g. oMLX max_model_len).
    context_window: int | None = None


class AgentModelList(ApiModel):
    data: list[AgentModel] = Field(default_factory=list)
    count: int = 0


class CreateAgentModelRequest(ApiModel):
    id: str
    provider: str = "openai"
    label: str | None = None


class UpdateAgentModelRequest(ApiModel):
    enabled: bool | None = None
    # When set, toggle only this provider's row for a shared bare model id
    # (e.g. kimi-k3 on moonshot vs opencode).
    provider: str | None = None


class ModelPreferences(ApiModel):
    """Pinned favorites + recently selected models (``provider:model`` keys)."""

    favorites: list[str] = Field(default_factory=list)
    recent: list[str] = Field(default_factory=list)


class ToggleModelFavoriteRequest(ApiModel):
    provider: str | None = None
    model: str
    profile_id: str | None = None


class ToggleModelFavoriteResponse(ApiModel):
    favorite: bool
    favorites: list[str] = Field(default_factory=list)
