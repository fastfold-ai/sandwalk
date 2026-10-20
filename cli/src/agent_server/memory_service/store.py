"""Persistent SQLite + Markdown store for bounded Memories, Pending Approvals, and Session Search."""

from __future__ import annotations

import contextlib
import json
import re
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_server.models.memory import (
    MemoryEntry,
    MemoryEntryList,
    MemorySettings,
    PendingMemoryWrite,
    UpdateMemorySettingsRequest,
)

_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"(?i)\b(bearer|api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9._-]{16,}['\"]?"),
)

_INJECTION_PATTERNS = (
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions"),
    re.compile(r"(?i)system\s+prompt\s+override"),
    re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]"),
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def memory_root() -> Path:
    from agent import config as _cfg_mod

    root = Path(_cfg_mod.CONFIG_DIR) / "memory"
    root.mkdir(parents=True, exist_ok=True)
    return root


def normalize_scope(scope: str | None) -> str:
    raw = str(scope or "global").strip()
    if not raw or raw.lower() in {"all", "default", "global"}:
        return "global"
    if raw.lower() == "user":
        return "user"
    if raw.lower() == "capy":
        return "capy"
    if raw.startswith(("project:", "specialist:")):
        return raw
    return f"project:{raw}"


def scrub_and_validate_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        raise ValueError("Memory content cannot be empty.")
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            raise ValueError(
                "Memory entry blocked by security scan (prompt injection or hidden Unicode detected)."
            )
    for secret_re in _SECRET_PATTERNS:
        cleaned = secret_re.sub("[REDACTED_SECRET]", cleaned)
    return cleaned


def load_memory_settings() -> MemorySettings:
    from agent.config import Config

    cfg = Config.load()
    return MemorySettings(
        enabled=bool(cfg.get("memory.enabled", True)),
        user_profile_enabled=bool(cfg.get("memory.user_profile_enabled", True)),
        wiki_enabled=bool(cfg.get("memory.wiki_enabled", True)),
        graph_enabled=bool(cfg.get("memory.graph_enabled", True)),
        default_cookbook=str(cfg.get("memory.default_cookbook") or "biomed-research"),
        global_cookbook=str(cfg.get("memory.global_cookbook") or "second-brain"),
        memory_char_limit=int(cfg.get("memory.memory_char_limit") or 2200),
        user_char_limit=int(cfg.get("memory.user_char_limit") or 1375),
        wiki_toc_max_chars=int(cfg.get("memory.wiki_toc_max_chars") or 1800),
        write_approval=bool(cfg.get("memory.write_approval", False)),
        graph_branch_on_write=bool(cfg.get("memory.graph_branch_on_write", False)),
        distiller_mode=str(cfg.get("memory.distiller.mode") or "hybrid"),  # type: ignore[arg-type]
        distiller_provider=str(cfg.get("memory.distiller.provider") or "auto"),
        distiller_model=str(cfg.get("memory.distiller.model") or "auto"),
        distiller_openai_profile_id=str(
            cfg.get("memory.distiller.openai_profile_id") or ""
        ),
        distiller_defer_on_local_gpu=bool(
            cfg.get("memory.distiller.defer_on_local_gpu", True)
        ),
        distiller_max_input_tokens=int(
            cfg.get("memory.distiller.max_input_tokens") or 48000
        ),
        embeddings_provider=str(cfg.get("memory.embeddings.provider") or "none"),  # type: ignore[arg-type]
        embeddings_model=str(cfg.get("memory.embeddings.model") or ""),
        embeddings_profile_id=str(cfg.get("memory.embeddings.profile_id") or ""),
    )


def update_memory_settings(payload: UpdateMemorySettingsRequest) -> MemorySettings:
    from agent.config import Config

    cfg = Config.load()
    mapping = {
        "enabled": "memory.enabled",
        "user_profile_enabled": "memory.user_profile_enabled",
        "wiki_enabled": "memory.wiki_enabled",
        "graph_enabled": "memory.graph_enabled",
        "default_cookbook": "memory.default_cookbook",
        "global_cookbook": "memory.global_cookbook",
        "memory_char_limit": "memory.memory_char_limit",
        "user_char_limit": "memory.user_char_limit",
        "wiki_toc_max_chars": "memory.wiki_toc_max_chars",
        "write_approval": "memory.write_approval",
        "graph_branch_on_write": "memory.graph_branch_on_write",
        "distiller_mode": "memory.distiller.mode",
        "distiller_provider": "memory.distiller.provider",
        "distiller_model": "memory.distiller.model",
        "distiller_openai_profile_id": "memory.distiller.openai_profile_id",
        "distiller_defer_on_local_gpu": "memory.distiller.defer_on_local_gpu",
        "distiller_max_input_tokens": "memory.distiller.max_input_tokens",
        "embeddings_provider": "memory.embeddings.provider",
        "embeddings_model": "memory.embeddings.model",
        "embeddings_profile_id": "memory.embeddings.profile_id",
    }
    data = payload.model_dump(exclude_none=True)
    for field_name, cfg_key in mapping.items():
        if field_name in data:
            cfg.set(cfg_key, data[field_name])
    cfg.save()
    return load_memory_settings()


