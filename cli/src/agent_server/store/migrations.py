"""Additive column/index migrations layered on top of :mod:`schema`.

Every migration is idempotent (checked against ``PRAGMA table_info``/``CREATE
INDEX IF NOT EXISTS``) so it is safe to call on every store open.
"""

from __future__ import annotations

import sqlite3


def apply_migrations(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS sites (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source_path TEXT NOT NULL,
            origin_session_id TEXT,
            origin_project_id TEXT,
            storage_path TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            file_count INTEGER NOT NULL,
            bytes INTEGER NOT NULL,
            cloud_site_id TEXT,
            cloud_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            published_at TEXT
        );
        CREATE INDEX IF NOT EXISTS sites_updated
            ON sites(updated_at DESC, id DESC);
        """
    )
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(sessions)").fetchall()}
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
    # Connector-spawned sessions (e.g. a Slack mention) carry their origin so the
    # UI can badge them; NULL means the session started locally.
    if "source" not in columns:
        connection.execute("ALTER TABLE sessions ADD COLUMN source TEXT")
    if "source_label" not in columns:
        connection.execute("ALTER TABLE sessions ADD COLUMN source_label TEXT")
    # Product surface for Overview usage (cli / ui / slack / unknown).
    if "client_surface" not in columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN client_surface TEXT NOT NULL DEFAULT 'unknown'"
        )
        # Slack-originated sessions are already tagged via `source`.
        connection.execute(
            """
            UPDATE sessions
            SET client_surface = 'slack'
            WHERE lower(coalesce(source, '')) = 'slack'
            """
        )
    if "title_source" not in columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN title_source TEXT NOT NULL DEFAULT 'pending'"
        )
        # One-time backfill: only known placeholders stay eligible for auto-title.
        placeholders = (
            "untitled",
            "untitled session",
            "untitled thread",
            "new chat",
            "new agent",
            "new agent session",
            "new research session",
        )
        placeholders_sql = ", ".join("?" for _ in placeholders)
        connection.execute(
            f"""
            UPDATE sessions
            SET title_source = 'user'
            WHERE lower(trim(title)) NOT IN ({placeholders_sql})
            """,
            placeholders,
        )

    # Desktop used to create sessions as "Untitled session", which
    # initial_title_source incorrectly marked as user and blocked auto-title.
    # Re-open auto-title for any remaining placeholder titles stuck as user.
    placeholders = (
        "untitled",
        "untitled session",
        "untitled thread",
        "new chat",
        "new agent",
        "new agent session",
        "new research session",
    )
    placeholders_sql = ", ".join("?" for _ in placeholders)
    connection.execute(
        f"""
        UPDATE sessions
        SET title_source = 'pending'
        WHERE title_source = 'user'
          AND lower(trim(title)) IN ({placeholders_sql})
        """,
        placeholders,
    )

    message_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(messages)").fetchall()
    }
    # Display-only sidecar (e.g. which Slack channel a message came from). The
    # model-facing text stays in `content`.
    if "metadata" not in message_columns:
        connection.execute("ALTER TABLE messages ADD COLUMN metadata TEXT")

    specialist_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(specialists)").fetchall()
    }
    if "mcp_catalog_ids" not in specialist_columns:
        connection.execute(
            "ALTER TABLE specialists ADD COLUMN mcp_catalog_ids TEXT NOT NULL DEFAULT '[]'"
        )
    if "tool_names" not in specialist_columns:
        connection.execute(
            "ALTER TABLE specialists ADD COLUMN tool_names TEXT NOT NULL DEFAULT '[]'"
        )
    if "enabled" not in specialist_columns:
        connection.execute("ALTER TABLE specialists ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")

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
        row["name"] for row in connection.execute("PRAGMA table_info(mcp_servers)").fetchall()
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

    slack_workspace_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(slack_workspaces)").fetchall()
    }
    if "needs_reauth" not in slack_workspace_columns:
        connection.execute(
            "ALTER TABLE slack_workspaces ADD COLUMN needs_reauth INTEGER NOT NULL DEFAULT 0"
        )

    project_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(projects)").fetchall()
    }
    if "folder_path" not in project_columns:
        connection.execute("ALTER TABLE projects ADD COLUMN folder_path TEXT")
    if "icon" not in project_columns:
        connection.execute(
            "ALTER TABLE projects ADD COLUMN icon TEXT NOT NULL DEFAULT 'folder'"
        )
    if "color" not in project_columns:
        connection.execute(
            "ALTER TABLE projects ADD COLUMN color TEXT NOT NULL DEFAULT 'neutral'"
        )

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS usage_runs (
            run_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            day TEXT NOT NULL,
            surface TEXT NOT NULL DEFAULT 'unknown',
            model_id TEXT,
            provider TEXT,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cache_read_tokens INTEGER NOT NULL DEFAULT 0,
            cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS usage_runs_day ON usage_runs(day);
        CREATE INDEX IF NOT EXISTS usage_runs_surface_day
            ON usage_runs(surface, day);
        CREATE INDEX IF NOT EXISTS usage_runs_model_day
            ON usage_runs(model_id, day);
        CREATE TABLE IF NOT EXISTS usage_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    usage_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(usage_runs)").fetchall()
    }
    if "provider" not in usage_columns:
        connection.execute("ALTER TABLE usage_runs ADD COLUMN provider TEXT")
