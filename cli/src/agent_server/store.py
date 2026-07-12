"""SQLite persistence for sessions, messages, and replayable events."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.config import CONFIG_DIR
from agent_server.models import (
    AgentMessage,
    AgentProject,
    AgentSession,
    EventEnvelope,
    McpServer,
    MessageRole,
    SessionStatus,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class AgentStore:
    """Small durable store shared by CLI and web transports."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or (CONFIG_DIR / "agent-server.db")).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    organize_label TEXT,
                    workspace_path TEXT,
                    last_message_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS messages_session_created
                    ON messages(session_id, created_at, id);

                CREATE TABLE IF NOT EXISTS message_feedback (
                    message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                    reaction TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    run_id TEXT,
                    timestamp TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS events_session_sequence
                    ON events(session_id, sequence);

                CREATE TABLE IF NOT EXISTS mcp_servers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    transport TEXT NOT NULL,
                    command TEXT,
                    args TEXT NOT NULL,
                    url TEXT,
                    enabled INTEGER NOT NULL,
                    catalog_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    agent_context TEXT,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "organize_label" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN organize_label TEXT")
            if "last_message_at" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN last_message_at TEXT")
            if "project_id" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN project_id TEXT")
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS sessions_project_updated
                    ON sessions(project_id, updated_at DESC)
                """
            )
            mcp_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(mcp_servers)").fetchall()
            }
            if "catalog_id" not in mcp_columns:
                connection.execute("ALTER TABLE mcp_servers ADD COLUMN catalog_id TEXT")
            for column, ddl in (
                ("description", "ALTER TABLE mcp_servers ADD COLUMN description TEXT"),
                ("oauth_client_id", "ALTER TABLE mcp_servers ADD COLUMN oauth_client_id TEXT"),
                ("oauth_server_url", "ALTER TABLE mcp_servers ADD COLUMN oauth_server_url TEXT"),
                ("oauth_scopes", "ALTER TABLE mcp_servers ADD COLUMN oauth_scopes TEXT"),
                (
                    "headers_helper_command",
                    "ALTER TABLE mcp_servers ADD COLUMN headers_helper_command TEXT",
                ),
            ):
                if column not in mcp_columns:
                    connection.execute(ddl)
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS mcp_servers_catalog_id
                    ON mcp_servers(catalog_id)
                    WHERE catalog_id IS NOT NULL
                """
            )

    @staticmethod
    def _session(row: sqlite3.Row) -> AgentSession:
        keys = set(row.keys())
        return AgentSession(
            id=row["id"],
            title=row["title"],
            status=row["status"],
            organize_label=row["organize_label"],
            project_id=row["project_id"] if "project_id" in keys else None,
            workspace_path=row["workspace_path"],
            last_message_at=(
                datetime.fromisoformat(row["last_message_at"])
                if row["last_message_at"]
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _project(row: sqlite3.Row, *, session_count: int = 0) -> AgentProject:
        return AgentProject(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            agent_context=row["agent_context"],
            pinned=bool(row["pinned"]),
            session_count=session_count,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _message(row: sqlite3.Row) -> AgentMessage:
        return AgentMessage(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def create_session(
        self,
        *,
        title: str | None,
        workspace_path: str | None,
        project_id: str | None = None,
    ) -> AgentSession:
        return self.ensure_session(
            str(uuid.uuid4()),
            title=title,
            workspace_path=workspace_path,
            project_id=project_id,
        )

    def ensure_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        workspace_path: str | None = None,
        project_id: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> AgentSession:
        normalized_id = str(session_id or "").strip()
        if not normalized_id:
            raise ValueError("Session id cannot be empty.")
        existing = self.get_session(normalized_id)
        if existing is not None:
            if title is not None and title.strip() and title.strip() != existing.title:
                return self.update_session(normalized_id, title=title.strip()) or existing
            return existing

        if project_id is not None and self.get_project(project_id) is None:
            raise ValueError(f"Project not found: {project_id}")

        now = utc_now()
        created = created_at or now
        updated = updated_at or created
        session = AgentSession(
            id=normalized_id,
            title=(title or "New research session").strip() or "New research session",
            status="idle",
            organize_label=None,
            project_id=project_id,
            workspace_path=workspace_path,
            last_message_at=None,
            created_at=created,
            updated_at=updated,
        )
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(
                    id, title, status, organize_label, project_id, workspace_path,
                    last_message_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.title,
                    session.status,
                    session.organize_label,
                    session.project_id,
                    session.workspace_path,
                    None,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
        return session

    def list_sessions(self, *, project_id: str | None = None) -> list[AgentSession]:
        with self._connect() as connection:
            if project_id:
                rows = connection.execute(
                    """
                    SELECT * FROM sessions
                    WHERE project_id = ?
                    ORDER BY updated_at DESC, id DESC
                    """,
                    (project_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC, id DESC"
                ).fetchall()
        return [self._session(row) for row in rows]

    def get_session(self, session_id: str) -> AgentSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return self._session(row) if row else None

    def search_sessions(self, query: str, *, limit: int = 50) -> list[AgentSession]:
        normalized = query.strip()
        if not normalized:
            return self.list_sessions()[:limit]
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT sessions.*
                FROM sessions
                LEFT JOIN messages ON messages.session_id = sessions.id
                WHERE sessions.title LIKE ? ESCAPE '\\'
                   OR messages.content LIKE ? ESCAPE '\\'
                ORDER BY sessions.updated_at DESC, sessions.id DESC
                LIMIT ?
                """,
                (f"%{normalized}%", f"%{normalized}%", max(1, min(limit, 100))),
            ).fetchall()
        return [self._session(row) for row in rows]

    def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        organize_label: str | None = None,
        update_organize_label: bool = False,
        project_id: str | None = None,
        update_project_id: bool = False,
    ) -> AgentSession | None:
        current = self.get_session(session_id)
        if current is None:
            return None
        next_title = current.title
        if title is not None:
            next_title = title.strip()
            if not next_title:
                raise ValueError("Session title cannot be empty.")
        next_label = organize_label if update_organize_label else current.organize_label
        next_project_id = current.project_id
        if update_project_id:
            if project_id is not None and self.get_project(project_id) is None:
                raise ValueError(f"Project not found: {project_id}")
            next_project_id = project_id
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET title = ?, organize_label = ?, project_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_title, next_label, next_project_id, now.isoformat(), session_id),
            )
        return self.get_session(session_id)

    def create_project(
        self,
        *,
        name: str,
        description: str | None = None,
        agent_context: str | None = None,
        pinned: bool = False,
    ) -> AgentProject:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Project name cannot be empty.")
        now = utc_now()
        project_id = str(uuid.uuid4())
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO projects(
                    id, name, description, agent_context, pinned, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    normalized,
                    (description or "").strip() or None,
                    (agent_context or "").strip() or None,
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
            self._project(row, session_count=int(row["session_count"] or 0))
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
        return self._project(row, session_count=int(row["session_count"] or 0))

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        update_description: bool = False,
        agent_context: str | None = None,
        update_agent_context: bool = False,
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
        next_pinned = current.pinned if pinned is None else bool(pinned)
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE projects
                SET name = ?, description = ?, agent_context = ?, pinned = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_name,
                    next_description,
                    next_context,
                    1 if next_pinned else 0,
                    now.isoformat(),
                    project_id,
                ),
            )
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET project_id = NULL WHERE project_id = ?",
                (project_id,),
            )
            cursor = connection.execute(
                "DELETE FROM projects WHERE id = ?", (project_id,)
            )
        return cursor.rowcount > 0

    def set_workspace_path(self, session_id: str, workspace_path: str) -> AgentSession | None:
        with self._write_lock, self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET workspace_path = ?, updated_at = ? WHERE id = ?",
                (workspace_path, utc_now().isoformat(), session_id),
            )
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0

    def set_session_status(self, session_id: str, status: SessionStatus) -> AgentSession | None:
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
                (status, now.isoformat(), session_id),
            )
        return self.get_session(session_id)

    def add_message(
        self,
        *,
        session_id: str,
        role: MessageRole,
        content: str,
        created_at: datetime | None = None,
        message_id: str | None = None,
    ) -> AgentMessage:
        timestamp = created_at or utc_now()
        message = AgentMessage(
            id=message_id or str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            created_at=timestamp,
        )
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO messages(id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.session_id,
                    message.role,
                    message.content,
                    message.created_at.isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE sessions
                SET updated_at = ?, last_message_at = ?
                WHERE id = ?
                """,
                (message.created_at.isoformat(), message.created_at.isoformat(), session_id),
            )
        return message

    def clear_messages(self, session_id: str) -> int:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (session_id,),
            )
            connection.execute(
                "UPDATE sessions SET last_message_at = NULL, updated_at = ? WHERE id = ?",
                (utc_now().isoformat(), session_id),
            )
        return int(cursor.rowcount)

    def list_messages(self, session_id: str) -> list[AgentMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
        return [self._message(row) for row in rows]

    def set_message_feedback(
        self,
        message_id: str,
        reaction: str | None,
    ) -> bool:
        with self._write_lock, self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if not exists:
                return False
            if reaction is None:
                connection.execute(
                    "DELETE FROM message_feedback WHERE message_id = ?",
                    (message_id,),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO message_feedback(message_id, reaction, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(message_id) DO UPDATE SET
                        reaction = excluded.reaction,
                        updated_at = excluded.updated_at
                    """,
                    (message_id, reaction, utc_now().isoformat()),
                )
        return True

    def get_session_feedback(self, session_id: str) -> dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT message_feedback.message_id, message_feedback.reaction
                FROM message_feedback
                JOIN messages ON messages.id = message_feedback.message_id
                WHERE messages.session_id = ?
                """,
                (session_id,),
            ).fetchall()
        return {str(row["message_id"]): str(row["reaction"]) for row in rows}

    def append_event(
        self,
        *,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        run_id: str | None = None,
    ) -> EventEnvelope:
        event_id = str(uuid.uuid4())
        timestamp = utc_now()
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO events(id, session_id, run_id, timestamp, type, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    session_id,
                    run_id,
                    timestamp.isoformat(),
                    event_type,
                    json.dumps(payload, separators=(",", ":"), default=str),
                ),
            )
            sequence = int(cursor.lastrowid)
        return EventEnvelope(
            id=event_id,
            session_id=session_id,
            run_id=run_id,
            sequence=sequence,
            timestamp=timestamp,
            type=event_type,
            payload=payload,
        )

    def list_events(self, session_id: str, *, after_sequence: int = 0) -> list[EventEnvelope]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM events
                WHERE session_id = ? AND sequence > ?
                ORDER BY sequence ASC
                """,
                (session_id, after_sequence),
            ).fetchall()
        return [
            EventEnvelope(
                id=row["id"],
                session_id=row["session_id"],
                run_id=row["run_id"],
                sequence=row["sequence"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                type=row["type"],
                payload=json.loads(row["payload"]),
            )
            for row in rows
        ]

    @staticmethod
    def _mcp_server(row: sqlite3.Row) -> McpServer:
        keys = set(row.keys())
        return McpServer(
            id=row["id"],
            name=row["name"],
            transport=row["transport"],
            command=row["command"],
            args=json.loads(row["args"]),
            url=row["url"],
            enabled=bool(row["enabled"]),
            catalog_id=row["catalog_id"] if "catalog_id" in keys else None,
            description=row["description"] if "description" in keys else None,
            oauth_client_id=row["oauth_client_id"] if "oauth_client_id" in keys else None,
            oauth_server_url=row["oauth_server_url"] if "oauth_server_url" in keys else None,
            oauth_scopes=row["oauth_scopes"] if "oauth_scopes" in keys else None,
            headers_helper_command=(
                row["headers_helper_command"] if "headers_helper_command" in keys else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_mcp_servers(self, *, enabled_only: bool = False) -> list[McpServer]:
        query = "SELECT * FROM mcp_servers"
        params: tuple = ()
        if enabled_only:
            query += " WHERE enabled = ?"
            params = (1,)
        query += " ORDER BY name COLLATE NOCASE, id"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._mcp_server(row) for row in rows]

    def create_mcp_server(
        self,
        *,
        name: str,
        transport: str,
        command: str | None,
        args: list[str],
        url: str | None,
        enabled: bool,
        catalog_id: str | None = None,
        description: str | None = None,
        oauth_client_id: str | None = None,
        oauth_server_url: str | None = None,
        oauth_scopes: str | None = None,
        headers_helper_command: str | None = None,
    ) -> McpServer:
        now = utc_now()
        server = McpServer(
            id=str(uuid.uuid4()),
            name=name.strip(),
            transport=transport,
            command=command.strip() if command else None,
            args=args,
            url=url.strip() if url else None,
            enabled=enabled,
            catalog_id=catalog_id.strip() if catalog_id else None,
            description=description.strip() if description else None,
            oauth_client_id=oauth_client_id.strip() if oauth_client_id else None,
            oauth_server_url=oauth_server_url.strip() if oauth_server_url else None,
            oauth_scopes=oauth_scopes.strip() if oauth_scopes else None,
            headers_helper_command=(
                headers_helper_command.strip() if headers_helper_command else None
            ),
            created_at=now,
            updated_at=now,
        )
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO mcp_servers(
                    id, name, transport, command, args, url, enabled, catalog_id,
                    description, oauth_client_id, oauth_server_url, oauth_scopes,
                    headers_helper_command, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    server.id,
                    server.name,
                    server.transport,
                    server.command,
                    json.dumps(server.args),
                    server.url,
                    int(server.enabled),
                    server.catalog_id,
                    server.description,
                    server.oauth_client_id,
                    server.oauth_server_url,
                    server.oauth_scopes,
                    server.headers_helper_command,
                    server.created_at.isoformat(),
                    server.updated_at.isoformat(),
                ),
            )
        return server

    def update_mcp_server(self, server_id: str, **changes) -> McpServer | None:
        current = next(
            (server for server in self.list_mcp_servers() if server.id == server_id),
            None,
        )
        if current is None:
            return None
        data = current.model_dump()
        for key, value in changes.items():
            if key in data:
                data[key] = value
        data["updated_at"] = utc_now()
        # Response-only fields — never persist from callers.
        data.pop("header_names", None)
        data.pop("headers_configured", None)
        server = McpServer(**data)
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE mcp_servers
                SET name = ?, command = ?, args = ?, url = ?, enabled = ?,
                    catalog_id = ?, description = ?, oauth_client_id = ?,
                    oauth_server_url = ?, oauth_scopes = ?,
                    headers_helper_command = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    server.name,
                    server.command,
                    json.dumps(server.args),
                    server.url,
                    int(server.enabled),
                    server.catalog_id,
                    server.description,
                    server.oauth_client_id,
                    server.oauth_server_url,
                    server.oauth_scopes,
                    server.headers_helper_command,
                    server.updated_at.isoformat(),
                    server.id,
                ),
            )
        return server

    def delete_mcp_server(self, server_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM mcp_servers WHERE id = ?", (server_id,))
        return cursor.rowcount > 0
