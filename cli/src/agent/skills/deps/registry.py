"""Registry of skill runtime-dependency adapters."""

from __future__ import annotations

from typing import Protocol

from agent.skills.deps.models import SkillDepInstallResult, SkillDepStatus


class SkillDepAdapter(Protocol):
    adapter_id: str
    skill_names: frozenset[str]

    def doctor(self) -> SkillDepStatus: ...

    def install(self, *, force: bool = False) -> SkillDepInstallResult: ...


class _AnyDocAdapter:
    adapter_id = "anydoc"
    skill_names = frozenset({"convert-documents-to-markdown"})

    def doctor(self) -> SkillDepStatus:
        from agent.skills.deps import anydoc

        return anydoc.doctor()

    def install(self, *, force: bool = False) -> SkillDepInstallResult:
        from agent.skills.deps import anydoc

        return anydoc.install(force=force)


class _ModalResearchAdapter:
    adapter_id = "modal-research"
    skill_names = frozenset(
        {"modal-basic-skills", "modal-gpu-dev", "modal-gpu-experiment", "sub-agents"}
    )

    def doctor(self) -> SkillDepStatus:
        from agent.skills.deps import modal_research

        return modal_research.doctor()

    def install(self, *, force: bool = False) -> SkillDepInstallResult:
        from agent.skills.deps import modal_research

        return modal_research.install(force=force)


_ADAPTERS: list[SkillDepAdapter] = [_AnyDocAdapter(), _ModalResearchAdapter()]


def list_adapters() -> list[SkillDepAdapter]:
    return list(_ADAPTERS)


def adapter_ids() -> list[str]:
    return [adapter.adapter_id for adapter in _ADAPTERS]


def has_runtime_deps(skill_name: str) -> bool:
    return get_adapter(skill_name) is not None


def get_adapter(skill_name: str | None) -> SkillDepAdapter | None:
    key = str(skill_name or "").strip().lower().replace("_", "-")
    if not key:
        return None
    for adapter in _ADAPTERS:
        names = {
            str(name).strip().lower().replace("_", "-")
            for name in adapter.skill_names
        }
        if key in names or key == adapter.adapter_id:
            return adapter
    return None


def doctor_skill(skill_name: str) -> SkillDepStatus:
    adapter = get_adapter(skill_name)
    if adapter is None:
        raise LookupError(
            f"No runtime dependency adapter for skill {skill_name!r}."
        )
    return adapter.doctor()


def install_skill_deps(
    skill_name: str, *, force: bool = False
) -> SkillDepInstallResult:
    adapter = get_adapter(skill_name)
    if adapter is None:
        raise LookupError(
            f"No runtime dependency adapter for skill {skill_name!r}."
        )
    return adapter.install(force=force)


def status_all() -> list[SkillDepStatus]:
    return [adapter.doctor() for adapter in _ADAPTERS]


def status_for(skill_name: str | None = None) -> list[SkillDepStatus]:
    if skill_name:
        return [doctor_skill(skill_name)]
    return status_all()
