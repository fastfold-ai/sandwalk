from __future__ import annotations

from datetime import datetime

from pydantic import Field

from agent_server.models.base import ApiModel


class Specialist(ApiModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    instructions: str | None = None
    color: str = "ink"
    icon: str = "agent"
    role_label: str | None = None
    avatar_url: str | None = None
    provider: str | None = None
    model: str | None = None
    openai_profile_id: str | None = None
    cookbook_id: str | None = None
    priors: str | None = None
    memory_count: int = 0
    skill_names: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)
    mcp_catalog_ids: list[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class CreateSpecialistRequest(ApiModel):
    name: str = Field(min_length=1)
    slug: str | None = None
    description: str | None = None
    instructions: str | None = None
    color: str = "ink"
    icon: str = "agent"
    role_label: str | None = None
    avatar_url: str | None = None
    provider: str | None = None
    model: str | None = None
    openai_profile_id: str | None = None
    cookbook_id: str | None = None
    priors: str | None = None
    skill_names: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)
    mcp_catalog_ids: list[str] = Field(default_factory=list)
    enabled: bool = True


class UpdateSpecialistRequest(ApiModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    instructions: str | None = None
    color: str | None = None
    icon: str | None = None
    role_label: str | None = None
    avatar_url: str | None = None
    provider: str | None = None
    model: str | None = None
    openai_profile_id: str | None = None
    cookbook_id: str | None = None
    priors: str | None = None
    skill_names: list[str] | None = None
    tool_names: list[str] | None = None
    mcp_server_ids: list[str] | None = None
    mcp_catalog_ids: list[str] | None = None
    enabled: bool | None = None
    clear_description: bool = False
    clear_instructions: bool = False
    clear_llm: bool = False
    clear_priors: bool = False


class SpecialistList(ApiModel):
    data: list[Specialist]


class DeleteSpecialistResponse(ApiModel):
    deleted: bool = True
