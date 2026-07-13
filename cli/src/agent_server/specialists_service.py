"""Specialists CRUD adapter for the agent server."""

from __future__ import annotations

from agent_server.models import Specialist
from agent_server.store import AgentStore


class SpecialistsService:
    def __init__(self, store: AgentStore) -> None:
        self._store = store

    def list(self) -> list[Specialist]:
        return self._store.list_specialists()

    def get(self, specialist_id: str) -> Specialist | None:
        return self._store.get_specialist(specialist_id)

    def create(
        self,
        *,
        name: str,
        slug: str | None = None,
        description: str | None = None,
        instructions: str | None = None,
        color: str = "ink",
        icon: str = "agent",
        skill_names: list[str] | None = None,
        mcp_server_ids: list[str] | None = None,
        mcp_catalog_ids: list[str] | None = None,
        enabled: bool = True,
    ) -> Specialist:
        return self._store.create_specialist(
            name=name,
            slug=slug,
            description=description,
            instructions=instructions,
            color=color,
            icon=icon,
            skill_names=skill_names,
            mcp_server_ids=mcp_server_ids,
            mcp_catalog_ids=mcp_catalog_ids,
            enabled=enabled,
        )

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
        skill_names: list[str] | None = None,
        mcp_server_ids: list[str] | None = None,
        mcp_catalog_ids: list[str] | None = None,
        enabled: bool | None = None,
    ) -> Specialist | None:
        return self._store.update_specialist(
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
            mcp_server_ids=mcp_server_ids,
            mcp_catalog_ids=mcp_catalog_ids,
            enabled=enabled,
        )

    def delete(self, specialist_id: str) -> bool:
        return self._store.delete_specialist(specialist_id)
