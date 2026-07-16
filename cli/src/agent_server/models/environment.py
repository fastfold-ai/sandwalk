from __future__ import annotations

from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class EnvironmentPackage(ApiModel):
    name: str
    version: str | None = None
    installed: bool = False
    removable: bool = True


class EnvironmentPackageGroup(ApiModel):
    id: str
    label: str
    description: str
    packages: list[EnvironmentPackage] = Field(default_factory=list)


class EnvironmentCorePackage(ApiModel):
    name: str
    version: str


class EnvironmentReport(ApiModel):
    python_path: str
    env_path: str | None = None
    env_bytes: int = 0
    groups: list[EnvironmentPackageGroup] = Field(default_factory=list)
    core: list[EnvironmentCorePackage] = Field(default_factory=list)
    checked_at: str


class EnvironmentPackageRequest(ApiModel):
    name: str = Field(min_length=1)
    # When true, allow installing packages outside the skill/tool catalog
    # (still never core FastFold dependencies).
    allow_unlisted: bool = False


class EnvironmentPackageMutationResult(ApiModel):
    ok: bool = True
    action: Literal["install", "uninstall"]
    name: str
    version: str | None = None
    installed: bool = False
    message: str = ""
