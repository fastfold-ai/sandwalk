"""SQLite persistence for sessions, messages, and replayable events."""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import subprocess
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
    Specialist,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


class AgentStore:
    """Small durable store shared by CLI and web transports."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or (CONFIG_DIR / "agent-server.db")).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        self._ensure_healthy_database()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        # NORMAL is durable enough with WAL and much less likely to leave a
        # torn page if the process is force-killed mid-write than OFF.
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _ensure_healthy_database(self) -> None:
        """Repair a malformed DB so serve does not crash-loop on startup."""
        if not self.path.exists():
            return
        try:
            with sqlite3.connect(self.path, timeout=5) as connection:
                row = connection.execute("PRAGMA integrity_check").fetchone()
                if row and str(row[0]) == "ok":
                    return
                detail = str(row[0]) if row else "integrity_check failed"
        except sqlite3.DatabaseError as exc:
            detail = str(exc)
        self._repair_database(reason=detail)

    def _sidecar(self, base: Path, suffix: str) -> Path:
        return Path(f"{base}{suffix}")

    def _quarantine_database(self, *, stamp: str) -> Path:
        backup = self.path.with_name(f"{self.path.name}.corrupt-{stamp}")
        for suffix in ("", "-wal", "-shm"):
            src = self._sidecar(self.path, suffix)
            if not src.exists():
                continue
            dest = self._sidecar(backup, suffix)
            try:
                if dest.exists():
                    dest.unlink()
                shutil.move(str(src), str(dest))
            except OSError as exc:
                logger.warning("Failed to quarantine %s: %s", src, exc)
        return backup

    def _integrity_ok(self, path: Path) -> bool:
        try:
            with sqlite3.connect(path, timeout=5) as connection:
                row = connection.execute("PRAGMA integrity_check").fetchone()
                return bool(row and str(row[0]) == "ok")
        except sqlite3.DatabaseError:
            return False

    def _repair_database(self, *, reason: str) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup = self._quarantine_database(stamp=stamp)
        logger.error(
            "Agent store database is corrupt (%s); quarantined to %s and recovering",
            reason,
            backup,
        )

        # Prefer a previously recovered sibling when present.
        sibling = Path(f"{self.path}.recovered")
        if sibling.exists() and self._integrity_ok(sibling):
            try:
                shutil.copy2(sibling, self.path)
                if self._integrity_ok(self.path):
                    logger.error("Restored agent store from %s", sibling)
                    return
            except OSError as exc:
                logger.warning("Failed to restore %s: %s", sibling, exc)

        # sqlite3 .recover dumps a rebuild script (best-effort).
        try:
            recover_sql = subprocess.check_output(
                ["sqlite3", str(backup), ".recover"],
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
            if self.path.exists():
                self.path.unlink()
            with sqlite3.connect(self.path) as connection:
                connection.executescript(recover_sql)
            if self._integrity_ok(self.path):
                try:
                    shutil.copy2(self.path, sibling)
                except OSError:
                    pass
                logger.error("Recovered agent store via sqlite3 .recover")
                return
        except (OSError, subprocess.SubprocessError, sqlite3.Error) as exc:
            logger.warning("sqlite3 .recover failed: %s", exc)

        # Last resort: empty DB so the API can boot (schema created in _initialize).
        for suffix in ("", "-wal", "-shm"):
            path = self._sidecar(self.path, suffix)
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
        logger.error(
            "Could not recover agent store data; starting with a fresh database "
            "(corrupt backup kept at %s)",
            backup,
        )

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

                CREATE TABLE IF NOT EXISTS specialists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    description TEXT,
                    instructions TEXT,
                    color TEXT NOT NULL,
                    icon TEXT NOT NULL,
                    skill_names TEXT NOT NULL,
                    mcp_server_ids TEXT NOT NULL,
                    mcp_catalog_ids TEXT NOT NULL DEFAULT '[]',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS store_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
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
            if "specialist_id" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN specialist_id TEXT")
            if "sandbox_backend" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN sandbox_backend TEXT")
            specialist_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(specialists)").fetchall()
            }
            if "mcp_catalog_ids" not in specialist_columns:
                connection.execute(
                    "ALTER TABLE specialists ADD COLUMN mcp_catalog_ids TEXT NOT NULL DEFAULT '[]'"
                )
            if "enabled" not in specialist_columns:
                connection.execute(
                    "ALTER TABLE specialists ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
                )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS sessions_project_updated
                    ON sessions(project_id, updated_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS sessions_specialist_updated
                    ON sessions(specialist_id, updated_at DESC)
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

        from agent_server.default_specialists import ensure_default_specialists

        ensure_default_specialists(self)

    def get_meta(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM store_meta WHERE key = ?",
                (key,),
            ).fetchone()
        return str(row["value"]) if row is not None else None

    def set_meta(self, key: str, value: str) -> None:
        with self._write_lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO store_meta(key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )

    @staticmethod
    def _session(row: sqlite3.Row) -> AgentSession:
        keys = set(row.keys())
        raw_backend = row["sandbox_backend"] if "sandbox_backend" in keys else None
        sandbox_backend = None
        if raw_backend is not None:
            normalized = str(raw_backend).strip().lower()
            if normalized in {"builtin", "modal"}:
                sandbox_backend = normalized
        return AgentSession(
            id=row["id"],
            title=row["title"],
            status=row["status"],
            organize_label=row["organize_label"],
            project_id=row["project_id"] if "project_id" in keys else None,
            specialist_id=row["specialist_id"] if "specialist_id" in keys else None,
            sandbox_backend=sandbox_backend,
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
    def _specialist(row: sqlite3.Row) -> Specialist:
        def _json_list(raw: Any) -> list[str]:
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                return []
            if not isinstance(parsed, list):
                return []
            return [str(item).strip() for item in parsed if str(item).strip()]

        keys = set(row.keys())
        return Specialist(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            description=row["description"],
            instructions=row["instructions"],
            color=row["color"] or "ink",
            icon=row["icon"] or "agent",
            skill_names=_json_list(row["skill_names"]),
            mcp_server_ids=_json_list(row["mcp_server_ids"]),
            mcp_catalog_ids=_json_list(
                row["mcp_catalog_ids"] if "mcp_catalog_ids" in keys else "[]"
            ),
            enabled=bool(row["enabled"]) if "enabled" in keys else True,
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
        specialist_id: str | None = None,
        sandbox_backend: str | None = None,
    ) -> AgentSession:
        return self.ensure_session(
            str(uuid.uuid4()),
            title=title,
            workspace_path=workspace_path,
            project_id=project_id,
            specialist_id=specialist_id,
            sandbox_backend=sandbox_backend,
        )

    def ensure_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        workspace_path: str | None = None,
        project_id: str | None = None,
        specialist_id: str | None = None,
        sandbox_backend: str | None = None,
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
        if specialist_id is not None and self.get_specialist(specialist_id) is None:
            raise ValueError(f"Specialist not found: {specialist_id}")
        normalized_backend = None
        if sandbox_backend is not None:
            candidate = str(sandbox_backend).strip().lower()
            if candidate not in {"builtin", "modal"}:
                raise ValueError("sandbox_backend must be 'builtin' or 'modal'")
            normalized_backend = candidate

        now = utc_now()
        created = created_at or now
        updated = updated_at or created
        session = AgentSession(
            id=normalized_id,
            title=(title or "New research session").strip() or "New research session",
            status="idle",
            organize_label=None,
            project_id=project_id,
            specialist_id=specialist_id,
            sandbox_backend=normalized_backend,
            workspace_path=workspace_path,
            last_message_at=None,
            created_at=created,
            updated_at=updated,
        )
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(
                    id, title, status, organize_label, project_id, specialist_id,
                    sandbox_backend, workspace_path, last_message_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.title,
                    session.status,
                    session.organize_label,
                    session.project_id,
                    session.specialist_id,
                    session.sandbox_backend,
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
        specialist_id: str | None = None,
        update_specialist_id: bool = False,
        sandbox_backend: str | None = None,
        update_sandbox_backend: bool = False,
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
        next_specialist_id = current.specialist_id
        if update_specialist_id:
            if specialist_id is not None and self.get_specialist(specialist_id) is None:
                raise ValueError(f"Specialist not found: {specialist_id}")
            next_specialist_id = specialist_id
        next_sandbox_backend = current.sandbox_backend
        if update_sandbox_backend:
            if sandbox_backend is not None:
                candidate = str(sandbox_backend).strip().lower()
                if candidate not in {"builtin", "modal"}:
                    raise ValueError("sandbox_backend must be 'builtin' or 'modal'")
                next_sandbox_backend = candidate
            else:
                next_sandbox_backend = None
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET title = ?, organize_label = ?, project_id = ?, specialist_id = ?,
                    sandbox_backend = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_title,
                    next_label,
                    next_project_id,
                    next_specialist_id,
                    next_sandbox_backend,
                    now.isoformat(),
                    session_id,
                ),
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

    @staticmethod
    def _slugify(value: str) -> str:
        import re

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
                    skill_names, mcp_server_ids, mcp_catalog_ids, enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        return [self._specialist(row) for row in rows]

    def get_specialist(self, specialist_id: str) -> Specialist | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM specialists WHERE id = ?", (specialist_id,)
            ).fetchone()
        return self._specialist(row) if row else None

    def get_specialist_by_slug(self, slug: str) -> Specialist | None:
        key = self._slugify(slug)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM specialists WHERE slug = ?", (key,)
            ).fetchone()
        return self._specialist(row) if row else None

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
                    color = ?, icon = ?, skill_names = ?, mcp_server_ids = ?,
                    mcp_catalog_ids = ?, enabled = ?, updated_at = ?
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
            sequence = int(cursor.lastrowid or 0)
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
        params: tuple[Any, ...] = ()
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
        from typing import Literal, cast

        now = utc_now()
        transport_lit = cast(Literal["stdio", "sse", "streamable_http"], transport)
        server = McpServer(
            id=str(uuid.uuid4()),
            name=name.strip(),
            transport=transport_lit,
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

    def update_mcp_server(self, server_id: str, **changes: Any) -> McpServer | None:
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
