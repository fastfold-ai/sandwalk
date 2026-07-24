"""``sqlite3.Row`` → pydantic model mapping helpers."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from agent_server.models import (
    AgentMessage,
    AgentProject,
    AgentSession,
    McpServer,
    Specialist,
)
from agent_server.store.util import parse_sandbox_backend


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


def session_from_row(row: sqlite3.Row) -> AgentSession:
    keys = set(row.keys())
    raw_backend = row["sandbox_backend"] if "sandbox_backend" in keys else None
    sandbox_backend = parse_sandbox_backend(
        None if raw_backend is None else str(raw_backend)
    )
    raw_source = row["title_source"] if "title_source" in keys else "pending"
    title_source = str(raw_source or "pending").strip().lower()
    if title_source not in {"pending", "auto", "user"}:
        title_source = "pending"
    return AgentSession(
        id=row["id"],
        title=row["title"],
        title_source=title_source,  # type: ignore[arg-type]
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


def specialist_from_row(row: sqlite3.Row) -> Specialist:
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
        tool_names=_json_list(row["tool_names"] if "tool_names" in keys else "[]"),
        mcp_server_ids=_json_list(row["mcp_server_ids"]),
        mcp_catalog_ids=_json_list(
            row["mcp_catalog_ids"] if "mcp_catalog_ids" in keys else "[]"
        ),
        enabled=bool(row["enabled"]) if "enabled" in keys else True,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def project_from_row(row: sqlite3.Row, *, session_count: int = 0) -> AgentProject:
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


def message_from_row(row: sqlite3.Row) -> AgentMessage:
    return AgentMessage(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def mcp_server_from_row(row: sqlite3.Row) -> McpServer:
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
