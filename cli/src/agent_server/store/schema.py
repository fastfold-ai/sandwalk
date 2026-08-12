"""Base table/index DDL for the agent store SQLite database."""

from __future__ import annotations

import sqlite3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    title_source TEXT NOT NULL DEFAULT 'pending',
    status TEXT NOT NULL,
    organize_label TEXT,
    workspace_path TEXT,
    client_surface TEXT NOT NULL DEFAULT 'unknown',
    last_message_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
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
    folder_path TEXT,
    icon TEXT NOT NULL DEFAULT 'folder',
    color TEXT NOT NULL DEFAULT 'neutral',
    pinned INTEGER NOT NULL DEFAULT 0,
    home_layout TEXT,
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
    tool_names TEXT NOT NULL DEFAULT '[]',
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

CREATE TABLE IF NOT EXISTS library_items (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    bytes INTEGER NOT NULL,
    mime TEXT,
    original_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    origin_session_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS library_items_updated
    ON library_items(updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS library_items_kind_updated
    ON library_items(kind, updated_at DESC);

CREATE INDEX IF NOT EXISTS library_items_sha256
    ON library_items(sha256);

CREATE TABLE IF NOT EXISTS library_item_sessions (
    item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    PRIMARY KEY (item_id, session_id)
);

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

CREATE TABLE IF NOT EXISTS slack_workspaces (
    team_id TEXT PRIMARY KEY,
    team_name TEXT,
    domain TEXT,
    mode TEXT NOT NULL,
    bot_token TEXT,
    app_token TEXT,
    bot_user_id TEXT,
    connection_id TEXT,
    assistant_enabled INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    -- Set when an outbound Slack call fails with an auth error (e.g. the bot
    -- token was rotated by a reinstall) — the UI turns this into a prominent
    -- "reconnect" prompt instead of a generic connectivity error.
    needs_reauth INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS slack_allowed_users (
    team_id TEXT NOT NULL REFERENCES slack_workspaces(team_id) ON DELETE CASCADE,
    slack_user_id TEXT NOT NULL,
    display_name TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (team_id, slack_user_id)
);

CREATE TABLE IF NOT EXISTS slack_subscriptions (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, channel)
);

CREATE INDEX IF NOT EXISTS slack_subscriptions_channel
    ON slack_subscriptions(channel);

CREATE TABLE IF NOT EXISTS slack_mention_threads (
    thread_target TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS slack_mention_threads_session
    ON slack_mention_threads(session_id);

CREATE TABLE IF NOT EXISTS slack_parked_messages (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    thread_target TEXT,
    slack_user_id TEXT NOT NULL,
    user_name TEXT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS slack_parked_messages_created
    ON slack_parked_messages(created_at DESC);

CREATE TABLE IF NOT EXISTS session_connector_mutes (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    connector TEXT NOT NULL,
    muted INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (session_id, connector)
);

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
CREATE INDEX IF NOT EXISTS usage_runs_surface_day ON usage_runs(surface, day);
CREATE INDEX IF NOT EXISTS usage_runs_model_day ON usage_runs(model_id, day);

CREATE TABLE IF NOT EXISTS usage_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
