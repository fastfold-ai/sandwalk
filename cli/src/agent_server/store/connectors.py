"""Slack connector state in the agent SQLite store.

Holds routing policy that must never leave the machine: which workspaces are
connected, who is allowed to trigger the agent, which sessions listen to which
channels, and which mention threads map to which sessions.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from agent_server.models.connectors import (
    SlackAllowedUser,
    SlackMode,
    SlackParkedMessage,
    SlackSubscription,
    SlackWorkspace,
)
from agent_server.store.util import utc_now


def slack_workspace_from_row(row: sqlite3.Row) -> SlackWorkspace:
    return SlackWorkspace(
        team_id=str(row["team_id"]),
        team_name=row["team_name"],
        domain=row["domain"],
        mode=str(row["mode"]),  # type: ignore[arg-type]
        bot_user_id=row["bot_user_id"],
        connection_id=row["connection_id"],
        assistant_enabled=bool(row["assistant_enabled"]),
        enabled=bool(row["enabled"]),
        has_bot_token=bool(row["bot_token"]),
        has_app_token=bool(row["app_token"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


class ConnectorMixin:
    # --- workspaces -----------------------------------------------------

    def upsert_slack_workspace(
        self,
        *,
        team_id: str,
        mode: SlackMode,
        team_name: str | None = None,
        domain: str | None = None,
        bot_token: str | None = None,
        app_token: str | None = None,
        bot_user_id: str | None = None,
        connection_id: str | None = None,
    ) -> SlackWorkspace:
        normalized = str(team_id or "").strip()
        if not normalized:
            raise ValueError("team_id cannot be empty.")
        if mode not in ("relay", "socket"):
            raise ValueError("mode must be 'relay' or 'socket'")
        now = utc_now().isoformat()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO slack_workspaces(
                    team_id, team_name, domain, mode, bot_token, app_token,
                    bot_user_id, connection_id, assistant_enabled, enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?)
                ON CONFLICT(team_id) DO UPDATE SET
                    team_name = COALESCE(excluded.team_name, slack_workspaces.team_name),
                    domain = COALESCE(excluded.domain, slack_workspaces.domain),
                    mode = excluded.mode,
                    bot_token = COALESCE(excluded.bot_token, slack_workspaces.bot_token),
                    app_token = COALESCE(excluded.app_token, slack_workspaces.app_token),
                    bot_user_id = COALESCE(
                        excluded.bot_user_id, slack_workspaces.bot_user_id
                    ),
                    connection_id = COALESCE(
                        excluded.connection_id, slack_workspaces.connection_id
                    ),
                    updated_at = excluded.updated_at
                """,
                (
                    normalized,
                    team_name,
                    domain,
                    mode,
                    bot_token,
                    app_token,
                    bot_user_id,
                    connection_id,
                    now,
                    now,
                ),
            )
        workspace = self.get_slack_workspace(normalized)
        if workspace is None:
            raise RuntimeError("Failed to upsert Slack workspace.")
        return workspace

    def get_slack_workspace(self, team_id: str) -> SlackWorkspace | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM slack_workspaces WHERE team_id = ?",
                (team_id,),
            ).fetchone()
        return slack_workspace_from_row(row) if row else None

    def list_slack_workspaces(self) -> list[SlackWorkspace]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM slack_workspaces ORDER BY created_at ASC, team_id ASC"
            ).fetchall()
        return [slack_workspace_from_row(row) for row in rows]

    def get_slack_tokens(self, team_id: str) -> tuple[str | None, str | None]:
        """Return ``(bot_token, app_token)`` — the only path that reads secrets."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT bot_token, app_token FROM slack_workspaces WHERE team_id = ?",
                (team_id,),
            ).fetchone()
        if row is None:
            return None, None
        return row["bot_token"], row["app_token"]

    def set_slack_workspace_flags(
        self,
        team_id: str,
        *,
        enabled: bool | None = None,
        assistant_enabled: bool | None = None,
    ) -> SlackWorkspace | None:
        sets: list[str] = []
        params: list[object] = []
        if enabled is not None:
            sets.append("enabled = ?")
            params.append(1 if enabled else 0)
        if assistant_enabled is not None:
            sets.append("assistant_enabled = ?")
            params.append(1 if assistant_enabled else 0)
        if not sets:
            return self.get_slack_workspace(team_id)
        sets.append("updated_at = ?")
        params.extend([utc_now().isoformat(), team_id])
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE slack_workspaces SET {', '.join(sets)} WHERE team_id = ?",
                params,
            )
            if cursor.rowcount == 0:
                return None
        return self.get_slack_workspace(team_id)

    def clear_slack_bot_token(self, team_id: str) -> None:
        """Drop the cached token after a disconnect or revocation upstream."""
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE slack_workspaces
                SET bot_token = NULL, updated_at = ?
                WHERE team_id = ?
                """,
                (utc_now().isoformat(), team_id),
            )

    def delete_slack_workspace(self, team_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM slack_workspaces WHERE team_id = ?",
                (team_id,),
            )
        return cursor.rowcount > 0

    # --- allowlist ------------------------------------------------------

    def allow_slack_user(
        self,
        *,
        team_id: str,
        slack_user_id: str,
        display_name: str | None = None,
    ) -> SlackAllowedUser:
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO slack_allowed_users(
                    team_id, slack_user_id, display_name, created_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(team_id, slack_user_id) DO UPDATE SET
                    display_name = COALESCE(
                        excluded.display_name, slack_allowed_users.display_name
                    )
                """,
                (team_id, slack_user_id, display_name, now.isoformat()),
            )
        return SlackAllowedUser(
            team_id=team_id,
            slack_user_id=slack_user_id,
            display_name=display_name,
            created_at=now,
        )

    def disallow_slack_user(self, *, team_id: str, slack_user_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM slack_allowed_users
                WHERE team_id = ? AND slack_user_id = ?
                """,
                (team_id, slack_user_id),
            )
        return cursor.rowcount > 0

    def list_slack_allowed_users(self, team_id: str) -> list[SlackAllowedUser]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM slack_allowed_users
                WHERE team_id = ?
                ORDER BY created_at ASC
                """,
                (team_id,),
            ).fetchall()
        return [
            SlackAllowedUser(
                team_id=str(row["team_id"]),
                slack_user_id=str(row["slack_user_id"]),
                display_name=row["display_name"],
                created_at=datetime.fromisoformat(str(row["created_at"])),
            )
            for row in rows
        ]

    def is_slack_user_allowed(self, *, team_id: str, slack_user_id: str) -> bool:
        """Closed by default — an empty allowlist authorizes nobody."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM slack_allowed_users
                WHERE team_id = ? AND slack_user_id = ?
                """,
                (team_id, slack_user_id),
            ).fetchone()
        return row is not None

    # --- channel subscriptions -----------------------------------------

    def add_slack_subscription(
        self, *, session_id: str, channel: str
    ) -> SlackSubscription:
        now = utc_now()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO slack_subscriptions(
                    session_id, channel, created_at
                )
                VALUES (?, ?, ?)
                """,
                (session_id, channel, now.isoformat()),
            )
        return SlackSubscription(
            session_id=session_id, channel=channel, created_at=now
        )

    def remove_slack_subscription(self, *, session_id: str, channel: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM slack_subscriptions
                WHERE session_id = ? AND channel = ?
                """,
                (session_id, channel),
            )
        return cursor.rowcount > 0

    def list_slack_subscriptions(
        self, *, session_id: str | None = None, channel: str | None = None
    ) -> list[SlackSubscription]:
        clauses: list[str] = []
        params: list[object] = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if channel:
            clauses.append("channel = ?")
            params.append(channel)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM slack_subscriptions
                {where}
                ORDER BY created_at ASC
                """,
                params,
            ).fetchall()
        return [
            SlackSubscription(
                session_id=str(row["session_id"]),
                channel=str(row["channel"]),
                created_at=datetime.fromisoformat(str(row["created_at"])),
            )
            for row in rows
        ]

    # --- mention threads ------------------------------------------------

    def get_slack_mention_session(self, thread_target: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM slack_mention_threads WHERE thread_target = ?",
                (thread_target,),
            ).fetchone()
        return str(row["session_id"]) if row else None

    def set_slack_mention_session(
        self, *, thread_target: str, session_id: str, channel: str
    ) -> None:
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO slack_mention_threads(
                    thread_target, session_id, channel, created_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(thread_target) DO UPDATE SET
                    session_id = excluded.session_id,
                    channel = excluded.channel
                """,
                (thread_target, session_id, channel, utc_now().isoformat()),
            )

    # --- parked (unauthorized) messages ---------------------------------

    def park_slack_message(
        self,
        *,
        team_id: str,
        channel: str,
        slack_user_id: str,
        text: str,
        thread_target: str | None = None,
        user_name: str | None = None,
    ) -> SlackParkedMessage:
        now = utc_now()
        message_id = str(uuid.uuid4())
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO slack_parked_messages(
                    id, team_id, channel, thread_target, slack_user_id,
                    user_name, text, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    team_id,
                    channel,
                    thread_target,
                    slack_user_id,
                    user_name,
                    text,
                    now.isoformat(),
                ),
            )
        return SlackParkedMessage(
            id=message_id,
            team_id=team_id,
            channel=channel,
            thread_target=thread_target,
            slack_user_id=slack_user_id,
            user_name=user_name,
            text=text,
            created_at=now,
        )

    def list_slack_parked_messages(self) -> list[SlackParkedMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM slack_parked_messages ORDER BY created_at DESC"
            ).fetchall()
        return [
            SlackParkedMessage(
                id=str(row["id"]),
                team_id=str(row["team_id"]),
                channel=str(row["channel"]),
                thread_target=row["thread_target"],
                slack_user_id=str(row["slack_user_id"]),
                user_name=row["user_name"],
                text=str(row["text"]),
                created_at=datetime.fromisoformat(str(row["created_at"])),
            )
            for row in rows
        ]

    def delete_slack_parked_message(self, message_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM slack_parked_messages WHERE id = ?",
                (message_id,),
            )
        return cursor.rowcount > 0

    # --- per-session connector mutes ------------------------------------

    def set_session_connector_mute(
        self, *, session_id: str, connector: str, muted: bool
    ) -> None:
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO session_connector_mutes(
                    session_id, connector, muted, updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, connector) DO UPDATE SET
                    muted = excluded.muted,
                    updated_at = excluded.updated_at
                """,
                (session_id, connector, 1 if muted else 0, utc_now().isoformat()),
            )

    def is_session_connector_muted(self, *, session_id: str, connector: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT muted FROM session_connector_mutes
                WHERE session_id = ? AND connector = ?
                """,
                (session_id, connector),
            ).fetchone()
        return bool(row["muted"]) if row else False
