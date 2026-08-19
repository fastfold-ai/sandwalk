"""Replayable event log."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from agent_server.models import EventEnvelope
from agent_server.store.event_notifier import EVENT_NOTIFIER
from agent_server.store.util import utc_now


class EventMixin:
    def append_event(
        self,
        *,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        run_id: str | None = None,
        notify: bool = True,
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
        # Wake SSE pollers immediately (outside the write lock). Bench
        # cells poll session status instead of SSE — skip the wake.
        if notify:
            EVENT_NOTIFIER.notify(session_id)
        if event_type in {
            "run.completed",
            "run.failed",
            "run.awaiting_approval",
        }:
            self._publish_run_lifecycle(session_id, event_type)
        return EventEnvelope(
            id=event_id,
            session_id=session_id,
            run_id=run_id,
            sequence=sequence,
            timestamp=timestamp,
            type=event_type,
            payload=payload,
        )

    def _publish_run_lifecycle(self, session_id: str, event_type: str) -> None:
        """Fan run finish/HITL out on the global session bus.

        Per-session SSE only reaches chats the UI already subscribed to. Slack
        (and any other background chat) needs this so the desktop can mark
        unread, Dock badge, and banners without that stream.
        """
        session = self.get_session(session_id)
        if session is None or getattr(session, "source", None) in {"bench", "capy"}:
            return
        try:
            from agent_server.session_event_bus import session_event_bus

            session_event_bus.publish(
                event_type,
                {
                    "sessionId": session_id,
                    "session": session.model_dump(mode="json", by_alias=True),
                },
            )
        except Exception:  # noqa: BLE001
            pass

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

    def clear_events(self, session_id: str) -> int:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM events WHERE session_id = ?",
                (session_id,),
            )
        return int(cursor.rowcount)
