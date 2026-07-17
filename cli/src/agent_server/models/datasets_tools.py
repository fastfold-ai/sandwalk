from __future__ import annotations

from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class DatasetSummary(ApiModel):
    id: str
    description: str
    status: Literal["complete", "partial", "missing", "on-demand"]
    files_found: int = 0
    files_expected: int = 0
    size_bytes: int | None = None
    size_display: str = "-"
    auto_download: bool = False
    path: str
    source: str | None = None
    note: str | None = None


class DatasetList(ApiModel):
    data: list[DatasetSummary] = Field(default_factory=list)
    count: int = 0


class DatasetInstallResponse(ApiModel):
    ok: bool
    id: str
    status: str
    summary: str
    dataset: DatasetSummary | None = None


class ToolSummary(ApiModel):
    id: str
    name: str
    category: str
    status: Literal["stable", "experimental", "guarded"]
    tier: Literal["core", "extra"] = "extra"
    description: str
    requires_data: list[str] = Field(default_factory=list)
    enabled: bool = True
    # False for registry core tools — always on; UI should lock the toggle.
    toggleable: bool = True


class ToolList(ApiModel):
    data: list[ToolSummary] = Field(default_factory=list)
    count: int = 0
    categories: list[str] = Field(default_factory=list)
    load_errors: dict[str, str] = Field(default_factory=dict)


class UpdateToolRequest(ApiModel):
    enabled: bool | None = None


ToolBatchAction = Literal["enable", "disable"]


class ToolBatchActionRequest(ApiModel):
    action: ToolBatchAction
    ids: list[str] = Field(default_factory=list)


class ToolBatchActionResponse(ApiModel):
    ok: bool
    action: ToolBatchAction
    requested: int
    succeeded: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    summary: str
