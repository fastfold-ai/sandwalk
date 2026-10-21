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

        -- FAS-107: Terminal as a first-class item peer to Chat.
        -- Precedent: VSCode's TabInputText | TabInputTerminal split, Zellij's
        -- PaneId::Terminal | PaneId::Plugin. Terminals get their own table
        -- (Chat-shaped columns like provider/model/tokens are meaningless
        -- for a shell); the tab strip / sidebar / splits query the unified
        -- workspace_items index instead of UNIONing across kinds.
        CREATE TABLE IF NOT EXISTS terminal_sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            title_source TEXT NOT NULL DEFAULT 'pending',
            project_id TEXT,
            workspace_path TEXT,
            shell TEXT,
            origin_chat_id TEXT,
            slot_key TEXT,
            status TEXT NOT NULL DEFAULT 'idle',
            organize_label TEXT,
            last_activity_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS terminal_sessions_project_updated
            ON terminal_sessions(project_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS terminal_sessions_slot_key
            ON terminal_sessions(slot_key)
            WHERE slot_key IS NOT NULL;

        -- Denormalized index over "everything that can appear in a tab or
        -- split". One row per underlying entity (chat or terminal today,
        -- files/preview/structure later). Columns are exactly what the tab
        -- strip sorts and filters by, so a single indexed query serves the
        -- strip without UNIONing across kinds.
        CREATE TABLE IF NOT EXISTS workspace_items (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            project_id TEXT,
            organize_label TEXT,
            title TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS workspace_items_project_updated
            ON workspace_items(project_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS workspace_items_kind_updated
            ON workspace_items(kind, updated_at DESC);

        -- Ring-buffer scrollback for terminals across app restarts.
        -- Bounded at write-time (last ~256 KB per PTY); reader replays the
        -- current blob on WebSocket attach. Precedent: iTerm2 Instant
        -- Replay narrowed to scrollback, WezTerm mux buffer.
        CREATE TABLE IF NOT EXISTS pty_scrollback (
            id TEXT PRIMARY KEY REFERENCES terminal_sessions(id) ON DELETE CASCADE,
            ring BLOB NOT NULL,
            updated_at TEXT NOT NULL
        );
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
    # Per-chat model selection (global llm.* only seeds new sessions).
    if "provider" not in columns:
        connection.execute("ALTER TABLE sessions ADD COLUMN provider TEXT")
    if "model" not in columns:
        connection.execute("ALTER TABLE sessions ADD COLUMN model TEXT")
    if "openai_profile_id" not in columns:
        connection.execute("ALTER TABLE sessions ADD COLUMN openai_profile_id TEXT")
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
    if "home_layout" not in project_columns:
        connection.execute("ALTER TABLE projects ADD COLUMN home_layout TEXT")

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
    if "project_id" not in usage_columns:
        connection.execute("ALTER TABLE usage_runs ADD COLUMN project_id TEXT")
    if "kind" not in usage_columns:
        connection.execute(
            "ALTER TABLE usage_runs ADD COLUMN kind TEXT NOT NULL DEFAULT 'chat'"
        )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS usage_runs_project ON usage_runs(project_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS usage_runs_kind_day ON usage_runs(kind, day)"
    )
    # FAS-107 pin/archive for terminals: adds `organize_label` on existing
    # DBs that were created before the paridad-con-chat pass. Idempotent.
    terminal_columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(terminal_sessions)"
        ).fetchall()
    }
    if "organize_label" not in terminal_columns:
        connection.execute(
            "ALTER TABLE terminal_sessions ADD COLUMN organize_label TEXT"
        )

    # FAS-107 backfill: mirror every existing chat session into workspace_items
    # so the tab strip / sidebar can query the unified index without a UNION.
    # Idempotent — INSERT OR IGNORE keeps existing rows untouched, and the
    # UPDATE keeps the denormalized copy in sync on subsequent boots.
    connection.execute(
        """
        INSERT OR IGNORE INTO workspace_items(
            id, kind, project_id, organize_label, title, updated_at
        )
        SELECT id, 'chat', project_id, organize_label, title, updated_at
        FROM sessions
        """
    )
    connection.execute(
        """
        UPDATE workspace_items
        SET project_id = sessions.project_id,
            organize_label = sessions.organize_label,
            title = sessions.title,
            updated_at = sessions.updated_at
        FROM sessions
        WHERE workspace_items.kind = 'chat'
          AND workspace_items.id = sessions.id
          AND (
               workspace_items.project_id IS NOT sessions.project_id
            OR workspace_items.organize_label IS NOT sessions.organize_label
            OR workspace_items.title != sessions.title
            OR workspace_items.updated_at != sessions.updated_at
          )
        """
    )

    session_col = next(
        (
            row
            for row in connection.execute("PRAGMA table_info(usage_runs)").fetchall()
            if row["name"] == "session_id"
        ),
        None,
    )
    if session_col is not None and int(session_col["notnull"] or 0):
        connection.executescript(
            """
            CREATE TABLE usage_runs_v2 (
                run_id TEXT PRIMARY KEY,
                session_id TEXT,
                day TEXT NOT NULL,
                surface TEXT NOT NULL DEFAULT 'unknown',
                model_id TEXT,
                provider TEXT,
                project_id TEXT,
                kind TEXT NOT NULL DEFAULT 'chat',
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cache_read_tokens INTEGER NOT NULL DEFAULT 0,
                cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            INSERT INTO usage_runs_v2(
                run_id, session_id, day, surface, model_id, provider,
                project_id, kind, input_tokens, output_tokens,
                cache_read_tokens, cache_creation_tokens, updated_at
            )
            SELECT
                run_id, session_id, day, surface, model_id, provider,
                project_id, COALESCE(kind, 'chat'), input_tokens,
                output_tokens, cache_read_tokens, cache_creation_tokens,
                updated_at
            FROM usage_runs;
            DROP TABLE usage_runs;
            ALTER TABLE usage_runs_v2 RENAME TO usage_runs;
            CREATE INDEX IF NOT EXISTS usage_runs_day ON usage_runs(day);
            CREATE INDEX IF NOT EXISTS usage_runs_surface_day
                ON usage_runs(surface, day);
            CREATE INDEX IF NOT EXISTS usage_runs_model_day
                ON usage_runs(model_id, day);
            CREATE INDEX IF NOT EXISTS usage_runs_project ON usage_runs(project_id);
            CREATE INDEX IF NOT EXISTS usage_runs_kind_day ON usage_runs(kind, day);
            """
        )

    session_columns_latest = {
        row["name"] for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
    }
    if "snoozed" not in session_columns_latest:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN snoozed INTEGER NOT NULL DEFAULT 0"
        )
    if "automation_id" not in session_columns_latest:
        connection.execute("ALTER TABLE sessions ADD COLUMN automation_id TEXT")

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS automations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            prompt TEXT NOT NULL DEFAULT '',
            command TEXT,
            schedule_expr TEXT NOT NULL DEFAULT 'every 1h',
            schedule_kind TEXT NOT NULL DEFAULT 'interval',
            schedule_label TEXT NOT NULL DEFAULT 'Every hour',
            session_mode TEXT NOT NULL DEFAULT 'fresh',
            origin_session_id TEXT,
            specialist_id TEXT,
            project_id TEXT,
            workdir TEXT,
            ssh_host_id TEXT,
            remote_workdir TEXT,
            skill_names TEXT NOT NULL DEFAULT '[]',
            tool_names TEXT NOT NULL DEFAULT '[]',
            mcp_server_ids TEXT NOT NULL DEFAULT '[]',
            provider_pin TEXT,
            model_pin TEXT,
            continuity INTEGER NOT NULL DEFAULT 0,
            context_from TEXT NOT NULL DEFAULT '[]',
            wake_on_change_only INTEGER NOT NULL DEFAULT 0,
            repeat_limit INTEGER,
            run_count INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            next_run_at TEXT,
            last_run_at TEXT,
            last_status TEXT NOT NULL DEFAULT 'idle',
            last_error TEXT,
            webhook_token TEXT,
            template_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS automations_enabled_next
            ON automations(enabled, next_run_at);

        CREATE TABLE IF NOT EXISTS automation_runs (
            id TEXT PRIMARY KEY,
            automation_id TEXT NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
            session_id TEXT,
            status TEXT NOT NULL DEFAULT 'running',
            trigger_source TEXT NOT NULL DEFAULT 'schedule',
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_seconds REAL,
            output_excerpt TEXT,
            output_path TEXT,
            error TEXT,
            was_catchup INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS automation_runs_automation_started
            ON automation_runs(automation_id, started_at DESC);

        CREATE TABLE IF NOT EXISTS ssh_hosts (
            id TEXT PRIMARY KEY,
            alias TEXT NOT NULL,
            host TEXT NOT NULL,
            user TEXT,
            port INTEGER NOT NULL DEFAULT 22,
            identity_file TEXT,
            proxy_jump TEXT,
            remote_port INTEGER NOT NULL DEFAULT 8787,
            default_workdir TEXT,
            status TEXT NOT NULL DEFAULT 'unknown',
            platform TEXT,
            arch TEXT,
            hostname TEXT,
            gpu_summary TEXT,
            slurm_available INTEGER NOT NULL DEFAULT 0,
            sandwalk_installed INTEGER NOT NULL DEFAULT 0,
            sandwalk_version TEXT,
            daemon_running INTEGER NOT NULL DEFAULT 0,
            tunnel_local_port INTEGER,
            tunnel_url TEXT,
            last_connected_at TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

