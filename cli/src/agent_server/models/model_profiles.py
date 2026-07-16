from __future__ import annotations

from pydantic import Field

from agent_server.models.base import ApiModel


class ModelProfile(ApiModel):
    id: str
    label: str
    backend: str
    base_url: str | None = None
    default_model: str | None = None
    discovery: list[str] = Field(default_factory=list)
    has_api_key: bool = False
    api_key_preview: str | None = None
    is_cloud: bool = False
    is_active: bool = False
    is_default: bool = False


class ModelProfileList(ApiModel):
    data: list[ModelProfile] = Field(default_factory=list)
    count: int = 0


class UpsertModelProfileRequest(ApiModel):
    id: str | None = None
    label: str | None = None
    backend: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    discovery: list[str] | None = None
    set_active: bool = False
    set_default: bool = False


class DiscoverModelEndpointRequest(ApiModel):
    """Probe an OpenAI-compatible endpoint without saving a profile first."""

    backend: str = "other"
    base_url: str
    api_key: str | None = None


class ModelProfileProbeResult(ApiModel):
    profile_id: str
    health: str
    models: list[str] = Field(default_factory=list)
    models_source: str | None = None
    error: str | None = None


class DeleteModelProfileResponse(ApiModel):
    ok: bool
    id: str
