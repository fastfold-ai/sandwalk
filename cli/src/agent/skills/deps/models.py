"""Structured status for skill runtime dependency adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CheckStatus = Literal["ok", "missing", "error", "warn"]
OverallStatus = Literal["ok", "missing", "error"]


@dataclass
class SkillDepCheck:
    name: str
    status: CheckStatus
    detail: str
    fix: str = ""

    def as_dict(self) -> dict[str, str]:
        out = {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
        }
        if self.fix:
            out["fix"] = self.fix
        return out


@dataclass
class SkillDepSetupStep:
    title: str
    body: str

    def as_dict(self) -> dict[str, str]:
        return {"title": self.title, "body": self.body}


@dataclass
class SkillDepStatus:
    """Runtime dependency status for one skill adapter."""

    adapter_id: str
    skill_name: str
    status: OverallStatus
    summary: str
    command: str = ""
    checks: list[SkillDepCheck] = field(default_factory=list)
    setup_steps: list[SkillDepSetupStep] = field(default_factory=list)
    has_runtime_deps: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "skill_name": self.skill_name,
            "status": self.status,
            "summary": self.summary,
            "command": self.command,
            "has_runtime_deps": self.has_runtime_deps,
            "checks": [check.as_dict() for check in self.checks],
            "setup_steps": [step.as_dict() for step in self.setup_steps],
        }


@dataclass
class SkillDepInstallResult:
    ok: bool
    summary: str
    status: SkillDepStatus | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok, "summary": self.summary}
        if self.status is not None:
            out["status"] = self.status.as_dict()
        return out
