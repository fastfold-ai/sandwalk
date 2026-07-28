from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class IntegrationField(ApiModel):
    env_var: str
    label: str
    is_secret: bool = True
    configured: bool
    source: Literal["environment", "config", "none"]
    masked_preview: str | None = None
    updated_at: datetime | None = None


class IntegrationUnlock(ApiModel):
    kind: Literal["tool", "skill", "capability", "notice"]
    id: str
    label: str
    description: str
    source: str | None = None
    requirement: Literal[
        "built_in",
        "install",
        "connector",
        "ambient",
        "not_wired",
    ] = "built_in"
    installable: bool = False
    installed: bool | None = None
    status_detail: str | None = None


class IntegrationProvider(ApiModel):
    key: str
    name: str
    category: str
    description: str
    env_var: str
    configured: bool
    source: Literal["environment", "config", "none"]
    masked_preview: str | None = None
    setup_url: str | None = None
    free: bool = False
    fields: list[IntegrationField] = Field(default_factory=list)
    unlocks: list[IntegrationUnlock] = Field(default_factory=list)


class IntegrationList(ApiModel):
    data: list[IntegrationProvider]


class UpdateIntegrationRequest(ApiModel):
    value: str | None = None
    values: dict[str, str] = Field(default_factory=dict)


class ValidateIntegrationResponse(ApiModel):
    ok: bool
    configured: bool
    source: Literal["environment", "config", "none"]
    message: str


class IntegrationSetupStep(ApiModel):
    id: str
    label: str
    ok: bool
    detail: str


class IntegrationSetupResponse(ApiModel):
    ok: bool
    integration_key: str
    summary: str
    steps: list[IntegrationSetupStep] = Field(default_factory=list)


class IntegrationSetupRequest(ApiModel):
    working_directory: str | None = None
