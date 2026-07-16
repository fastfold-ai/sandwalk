"""Specialist update/delete."""

from __future__ import annotations

import json

from agent_server.models import Specialist
from agent_server.store.util import utc_now


class SpecialistUpdateMixin:
    def update_specialist(
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
        tool_names: list[str] | None = None,
        mcp_server_ids: list[str] | None = None,
        mcp_catalog_ids: list[str] | None = None,
        enabled: bool | None = None,
    ) -> Specialist | None:
        current = self.get_specialist(specialist_id)
        if current is None:
            return None
        next_name = current.name
        if name is not None:
            next_name = name.strip()
            if not next_name:
                raise ValueError("Specialist name cannot be empty.")
        next_slug = current.slug
        if slug is not None:
            next_slug = self._slugify(slug)
        next_description = current.description
        if update_description:
            next_description = (description or "").strip() or None
        next_instructions = current.instructions
        if update_instructions:
            next_instructions = (instructions or "").strip() or None
        next_color = current.color if color is None else ((color or "").strip() or "ink")
        next_icon = current.icon if icon is None else ((icon or "").strip() or "agent")
        next_skills = (
            current.skill_names
            if skill_names is None
            else [str(item).strip() for item in skill_names if str(item).strip()]
        )
        next_tools = (
            current.tool_names
            if tool_names is None
            else [str(item).strip() for item in tool_names if str(item).strip()]
        )
        next_mcps = (
            current.mcp_server_ids
            if mcp_server_ids is None
            else [str(item).strip() for item in mcp_server_ids if str(item).strip()]
        )
        next_catalogs = (
            current.mcp_catalog_ids
            if mcp_catalog_ids is None
            else [str(item).strip() for item in mcp_catalog_ids if str(item).strip()]
        )
        next_enabled = current.enabled if enabled is None else bool(enabled)
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            if next_slug != current.slug:
                clash = connection.execute(
                    "SELECT id FROM specialists WHERE slug = ? AND id != ?",
                    (next_slug, specialist_id),
                ).fetchone()
                if clash is not None:
                    raise ValueError(f"Specialist slug already exists: {next_slug}")
            connection.execute(
                """
                UPDATE specialists
                SET name = ?, slug = ?, description = ?, instructions = ?,
                    color = ?, icon = ?, skill_names = ?, tool_names = ?,
                    mcp_server_ids = ?, mcp_catalog_ids = ?, enabled = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    next_name,
                    next_slug,
                    next_description,
                    next_instructions,
                    next_color,
                    next_icon,
                    json.dumps(next_skills),
                    json.dumps(next_tools),
                    json.dumps(next_mcps),
                    json.dumps(next_catalogs),
                    1 if next_enabled else 0,
                    now.isoformat(),
                    specialist_id,
                ),
            )
        return self.get_specialist(specialist_id)

    def delete_specialist(self, specialist_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET specialist_id = NULL WHERE specialist_id = ?",
                (specialist_id,),
            )
            cursor = connection.execute(
                "DELETE FROM specialists WHERE id = ?", (specialist_id,)
            )
        return cursor.rowcount > 0
