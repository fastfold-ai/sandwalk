"""Specialists CRUD adapter for the agent server."""

from __future__ import annotations

from agent_server.models import Specialist
from agent_server.store import AgentStore


def _enrich_specialist(specialist: Specialist) -> Specialist:
    try:
        from agent_server.memory_service.store import MemoryStore

        mstore = MemoryStore()
        cnt = mstore.count_scope_memories(f"specialist:{specialist.id}")
        if cnt == 0 and specialist.slug:
            cnt = mstore.count_scope_memories(f"specialist:{specialist.slug}")
        persona = mstore.get_specialist_persona(specialist.id, specialist.slug)
        return specialist.model_copy(
            update={
                "memory_count": cnt,
                "role_label": persona.get("role_label") or specialist.role_label,
                "avatar_url": persona.get("avatar_url") or specialist.avatar_url,
                "provider": persona.get("provider") or specialist.provider,
                "model": persona.get("model") or specialist.model,
                "openai_profile_id": persona.get("openai_profile_id")
                or specialist.openai_profile_id,
                "cookbook_id": persona.get("cookbook_id") or specialist.cookbook_id,
                "priors": persona.get("priors") or specialist.priors,
            }
        )
    except Exception:
        return specialist


class SpecialistsService:
    def __init__(self, store: AgentStore) -> None:
        self._store = store
        try:
            from agent_server.default_specialists import ensure_persona_specialists

            ensure_persona_specialists(store)
        except Exception:
            pass

    def list(self) -> list[Specialist]:
        return [_enrich_specialist(s) for s in self._store.list_specialists()]

    def get(self, specialist_id: str) -> Specialist | None:
        found = self._store.get_specialist(specialist_id)
        return _enrich_specialist(found) if found else None

    def create(
        self,
        *,
        name: str,
        slug: str | None = None,
        description: str | None = None,
        instructions: str | None = None,
        color: str = "ink",
        icon: str = "agent",
        role_label: str | None = None,
        avatar_url: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        openai_profile_id: str | None = None,
        cookbook_id: str | None = None,
        priors: str | None = None,
        skill_names: list[str] | None = None,
        tool_names: list[str] | None = None,
        mcp_server_ids: list[str] | None = None,
        mcp_catalog_ids: list[str] | None = None,
        enabled: bool = True,
    ) -> Specialist:
        created = self._store.create_specialist(
            name=name,
            slug=slug,
            description=description,
            instructions=instructions,
            color=color,
            icon=icon,
            skill_names=skill_names,
            tool_names=tool_names,
            mcp_server_ids=mcp_server_ids,
            mcp_catalog_ids=mcp_catalog_ids,
            enabled=enabled,
        )
        if any(
            v is not None
            for v in (
                role_label,
                avatar_url,
                provider,
                model,
                openai_profile_id,
                cookbook_id,
                priors,
            )
        ):
            try:
                from agent_server.memory_service.store import MemoryStore

                MemoryStore().upsert_specialist_persona(
                    created.id,
                    slug=created.slug,
                    role_label=role_label,
                    avatar_url=avatar_url,
                    provider=provider,
                    model=model,
                    openai_profile_id=openai_profile_id,
                    cookbook_id=cookbook_id,
                    priors=priors,
                )
            except Exception:
                pass
        return _enrich_specialist(created)

    def update(
        self,
        specialist_id: str,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        update_description: bool = False,
        instructions: str | None = None,
        update_instructions: bool = False,
        color: str | None = None,
        icon: str | None = None,
        role_label: str | None = None,
        avatar_url: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        openai_profile_id: str | None = None,
        clear_llm: bool = False,
        cookbook_id: str | None = None,
        priors: str | None = None,
        clear_priors: bool = False,
        skill_names: list[str] | None = None,
        tool_names: list[str] | None = None,
        mcp_server_ids: list[str] | None = None,
        mcp_catalog_ids: list[str] | None = None,
        enabled: bool | None = None,
    ) -> Specialist | None:
        updated = self._store.update_specialist(
            specialist_id,
            name=name,
            slug=slug,
            description=description,
            update_description=update_description,
            instructions=instructions,
            update_instructions=update_instructions,
            color=color,
            icon=icon,
            skill_names=skill_names,
            tool_names=tool_names,
            mcp_server_ids=mcp_server_ids,
            mcp_catalog_ids=mcp_catalog_ids,
            enabled=enabled,
        )
        if updated is None:
            return None
        if (
            any(
                v is not None
                for v in (
                    role_label,
                    avatar_url,
                    provider,
                    model,
                    openai_profile_id,
                    cookbook_id,
                    priors,
                )
            )
            or clear_llm
            or clear_priors
        ):
            try:
                from agent_server.memory_service.store import MemoryStore

                MemoryStore().upsert_specialist_persona(
                    updated.id,
                    slug=updated.slug,
                    role_label=role_label,
                    avatar_url=avatar_url,
                    provider=provider,
                    model=model,
                    openai_profile_id=openai_profile_id,
                    clear_llm=clear_llm,
                    cookbook_id=cookbook_id,
                    priors=priors,
                    clear_priors=clear_priors,
                )
            except Exception:
                pass
        return _enrich_specialist(updated)

    def delete(self, specialist_id: str) -> bool:
        return self._store.delete_specialist(specialist_id)
