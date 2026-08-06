"""Runtime dependency adapters for skills that need extra libs/CLIs."""

from __future__ import annotations

from agent.skills.deps.models import (
    SkillDepCheck,
    SkillDepInstallResult,
    SkillDepSetupStep,
    SkillDepStatus,
)
from agent.skills.deps.registry import (
    adapter_ids,
    doctor_skill,
    get_adapter,
    has_runtime_deps,
    install_skill_deps,
    list_adapters,
    status_all,
    status_for,
)

__all__ = [
    "SkillDepCheck",
    "SkillDepInstallResult",
    "SkillDepSetupStep",
    "SkillDepStatus",
    "adapter_ids",
    "doctor_skill",
    "get_adapter",
    "has_runtime_deps",
    "install_skill_deps",
    "list_adapters",
    "status_all",
    "status_for",
]
