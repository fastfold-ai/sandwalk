"""Project CRUD."""

from __future__ import annotations

import sqlite3
import uuid

from agent_server.models import AgentProject
from agent_server.project_folder import (
    normalize_project_color,
    normalize_project_icon,
    validate_project_folder_path,
)
from agent_server.store.rows import project_from_row
from agent_server.store.util import utc_now


class ProjectMixin:
    @staticmethod
    def _project(row: sqlite3.Row, *, session_count: int = 0) -> AgentProject:
        return project_from_row(row, session_count=session_count)

    def create_project(
        self,
        *,
        name: str,
        description: str | None = None,
        agent_context: str | None = None,
        folder_path: str | None = None,
        icon: str | None = None,
        color: str | None = None,
        pinned: bool = False,
    ) -> AgentProject:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Project name cannot be empty.")
        next_folder = validate_project_folder_path(folder_path)
        next_icon = normalize_project_icon(icon)
        next_color = normalize_project_color(color)
        now = utc_now()
        project_id = str(uuid.uuid4())
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO projects(
                    id, name, description, agent_context, folder_path, icon, color,
                    pinned, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    normalized,
                    (description or "").strip() or None,
                    (agent_context or "").strip() or None,
                    next_folder,
                    next_icon,
                    next_color,
                    1 if pinned else 0,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        project = self.get_project(project_id)
        if project is None:
            raise RuntimeError("Failed to create project.")
        return project

    def list_projects(self) -> list[AgentProject]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    projects.*,
                    (
                        SELECT COUNT(*)
                        FROM sessions
                        WHERE sessions.project_id = projects.id
                    ) AS session_count
                FROM projects
                ORDER BY projects.pinned DESC, projects.updated_at DESC, projects.id DESC
                """
            ).fetchall()
        return [
            project_from_row(row, session_count=int(row["session_count"] or 0))
            for row in rows
        ]

    def get_project(self, project_id: str) -> AgentProject | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    projects.*,
                    (
                        SELECT COUNT(*)
                        FROM sessions
                        WHERE sessions.project_id = projects.id
                    ) AS session_count
                FROM projects
                WHERE projects.id = ?
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return project_from_row(row, session_count=int(row["session_count"] or 0))

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        update_description: bool = False,
        agent_context: str | None = None,
        update_agent_context: bool = False,
        folder_path: str | None = None,
        update_folder_path: bool = False,
        icon: str | None = None,
        color: str | None = None,
        pinned: bool | None = None,
    ) -> AgentProject | None:
        current = self.get_project(project_id)
        if current is None:
            return None
        next_name = current.name
        if name is not None:
            next_name = name.strip()
            if not next_name:
                raise ValueError("Project name cannot be empty.")
        next_description = current.description
        if update_description:
            next_description = (description or "").strip() or None
        next_context = current.agent_context
        if update_agent_context:
            next_context = (agent_context or "").strip() or None
        next_folder = current.folder_path
        if update_folder_path:
            next_folder = validate_project_folder_path(folder_path)
        next_icon = current.icon
        if icon is not None:
            next_icon = normalize_project_icon(icon)
        next_color = current.color
        if color is not None:
            next_color = normalize_project_color(color)
        next_pinned = current.pinned if pinned is None else bool(pinned)
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE projects
                SET name = ?, description = ?, agent_context = ?, folder_path = ?,
                    icon = ?, color = ?, pinned = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_name,
                    next_description,
                    next_context,
                    next_folder,
                    next_icon,
                    next_color,
                    1 if next_pinned else 0,
                    now.isoformat(),
                    project_id,
                ),
            )
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        """Delete the project and all sessions under it (messages/events cascade)."""
        with self._write_lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE project_id = ?",
                (project_id,),
            )
            cursor = connection.execute(
                "DELETE FROM projects WHERE id = ?", (project_id,)
            )
        return cursor.rowcount > 0
