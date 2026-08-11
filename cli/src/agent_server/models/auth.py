from __future__ import annotations

from pydantic import Field

from agent_server.models.base import ApiModel


class AuthStatusResponse(ApiModel):
    auth_enabled: bool = False
    api_key_configured: bool = False
    authenticated: bool = False


class AuthLoginRequest(ApiModel):
    api_key: str = Field(min_length=1)
    remember: bool = False


class AuthSettingsResponse(ApiModel):
    auth_enabled: bool = False
    api_key: str = ""
    api_key_configured: bool = False


class UpdateAuthSettingsRequest(ApiModel):
    api_key: str | None = None
    auth_enabled: bool | None = None
