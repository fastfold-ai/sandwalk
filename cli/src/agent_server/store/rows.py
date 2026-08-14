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
    MessageSource,
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
    raw_origin = row["source"] if "source" in keys else None
    origin = str(raw_origin or "").strip().lower() or None
    if origin not in {"slack", "bench", None}:
        origin = None
    raw_surface = row["client_surface"] if "client_surface" in keys else "unknown"
    surface = str(raw_surface or "unknown").strip().lower()
    if surface not in {"cli", "ui", "slack", "unknown"}:
        surface = "slack" if origin == "slack" else "unknown"
    raw_provider = row["provider"] if "provider" in keys else None
    raw_model = row["model"] if "model" in keys else None
    raw_profile = row["openai_profile_id"] if "openai_profile_id" in keys else None
    return AgentSession(
        id=row["id"],
        title=row["title"],
        title_source=title_source,  # type: ignore[arg-type]
        status=row["status"],
        organize_label=row["organize_label"],
        project_id=row["project_id"] if "project_id" in keys else None,
        specialist_id=row["specialist_id"] if "specialist_id" in keys else None,
        sandbox_backend=sandbox_backend,
        provider=(str(raw_provider).strip() or None) if raw_provider else None,
        model=(str(raw_model).strip() or None) if raw_model else None,
        openai_profile_id=(str(raw_profile).strip() or None) if raw_profile else None,
        workspace_path=row["workspace_path"],
        source=origin,  # type: ignore[arg-type]
        source_label=(row["source_label"] if "source_label" in keys else None),
        client_surface=surface,  # type: ignore[arg-type]
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
    from agent_server.widget_layout import parse_layout

    keys = set(row.keys())
    raw_layout = row["home_layout"] if "home_layout" in keys else None
    return AgentProject(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        agent_context=row["agent_context"],
        folder_path=row["folder_path"] if "folder_path" in keys else None,
        icon=(row["icon"] if "icon" in keys and row["icon"] else "folder"),
        color=(row["color"] if "color" in keys and row["color"] else "neutral"),
        pinned=bool(row["pinned"]),
        home_layout=parse_layout(
            None if raw_layout is None else str(raw_layout)
        ),
        session_count=session_count,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def message_from_row(row: sqlite3.Row) -> AgentMessage:
    keys = set(row.keys())
    source = None
    raw = row["metadata"] if "metadata" in keys else None
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                source = MessageSource.model_validate(parsed)
        except (ValueError, TypeError):
            # A display sidecar is never worth failing a message read over.
            source = None
    return AgentMessage(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        source=source,
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
