"""Message CRUD and per-message feedback."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from agent_server.models import AgentMessage, MessageRole, MessageSource
from agent_server.store.rows import message_from_row
from agent_server.store.util import utc_now


class MessageMixin:
    @staticmethod
    def _message(row) -> AgentMessage:  # type: ignore[no-untyped-def]
        return message_from_row(row)

    def add_message(
        self,
        *,
        session_id: str,
        role: MessageRole,
        content: str,
        source: MessageSource | None = None,
        created_at: datetime | None = None,
        message_id: str | None = None,
    ) -> AgentMessage:
        timestamp = created_at or utc_now()
        message = AgentMessage(
            id=message_id or str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            source=source,
            created_at=timestamp,
        )
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO messages(id, session_id, role, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.session_id,
                    message.role,
                    message.content,
                    (
                        json.dumps(source.model_dump(mode="json", by_alias=True))
                        if source is not None
                        else None
                    ),
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
        return [message_from_row(row) for row in rows]

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