class MemoryStore:
    """Thread-safe SQLite + Markdown store for Sandwalk Memory & Graph state."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (memory_root() / "memory.db")
        self._lock = threading.RLock()
        self._init_db()

    @contextlib.contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    target TEXT NOT NULL DEFAULT 'memory',
                    layer TEXT NOT NULL DEFAULT 'L1',
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    pinned INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active',
                    source_session_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_entries_scope
                    ON memory_entries(scope, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS memory_pending_writes (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    action TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    source_session_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scope_cookbooks (
                    scope TEXT PRIMARY KEY,
                    cookbook_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS specialist_personas (
                    specialist_id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL,
                    role_label TEXT,
                    avatar_url TEXT,
                    provider TEXT,
                    model TEXT,
                    openai_profile_id TEXT,
                    cookbook_id TEXT,
                    priors TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS graph_branches (
                    scope TEXT NOT NULL,
                    name TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (scope, name)
                );

                CREATE TABLE IF NOT EXISTS graph_nodes (
                    id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    branch TEXT NOT NULL DEFAULT 'main',
                    slug TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    layer TEXT NOT NULL DEFAULT 'domain',
                    name TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    properties_json TEXT NOT NULL DEFAULT '{}',
                    source_ref TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (scope, branch, id)
                );

                CREATE TABLE IF NOT EXISTS graph_edges (
                    id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    branch TEXT NOT NULL DEFAULT 'main',
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    polarity TEXT NOT NULL DEFAULT 'neutral',
                    score REAL NOT NULL DEFAULT 0.8,
                    summary TEXT NOT NULL DEFAULT '',
                    source_ref TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (scope, branch, id)
                );
                """
            )

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        try:
            tags = json.loads(row["tags_json"] or "[]")
        except Exception:
            tags = []
        return MemoryEntry(
            id=row["id"],
            scope=row["scope"],
            target=row["target"],
            layer=row["layer"],
            content=row["content"],
            tags=[str(t) for t in tags if str(t).strip()],
            pinned=bool(row["pinned"]),
            status=row["status"],
            source_session_id=row["source_session_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _sync_markdown_mirror(self, scope: str) -> None:
        """Mirror active entries to USER.md / MEMORY.md / PRIORS.md on disk (Hermes style)."""
        root = memory_root()
        if scope == "user":
            entries = self.list_entries(scope="user", include_user=False).data
            path = root / "USER.md"
        elif scope.startswith("specialist:"):
            slug = scope.split(":", 1)[1]
            spec_dir = root / "specialists" / slug
            spec_dir.mkdir(parents=True, exist_ok=True)
            entries = self.list_entries(scope=scope, include_user=False).data
            path = spec_dir / "MEMORY.md"
        elif scope.startswith("project:"):
            pid = scope.split(":", 1)[1]
            proj_dir = root / "projects" / pid
            proj_dir.mkdir(parents=True, exist_ok=True)
            entries = self.list_entries(scope=scope, include_user=False).data
            path = proj_dir / "MEMORY.md"
        else:
            entries = self.list_entries(scope="global", include_user=False).data
            path = root / "MEMORY.md"

        body = "\n\n§\n\n".join(e.content for e in entries)
        path.write_text(body + ("\n" if body else ""), encoding="utf-8")

    def list_entries(self, *, scope: str = "global", include_user: bool = True) -> MemoryEntryList:
        norm_scope = normalize_scope(scope)
        settings = load_memory_settings()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memory_entries
                WHERE scope = ? AND status = 'active'
                ORDER BY pinned DESC, updated_at DESC
                """,
                (norm_scope,),
            ).fetchall()
            user_rows = (
                conn.execute(
                    """
                    SELECT * FROM memory_entries
                    WHERE scope = 'user' AND status = 'active'
                    ORDER BY pinned DESC, updated_at DESC
                    """
                ).fetchall()
                if include_user and norm_scope != "user"
                else []
            )
        scope_entries = [self._row_to_entry(r) for r in rows]
        user_entries = [self._row_to_entry(r) for r in user_rows]
        char_used = sum(len(e.content) for e in scope_entries)
        user_char_used = (
            char_used if norm_scope == "user" else sum(len(e.content) for e in user_entries)
        )
        combined = [*user_entries, *scope_entries] if include_user and norm_scope != "user" else scope_entries
        return MemoryEntryList(
            data=combined,
            scope=norm_scope,
            char_used=char_used,
            char_limit=settings.memory_char_limit,
            user_char_used=user_char_used,
            user_char_limit=settings.user_char_limit,
        )

    def stage_pending_write(
        self,
        *,
        scope: str,
        kind: str,
        action: str,
        summary: str,
        payload: dict[str, Any],
        source_session_id: str | None = None,
    ) -> PendingMemoryWrite:
        norm_scope = normalize_scope(scope)
        now = _now_iso()
        pid = f"pw_{uuid.uuid4().hex[:10]}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_pending_writes(
                    id, scope, kind, action, summary, payload_json, source_session_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, norm_scope, kind, action, summary, json.dumps(payload), source_session_id, now),
            )
        return PendingMemoryWrite(
            id=pid,
            scope=norm_scope,
            kind=kind,  # type: ignore[arg-type]
            action=action,  # type: ignore[arg-type]
            summary=summary,
            payload=payload,
            source_session_id=source_session_id,
            created_at=now,
        )

    def list_pending_writes(self, *, scope: str | None = None) -> list[PendingMemoryWrite]:
        with self._connect() as conn:
            if scope and scope != "all":
                norm = normalize_scope(scope)
                rows = conn.execute(
                    "SELECT * FROM memory_pending_writes WHERE scope = ? ORDER BY created_at DESC",
                    (norm,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memory_pending_writes ORDER BY created_at DESC"
                ).fetchall()
        out: list[PendingMemoryWrite] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except Exception:
                payload = {}
            out.append(
                PendingMemoryWrite(
                    id=row["id"],
                    scope=row["scope"],
                    kind=row["kind"],
                    action=row["action"],
                    summary=row["summary"],
                    payload=payload,
                    source_session_id=row["source_session_id"],
                    created_at=row["created_at"],
                )
            )
        return out

    def reject_pending_write(self, pending_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM memory_pending_writes WHERE id = ?", (pending_id,))
        return cur.rowcount > 0

    def add_entry(
        self,
        *,
        scope: str = "global",
        target: str = "memory",
        layer: str = "L1",
        content: str,
        tags: list[str] | None = None,
        pinned: bool = False,
        source_session_id: str | None = None,
        bypass_approval: bool = True,
    ) -> MemoryEntry:
        cleaned = scrub_and_validate_text(content)
        effective_scope = "user" if target == "user" else normalize_scope(scope)
        settings = load_memory_settings()
        if settings.write_approval and not bypass_approval:
            staged = self.stage_pending_write(
                scope=effective_scope,
                kind="memory",
                action="add",
                summary=f"Add memory ({effective_scope}): {cleaned[:80]}",
                payload={
                    "scope": effective_scope,
                    "target": target,
                    "layer": layer,
                    "content": cleaned,
                    "tags": list(tags or []),
                    "pinned": pinned,
                },
                source_session_id=source_session_id,
            )
            return MemoryEntry(
                id=staged.id,
                scope=effective_scope,
                target=target,  # type: ignore[arg-type]
                layer=layer,  # type: ignore[arg-type]
                content=cleaned,
                tags=list(tags or []),
                pinned=pinned,
                status="pending",
                source_session_id=source_session_id,
                created_at=staged.created_at,
                updated_at=staged.created_at,
            )

        current = self.list_entries(scope=effective_scope, include_user=False)
        for existing in current.data:
            if existing.content.strip().lower() == cleaned.lower():
                return existing

        limit = settings.user_char_limit if effective_scope == "user" else settings.memory_char_limit
        if current.char_used + len(cleaned) > limit:
            overflow = (current.char_used + len(cleaned)) - limit
            raise ValueError(
                f"Memory at {current.char_used}/{limit} chars; adding this entry "
                f"({len(cleaned)} chars) would exceed the limit by {overflow} chars. "
                "Shorten or remove stale entries first."
            )

        now = _now_iso()
        entry_id = f"mem_{uuid.uuid4().hex[:10]}"
        clean_tags = [str(t).strip() for t in (tags or []) if str(t).strip()]
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_entries(
                    id, scope, target, layer, content, tags_json, pinned, status,
                    source_session_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    entry_id,
                    effective_scope,
                    target,
                    layer,
                    cleaned,
                    json.dumps(clean_tags),
                    1 if pinned else 0,
                    source_session_id,
                    now,
                    now,
                ),
            )
        self._sync_markdown_mirror(effective_scope)
        return self.get_entry(entry_id)  # type: ignore[return-value]

    def get_entry(self, entry_id: str) -> MemoryEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memory_entries WHERE id = ?", (entry_id,)
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def update_entry(
        self,
        entry_id: str,
        *,
        content: str | None = None,
        tags: list[str] | None = None,
        pinned: bool | None = None,
    ) -> MemoryEntry | None:
        existing = self.get_entry(entry_id)
        if existing is None:
            return None
        next_content = existing.content if content is None else scrub_and_validate_text(content)
        next_tags = (
            existing.tags
            if tags is None
            else [str(t).strip() for t in tags if str(t).strip()]
        )
        next_pinned = existing.pinned if pinned is None else bool(pinned)
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE memory_entries
                SET content = ?, tags_json = ?, pinned = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_content, json.dumps(next_tags), 1 if next_pinned else 0, now, entry_id),
            )
        self._sync_markdown_mirror(existing.scope)
        return self.get_entry(entry_id)

    def delete_entry(self, entry_id: str) -> bool:
        existing = self.get_entry(entry_id)
        if existing is None:
            return False
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
        self._sync_markdown_mirror(existing.scope)
        return cur.rowcount > 0

    def mutate_by_substring(
        self,
        *,
        scope: str,
        target: str = "memory",
        action: str,
        content: str = "",
        old_text: str = "",
        tags: list[str] | None = None,
        source_session_id: str | None = None,
        bypass_approval: bool = False,
    ) -> dict[str, Any]:
        """Hermes-compatible add / patch / remove with unique substring matching."""
        effective_scope = "user" if target == "user" else normalize_scope(scope)
        act = action.strip().lower()
        if act == "add":
            entry = self.add_entry(
                scope=effective_scope,
                target=target,
                content=content,
                tags=tags,
                source_session_id=source_session_id,
                bypass_approval=bypass_approval,
            )
            return {
                "ok": True,
                "action": "add",
                "status": entry.status,
                "entry": entry.model_dump(mode="json", by_alias=True),
            }

        needle = str(old_text or "").strip()
        if not needle:
            raise ValueError(f"old_text is required for memory.{act}")
        entries = self.list_entries(scope=effective_scope, include_user=False).data
        exact = [e for e in entries if e.content == needle]
        matches = exact if len(exact) == 1 else [e for e in entries if needle in e.content]
        if not matches:
            raise ValueError(f"No memory entry in {effective_scope} matched old_text='{needle}'.")
        if len(matches) > 1:
            raise ValueError(
                f"old_text='{needle}' matched {len(matches)} entries; provide a more specific span."
            )
        matched = matches[0]
        if act == "remove":
            self.delete_entry(matched.id)
            return {"ok": True, "action": "remove", "removed_id": matched.id}
        if act == "patch":
            if matched.content.count(needle) > 1 and matched.content != needle:
                raise ValueError("old_text appears more than once in the matched entry.")
            replacement = matched.content.replace(needle, str(content or "").strip(), 1)
            updated = self.update_entry(matched.id, content=replacement, tags=tags)
            return {
                "ok": True,
                "action": "patch",
                "entry": updated.model_dump(mode="json", by_alias=True) if updated else None,
            }
        raise ValueError(f"Unsupported memory action '{action}'. Use add, patch, or remove.")

    def count_scope_memories(self, scope: str) -> int:
        norm = normalize_scope(scope)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM memory_entries WHERE scope = ? AND status = 'active'",
                (norm,),
            ).fetchone()
        return int(row[0]) if row else 0

    def get_scope_cookbook(self, scope: str) -> str:
        norm = normalize_scope(scope)
        settings = load_memory_settings()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cookbook_id FROM scope_cookbooks WHERE scope = ?", (norm,)
            ).fetchone()
        if row and row["cookbook_id"]:
            return str(row["cookbook_id"])
        if norm in {"global", "user"}:
            return settings.global_cookbook
        return settings.default_cookbook

    def set_scope_cookbook(self, scope: str, cookbook_id: str) -> str:
        norm = normalize_scope(scope)
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scope_cookbooks(scope, cookbook_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(scope) DO UPDATE SET cookbook_id = excluded.cookbook_id, updated_at = excluded.updated_at
                """,
                (norm, cookbook_id, now),
            )
        return cookbook_id

    def get_specialist_persona(self, specialist_id: str, slug: str = "") -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM specialist_personas WHERE specialist_id = ? OR (slug != '' AND slug = ?)",
                (specialist_id, slug),
            ).fetchone()
        if not row:
            return {}
        return {
            "role_label": row["role_label"],
            "avatar_url": row["avatar_url"],
            "provider": row["provider"],
            "model": row["model"],
            "openai_profile_id": row["openai_profile_id"],
            "cookbook_id": row["cookbook_id"],
            "priors": row["priors"],
        }

    def upsert_specialist_persona(
        self,
        specialist_id: str,
        *,
        slug: str = "",
        role_label: str | None = None,
        avatar_url: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        openai_profile_id: str | None = None,
        clear_llm: bool = False,
        cookbook_id: str | None = None,
        priors: str | None = None,
        clear_priors: bool = False,
    ) -> dict[str, Any]:
        cur = self.get_specialist_persona(specialist_id, slug)
        next_role = cur.get("role_label") if role_label is None else ((role_label or "").strip() or None)
        next_avatar = cur.get("avatar_url") if avatar_url is None else ((avatar_url or "").strip() or None)
        if clear_llm:
            next_prov = None
            next_mod = None
            next_prof = None
        else:
            next_prov = cur.get("provider") if provider is None else ((provider or "").strip() or None)
            next_mod = cur.get("model") if model is None else ((model or "").strip() or None)
            next_prof = (
                cur.get("openai_profile_id")
                if openai_profile_id is None
                else ((openai_profile_id or "").strip() or None)
            )
        next_cb = cur.get("cookbook_id") if cookbook_id is None else ((cookbook_id or "").strip() or None)
        if clear_priors:
            next_priors = None
        else:
            next_priors = cur.get("priors") if priors is None else ((priors or "").strip() or None)
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO specialist_personas(
                    specialist_id, slug, role_label, avatar_url, provider, model,
                    openai_profile_id, cookbook_id, priors, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(specialist_id) DO UPDATE SET
                    slug = excluded.slug,
                    role_label = excluded.role_label,
                    avatar_url = excluded.avatar_url,
                    provider = excluded.provider,
                    model = excluded.model,
                    openai_profile_id = excluded.openai_profile_id,
                    cookbook_id = excluded.cookbook_id,
                    priors = excluded.priors,
                    updated_at = excluded.updated_at
                """,
                (
                    specialist_id,
                    slug,
                    next_role,
                    next_avatar,
                    next_prov,
                    next_mod,
                    next_prof,
                    next_cb,
                    next_priors,
                    now,
                ),
            )
        return self.get_specialist_persona(specialist_id, slug)


def search_past_sessions(
    agent_store: Any,
    query: str,
    *,
    project_id: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fast full-text search across past session messages (Hermes session_search pattern)."""
    needle = str(query or "").strip()
    if not needle or agent_store is None:
        return []
    capped = max(1, min(int(limit), 30))
    sessions = agent_store.search_sessions(needle, limit=capped)
    results: list[dict[str, Any]] = []
    lowered = needle.lower()
    for sess in sessions:
        if project_id and getattr(sess, "project_id", None) != project_id:
            continue
        messages = agent_store.list_messages(sess.id)
        matching_snippets: list[str] = []
        for msg in messages:
            text = str(getattr(msg, "content", "") or "")
            idx = text.lower().find(lowered)
            if idx != -1:
                start = max(0, idx - 80)
                end = min(len(text), idx + len(needle) + 140)
                snippet = text[start:end].replace("\n", " ").strip()
                matching_snippets.append(f"[{msg.role}] {snippet}")
                if len(matching_snippets) >= 3:
                    break
        results.append(
            {
                "session_id": sess.id,
                "title": sess.title,
                "project_id": getattr(sess, "project_id", None),
                "updated_at": sess.updated_at.isoformat()
                if hasattr(sess.updated_at, "isoformat")
                else str(sess.updated_at),
                "snippets": matching_snippets,
            }
        )
    return results[:capped]
