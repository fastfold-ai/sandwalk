from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class DoctorCheckResult(ApiModel):
    name: str
    status: Literal["ok", "warn", "error"]
    detail: str
    category: str = "general"
    fix: str | None = None


class DoctorSummary(ApiModel):
    ok: int = 0
    warn: int = 0
    error: int = 0
    total: int = 0


class DoctorReport(ApiModel):
    ok: bool
    checked_at: str
    summary: DoctorSummary
    checks: list[DoctorCheckResult] = Field(default_factory=list)


class DoctorDiagnosticsRequest(ApiModel):
    ui_diagnostics: dict[str, Any] | None = None
