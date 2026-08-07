"""Persisted per-run usage rollups for Overview analytics."""

from __future__ import annotations

from typing import Any

from agent_server.store.util import utc_now

_SURFACES = frozenset({"cli", "ui", "slack", "unknown"})


def normalize_surface(value: object | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in _SURFACES:
        return raw
    return "unknown"


def normalize_provider(value: object | None) -> str | None:
    raw = str(value or "").strip().lower()
    return raw or None


class UsageMixin:
    def upsert_usage_run(
        self,
        *,
        run_id: str,
        session_id: str,
        day: str,
        surface: str = "unknown",
        model_id: str | None = None,
        provider: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> None:
        rid = str(run_id or "").strip()
        sid = str(session_id or "").strip()
        if not rid or not sid:
            return
        now = utc_now().isoformat()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO usage_runs(
                    run_id, session_id, day, surface, model_id, provider,
                    input_tokens, output_tokens, cache_read_tokens,
                    cache_creation_tokens, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    day = excluded.day,
                    surface = CASE
                        WHEN excluded.surface != 'unknown' THEN excluded.surface
                        ELSE usage_runs.surface
                    END,
                    model_id = COALESCE(excluded.model_id, usage_runs.model_id),
                    provider = COALESCE(excluded.provider, usage_runs.provider),
                    input_tokens = excluded.input_tokens,
                    output_tokens = excluded.output_tokens,
                    cache_read_tokens = excluded.cache_read_tokens,
                    cache_creation_tokens = excluded.cache_creation_tokens,
                    updated_at = excluded.updated_at
                """,
                (
                    rid,
                    sid,
                    day,
                    normalize_surface(surface),
                    (model_id or "").strip() or None,
                    normalize_provider(provider),
                    max(0, int(input_tokens or 0)),
                    max(0, int(output_tokens or 0)),
                    max(0, int(cache_read_tokens or 0)),
                    max(0, int(cache_creation_tokens or 0)),
                    now,
                ),
            )

    def list_usage_runs(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, session_id, day, surface, model_id, provider,
                       input_tokens, output_tokens, cache_read_tokens,
                       cache_creation_tokens, updated_at
                FROM usage_runs
                ORDER BY day ASC, run_id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def usage_run_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM usage_runs").fetchone()
            return int(row["n"] if row else 0)

    def get_usage_meta(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM usage_meta WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def set_usage_meta(self, key: str, value: str) -> None:
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO usage_meta(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def list_run_usage_events(self) -> list[dict[str, Any]]:
        """Return raw run.usage event rows for backfill (newest last)."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT e.run_id, e.session_id, e.timestamp, e.payload,
                       s.client_surface, s.source
                FROM events e
                LEFT JOIN sessions s ON s.id = e.session_id
                WHERE e.type = 'run.usage' AND e.run_id IS NOT NULL
                ORDER BY e.sequence ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def count_messages_for_sessions(self, session_ids: list[str]) -> int:
        ids = [str(sid).strip() for sid in session_ids if str(sid).strip()]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS n FROM messages
                WHERE session_id IN ({placeholders})
                """,
                ids,
            ).fetchone()
        return int(row["n"] if row else 0)
