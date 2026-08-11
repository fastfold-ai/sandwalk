"""Specialist creation and read-only lookups.

Mutations (update/delete) live in :mod:`agent_server.store.specialist_updates`.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid

from agent_server.models import Specialist
from agent_server.store.rows import specialist_from_row
from agent_server.store.util import utc_now


class SpecialistMixin:
    @staticmethod
    def _specialist(row: sqlite3.Row) -> Specialist:
        return specialist_from_row(row)

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        return slug or "specialist"

    def create_specialist(
        self,
        *,
        name: str,
        slug: str | None = None,
        description: str | None = None,
        instructions: str | None = None,
        color: str = "ink",
        icon: str = "git-branch",
        skill_names: list[str] | None = None,
        tool_names: list[str] | None = None,
        mcp_server_ids: list[str] | None = None,
        mcp_catalog_ids: list[str] | None = None,
        enabled: bool = True,
    ) -> Specialist:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Specialist name cannot be empty.")
        next_slug = self._slugify(slug or normalized)
        now = utc_now()
        specialist_id = str(uuid.uuid4())
        skills = [str(item).strip() for item in (skill_names or []) if str(item).strip()]
        tools = [str(item).strip() for item in (tool_names or []) if str(item).strip()]
        mcps = [
            str(item).strip() for item in (mcp_server_ids or []) if str(item).strip()
        ]
        catalogs = [
            str(item).strip() for item in (mcp_catalog_ids or []) if str(item).strip()
        ]
        with self._write_lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM specialists WHERE slug = ?", (next_slug,)
            ).fetchone()
            if existing is not None:
                raise ValueError(f"Specialist slug already exists: {next_slug}")
            connection.execute(
                """
                INSERT INTO specialists(
                    id, name, slug, description, instructions, color, icon,
                    skill_names, tool_names, mcp_server_ids, mcp_catalog_ids, enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    specialist_id,
                    normalized,
                    next_slug,
                    (description or "").strip() or None,
                    (instructions or "").strip() or None,
                    (color or "ink").strip() or "ink",
                    (icon or "git-branch").strip() or "git-branch",
                    json.dumps(skills),
                    json.dumps(tools),
                    json.dumps(mcps),
                    json.dumps(catalogs),
                    1 if enabled else 0,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        specialist = self.get_specialist(specialist_id)
        if specialist is None:
            raise RuntimeError("Failed to create specialist.")
        return specialist

    def list_specialists(self) -> list[Specialist]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM specialists
                ORDER BY updated_at DESC, name ASC, id DESC
                """
            ).fetchall()
        return [specialist_from_row(row) for row in rows]

    def get_specialist(self, specialist_id: str) -> Specialist | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM specialists WHERE id = ?", (specialist_id,)
            ).fetchone()
        return specialist_from_row(row) if row else None

    def get_specialist_by_slug(self, slug: str) -> Specialist | None:
        key = self._slugify(slug)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM specialists WHERE slug = ?", (key,)
            ).fetchone()
        return specialist_from_row(row) if row else None

    def resolve_specialist_ref(self, ref: str) -> Specialist | None:
        """Resolve by id, slug, or case-insensitive name."""
        key = (ref or "").strip()
        if not key:
            return None
        by_id = self.get_specialist(key)
        if by_id is not None:
            return by_id
        by_slug = self.get_specialist_by_slug(key)
        if by_slug is not None:
            return by_slug
        lowered = key.lower()
        for specialist in self.list_specialists():
            if specialist.name.strip().lower() == lowered:
                return specialist
        return None
