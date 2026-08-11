"""Skill runtime dependency status / install mixin."""

from __future__ import annotations

from agent_server.models import (
    SkillDepCheck,
    SkillDepsInstallResponse,
    SkillDepsStatus,
    SkillDepSetupStep,
)


class DepsMixin:
    @staticmethod
    def _status_from_core(status) -> SkillDepsStatus:
        return SkillDepsStatus(
            adapter_id=status.adapter_id,
            skill_name=status.skill_name,
            status=status.status,
            summary=status.summary,
            command=status.command or "",
            has_runtime_deps=bool(status.has_runtime_deps),
            checks=[
                SkillDepCheck(
                    name=check.name,
                    status=check.status,
                    detail=check.detail,
                    fix=check.fix or "",
                )
                for check in status.checks
            ],
            setup_steps=[
                SkillDepSetupStep(title=step.title, body=step.body)
                for step in status.setup_steps
            ],
        )

    def get_deps(self, skill_name: str) -> SkillDepsStatus:
        from agent.skills.deps import doctor_skill, has_runtime_deps

        if not has_runtime_deps(skill_name):
            raise LookupError(
                f"No runtime dependency adapter for skill {skill_name!r}."
            )
        return self._status_from_core(doctor_skill(skill_name))

    def doctor_deps(self, skill_name: str) -> SkillDepsStatus:
        return self.get_deps(skill_name)

    def install_deps(
        self, skill_name: str, *, force: bool = False
    ) -> SkillDepsInstallResponse:
        from agent.skills.deps import install_skill_deps

        try:
            result = install_skill_deps(skill_name, force=force)
        except LookupError as exc:
            raise LookupError(str(exc)) from exc
        status = (
            self._status_from_core(result.status)
            if result.status is not None
            else None
        )
        return SkillDepsInstallResponse(
            ok=bool(result.ok),
            summary=str(result.summary or ""),
            status=status,
        )
