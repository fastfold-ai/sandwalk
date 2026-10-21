"""SQLite persistence mixin for Automations, Automation Runs, and SSH Hosts."""

from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from agent_server.models.automations import (
    Automation,
    AutomationRun,
    SshHost,
)
from agent_server.store.util import utc_now


def _json_str_list(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    try:
        parsed = json.loads(str(raw))
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(x).strip() for x in parsed if str(x).strip()]


def _parse_dt(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except Exception:
        return None


def automation_from_row(row: sqlite3.Row) -> Automation:
    return Automation(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        prompt=row["prompt"] or "",
        command=row["command"],
        schedule_expr=row["schedule_expr"] or "every 1h",
        schedule_kind=row["schedule_kind"] or "interval",
        schedule_label=row["schedule_label"] or row["schedule_expr"] or "Every hour",
        session_mode=row["session_mode"] or "fresh",
        origin_session_id=row["origin_session_id"],
        specialist_id=row["specialist_id"],
        project_id=row["project_id"],
        workdir=row["workdir"],
        ssh_host_id=row["ssh_host_id"],
        remote_workdir=row["remote_workdir"],
        skill_names=_json_str_list(row["skill_names"]),
        tool_names=_json_str_list(row["tool_names"]),
        mcp_server_ids=_json_str_list(row["mcp_server_ids"]),
        provider_pin=row["provider_pin"],
        model_pin=row["model_pin"],
        continuity=bool(row["continuity"]),
        context_from=_json_str_list(row["context_from"]),
        wake_on_change_only=bool(row["wake_on_change_only"]),
        repeat_limit=int(row["repeat_limit"]) if row["repeat_limit"] is not None else None,
        run_count=int(row["run_count"] or 0),
        enabled=bool(row["enabled"]),
        next_run_at=_parse_dt(row["next_run_at"]),
        last_run_at=_parse_dt(row["last_run_at"]),
        last_status=row["last_status"] or "idle",
        last_error=row["last_error"],
        webhook_token=row["webhook_token"],
        template_id=row["template_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def automation_run_from_row(row: sqlite3.Row) -> AutomationRun:
    keys = set(row.keys())
    return AutomationRun(
        id=row["id"],
        automation_id=row["automation_id"],
        automation_name=row["automation_name"] if "automation_name" in keys else None,
        session_id=row["session_id"],
        status=row["status"] or "running",
        trigger_source=row["trigger_source"] or "schedule",
        started_at=datetime.fromisoformat(row["started_at"]),
        finished_at=_parse_dt(row["finished_at"]),
        duration_seconds=(
            float(row["duration_seconds"]) if row["duration_seconds"] is not None else None
        ),
        output_excerpt=row["output_excerpt"],
        output_path=row["output_path"],
        error=row["error"],
        was_catchup=bool(row["was_catchup"]),
    )


def ssh_host_from_row(row: sqlite3.Row) -> SshHost:
    return SshHost(
        id=row["id"],
        alias=row["alias"],
        host=row["host"],
        user=row["user"],
        port=int(row["port"] or 22),
        identity_file=row["identity_file"],
        proxy_jump=row["proxy_jump"],
        remote_port=int(row["remote_port"] or 8787),
        default_workdir=row["default_workdir"],
        source="saved",
        status=row["status"] or "unknown",
        platform=row["platform"],
        arch=row["arch"],
        hostname=row["hostname"],
        gpu_summary=row["gpu_summary"],
        slurm_available=bool(row["slurm_available"]),
        sandwalk_installed=bool(row["sandwalk_installed"]),
        sandwalk_version=row["sandwalk_version"],
        daemon_running=bool(row["daemon_running"]),
        tunnel_local_port=(
            int(row["tunnel_local_port"]) if row["tunnel_local_port"] is not None else None
        ),
        tunnel_url=row["tunnel_url"],
        last_connected_at=_parse_dt(row["last_connected_at"]),
        last_error=row["last_error"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class AutomationMixin:
    _write_lock: Any
    _connect: Any

    def create_automation(
        self,
        *,
        name: str,
        description: str | None = None,
        prompt: str = "",
        command: str | None = None,
        schedule_expr: str = "every 1h",
        schedule_kind: str = "interval",
        schedule_label: str = "Every hour",
        session_mode: str = "fresh",
        origin_session_id: str | None = None,
        specialist_id: str | None = None,
        project_id: str | None = None,
        workdir: str | None = None,
        ssh_host_id: str | None = None,
        remote_workdir: str | None = None,
        skill_names: list[str] | None = None,
        tool_names: list[str] | None = None,
        mcp_server_ids: list[str] | None = None,
        provider_pin: str | None = None,
        model_pin: str | None = None,
        continuity: bool = False,
        context_from: list[str] | None = None,
        wake_on_change_only: bool = False,
        repeat_limit: int | None = None,
        enabled: bool = True,
        next_run_at: datetime | None = None,
        template_id: str | None = None,
        automation_id: str | None = None,
    ) -> Automation:
        now = utc_now().isoformat()
        aid = automation_id or str(uuid.uuid4())
        token = secrets.token_urlsafe(18)
        with self._write_lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO automations(
                    id, name, description, prompt, command,
                    schedule_expr, schedule_kind, schedule_label, session_mode,
                    origin_session_id, specialist_id, project_id, workdir,
                    ssh_host_id, remote_workdir,
                    skill_names, tool_names, mcp_server_ids,
                    provider_pin, model_pin,
                    continuity, context_from, wake_on_change_only,
                    repeat_limit, run_count, enabled, next_run_at,
                    last_run_at, last_status, last_error,
                    webhook_token, template_id, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, 0, ?, ?,
                    NULL, 'idle', NULL,
                    ?, ?, ?, ?
                )
                """,
                (
                    aid,
                    name.strip() or "Untitled automation",
                    description,
                    prompt,
                    command,
                    schedule_expr,
                    schedule_kind,
                    schedule_label,
                    session_mode,
                    origin_session_id,
                    specialist_id,
                    project_id,
                    workdir,
                    ssh_host_id,
                    remote_workdir,
                    json.dumps(skill_names or []),
                    json.dumps(tool_names or []),
                    json.dumps(mcp_server_ids or []),
                    provider_pin,
                    model_pin,
                    1 if continuity else 0,
                    json.dumps(context_from or []),
                    1 if wake_on_change_only else 0,
                    repeat_limit,
                    1 if enabled else 0,
                    next_run_at.isoformat() if next_run_at else None,
                    token,
                    template_id,
                    now,
                    now,
                ),
            )
        if origin_session_id:
            try:
                self.update_session(  # type: ignore[attr-defined]
                    origin_session_id,
                    automation_id=aid,
                    update_automation_id=True,
                )
            except Exception:
                pass
        res = self.get_automation(aid)
        if res is None:
            raise RuntimeError("Failed to create automation.")
        return res

    def get_automation(self, id_or_name: str) -> Automation | None:
        needle = (id_or_name or "").strip()
        if not needle:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM automations WHERE id = ?", (needle,)
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM automations WHERE lower(name) = lower(?) ORDER BY updated_at DESC LIMIT 1",
                    (needle,),
                ).fetchone()
        return automation_from_row(row) if row is not None else None

    def get_automation_by_webhook_token(self, token: str) -> Automation | None:
        cleaned = (token or "").strip()
        if not cleaned:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM automations WHERE webhook_token = ?", (cleaned,)
            ).fetchone()
        return automation_from_row(row) if row is not None else None

    def list_automations(self) -> list[Automation]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM automations ORDER BY updated_at DESC, created_at DESC"
            ).fetchall()
        return [automation_from_row(r) for r in rows]

    def update_automation_fields(
        self,
        automation_id: str,
        **fields: Any,
    ) -> Automation | None:
        current = self.get_automation(automation_id)
        if current is None:
            return None
        allowed = {
            "name",
            "description",
            "prompt",
            "command",
            "schedule_expr",
            "schedule_kind",
            "schedule_label",
            "session_mode",
            "origin_session_id",
            "specialist_id",
            "project_id",
            "workdir",
            "ssh_host_id",
            "remote_workdir",
            "skill_names",
            "tool_names",
            "mcp_server_ids",
            "provider_pin",
            "model_pin",
            "continuity",
            "context_from",
            "wake_on_change_only",
            "repeat_limit",
            "run_count",
            "enabled",
            "next_run_at",
            "last_run_at",
            "last_status",
            "last_error",
        }
        assignments: list[str] = []
        values: list[Any] = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            assignments.append(f"{k} = ?")
            if k in {"skill_names", "tool_names", "mcp_server_ids", "context_from"}:
                values.append(json.dumps(v or []))
            elif k in {"continuity", "wake_on_change_only", "enabled"}:
                values.append(1 if v else 0)
            elif k in {"next_run_at", "last_run_at"} and isinstance(v, datetime):
                values.append(v.isoformat())
            else:
                values.append(v)
        if not assignments:
            return current
        assignments.append("updated_at = ?")
        values.append(utc_now().isoformat())
        values.append(current.id)
        with self._write_lock, self._connect() as conn:
            conn.execute(
                f"UPDATE automations SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )
        return self.get_automation(current.id)

    def delete_automation(self, automation_id: str) -> bool:
        current = self.get_automation(automation_id)
        if current is None:
            return False
        with self._write_lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM automations WHERE id = ?", (current.id,))
        return bool(cur.rowcount > 0)

    def create_automation_run(
        self,
        *,
        automation_id: str,
        session_id: str | None = None,
        status: str = "running",
        trigger_source: str = "schedule",
        was_catchup: bool = False,
    ) -> AutomationRun:
        rid = str(uuid.uuid4())
        now = utc_now().isoformat()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO automation_runs(
                    id, automation_id, session_id, status, trigger_source,
                    started_at, was_catchup
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rid,
                    automation_id,
                    session_id,
                    status,
                    trigger_source,
                    now,
                    1 if was_catchup else 0,
                ),
            )
            row = conn.execute(
                """
                SELECT r.*, a.name AS automation_name
                FROM automation_runs r
                LEFT JOIN automations a ON a.id = r.automation_id
                WHERE r.id = ?
                """,
                (rid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Failed to create automation run.")
        return automation_run_from_row(row)

    def finish_automation_run(
        self,
        run_id: str,
        *,
        status: str,
        session_id: str | None = None,
        output_excerpt: str | None = None,
        output_path: str | None = None,
        error: str | None = None,
    ) -> AutomationRun | None:
        now = utc_now()
        with self._write_lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM automation_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if existing is None:
                return None
            started = datetime.fromisoformat(existing["started_at"])
            dur = max(0.0, (now - started).total_seconds())
            next_session = session_id if session_id is not None else existing["session_id"]
            conn.execute(
                """
                UPDATE automation_runs
                SET status = ?, session_id = ?, finished_at = ?, duration_seconds = ?,
                    output_excerpt = ?, output_path = ?, error = ?
                WHERE id = ?
                """,
                (
                    status,
                    next_session,
                    now.isoformat(),
                    round(dur, 3),
                    output_excerpt,
                    output_path,
                    error,
                    run_id,
                ),
            )
            row = conn.execute(
                """
                SELECT r.*, a.name AS automation_name
                FROM automation_runs r
                LEFT JOIN automations a ON a.id = r.automation_id
                WHERE r.id = ?
                """,
                (run_id,),
            ).fetchone()
        return automation_run_from_row(row) if row is not None else None

    def list_automation_runs(
        self,
        *,
        automation_id: str | None = None,
        limit: int = 50,
    ) -> list[AutomationRun]:
        with self._connect() as conn:
            if automation_id:
                rows = conn.execute(
                    """
                    SELECT r.*, a.name AS automation_name
                    FROM automation_runs r
                    LEFT JOIN automations a ON a.id = r.automation_id
                    WHERE r.automation_id = ?
                    ORDER BY r.started_at DESC
                    LIMIT ?
                    """,
                    (automation_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT r.*, a.name AS automation_name
                    FROM automation_runs r
                    LEFT JOIN automations a ON a.id = r.automation_id
                    ORDER BY r.started_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [automation_run_from_row(r) for r in rows]

    # --- SSH Hosts Persistence ---

    def upsert_ssh_host(
        self,
        *,
        alias: str,
        host: str,
        user: str | None = None,
        port: int = 22,
        identity_file: str | None = None,
        proxy_jump: str | None = None,
        remote_port: int = 8787,
        default_workdir: str | None = None,
        host_id: str | None = None,
    ) -> SshHost:
        now = utc_now().isoformat()
        hid = host_id or str(uuid.uuid4())
        clean_alias = alias.strip() or host.strip()
        clean_host = host.strip()
        clean_user = user.strip() if user and user.strip() else None
        clean_port = int(port or 22)
        with self._write_lock, self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM ssh_hosts
                WHERE id = ?
                   OR lower(alias) = lower(?)
                   OR (
                        lower(host) = lower(?)
                        AND coalesce(lower(user), '') = coalesce(lower(?), '')
                        AND port = ?
                   )
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (hid, clean_alias, clean_host, clean_user or "", clean_port),
            ).fetchone()
            if existing is not None:
                hid = existing["id"]
                existing_alias = (existing["alias"] or "").strip()
                # Preserve existing human alias if the incoming alias is just the raw host/IP
                effective_alias = (
                    existing_alias
                    if existing_alias
                    and existing_alias.lower() != clean_host.lower()
                    and clean_alias.lower() == clean_host.lower()
                    else clean_alias
                )
                conn.execute(
                    """
                    UPDATE ssh_hosts
                    SET alias = ?, host = ?, user = ?, port = ?, identity_file = ?,
                        proxy_jump = ?, remote_port = ?, default_workdir = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        effective_alias,
                        clean_host,
                        clean_user or existing["user"],
                        clean_port,
                        identity_file or existing["identity_file"],
                        proxy_jump or existing["proxy_jump"],
                        int(remote_port or existing["remote_port"] or 8787),
                        default_workdir or existing["default_workdir"],
                        now,
                        hid,
                    ),
                )
                # Remove any stale duplicate rows for the same (host, user, port)
                conn.execute(
                    """
                    DELETE FROM ssh_hosts
                    WHERE id != ?
                      AND lower(host) = lower(?)
                      AND coalesce(lower(user), '') = coalesce(lower(?), '')
                      AND port = ?
                    """,
                    (hid, clean_host, clean_user or existing["user"] or "", clean_port),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO ssh_hosts(
                        id, alias, host, user, port, identity_file, proxy_jump,
                        remote_port, default_workdir, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', ?, ?)
                    """,
                    (
                        hid,
                        clean_alias,
                        clean_host,
                        clean_user,
                        clean_port,
                        identity_file,
                        proxy_jump,
                        int(remote_port or 8787),
                        default_workdir,
                        now,
                        now,
                    ),
                )
        res = self.get_ssh_host(hid)
        if res is None:
            raise RuntimeError("Failed to save SSH host.")
        return res

    def get_ssh_host(self, id_or_alias: str) -> SshHost | None:
        needle = (id_or_alias or "").strip()
        if not needle:
            return None
        user_part: str | None = None
        host_part = needle
        if "@" in needle and " " not in needle:
            u, h = needle.split("@", 1)
            user_part = u.strip() or None
            host_part = h.strip()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM ssh_hosts
                WHERE id = ?
                   OR lower(alias) = lower(?)
                   OR lower(host) = lower(?)
                   OR lower(host) = lower(?)
                   OR (
                        ? IS NOT NULL
                        AND lower(host) = lower(?)
                        AND coalesce(lower(user), '') = lower(?)
                   )
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (
                    needle,
                    needle,
                    needle,
                    host_part,
                    user_part,
                    host_part,
                    user_part or "",
                ),
            ).fetchone()
        return ssh_host_from_row(row) if row is not None else None

    def list_saved_ssh_hosts(self) -> list[SshHost]:
        with self._write_lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ssh_hosts ORDER BY updated_at DESC, alias ASC"
            ).fetchall()
            seen_targets: set[tuple[str, str, int]] = set()
            kept: list[SshHost] = []
            duplicate_ids: list[str] = []
            for r in rows:
                h = ssh_host_from_row(r)
                key = (h.host.lower(), (h.user or "").lower(), int(h.port or 22))
                if key in seen_targets:
                    duplicate_ids.append(h.id)
                    continue
                seen_targets.add(key)
                kept.append(h)
            if duplicate_ids:
                placeholders = ",".join("?" for _ in duplicate_ids)
                conn.execute(
                    f"DELETE FROM ssh_hosts WHERE id IN ({placeholders})",
                    tuple(duplicate_ids),
                )
        return kept

    def update_ssh_host_status(
        self,
        host_id: str,
        **fields: Any,
    ) -> SshHost | None:
        current = self.get_ssh_host(host_id)
        if current is None:
            return None
        allowed = {
            "alias",
            "host",
            "user",
            "port",
            "identity_file",
            "proxy_jump",
            "remote_port",
            "default_workdir",
            "status",
            "platform",
            "arch",
            "hostname",
            "gpu_summary",
            "slurm_available",
            "sandwalk_installed",
            "sandwalk_version",
            "daemon_running",
            "tunnel_local_port",
            "tunnel_url",
            "last_connected_at",
            "last_error",
        }
        assignments: list[str] = []
        values: list[Any] = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            assignments.append(f"{k} = ?")
            if k in {"slurm_available", "sandwalk_installed", "daemon_running"}:
                values.append(1 if v else 0)
            elif k == "last_connected_at" and isinstance(v, datetime):
                values.append(v.isoformat())
            else:
                values.append(v)
        if not assignments:
            return current
        assignments.append("updated_at = ?")
        values.append(utc_now().isoformat())
        values.append(current.id)
        with self._write_lock, self._connect() as conn:
            conn.execute(
                f"UPDATE ssh_hosts SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )
        return self.get_ssh_host(current.id)

    def delete_ssh_host(self, host_id: str) -> bool:
        current = self.get_ssh_host(host_id)
        if current is None:
            return False
        with self._write_lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM ssh_hosts WHERE id = ?", (current.id,))
        return bool(cur.rowcount > 0)
