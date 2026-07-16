"""MCP server registry CRUD."""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any, Literal, cast

from agent_server.models import McpServer
from agent_server.store.rows import mcp_server_from_row
from agent_server.store.util import utc_now


class McpServerMixin:
    @staticmethod
    def _mcp_server(row: sqlite3.Row) -> McpServer:
        return mcp_server_from_row(row)

    def list_mcp_servers(self, *, enabled_only: bool = False) -> list[McpServer]:
        query = "SELECT * FROM mcp_servers"
        params: tuple[Any, ...] = ()
        if enabled_only:
            query += " WHERE enabled = ?"
            params = (1,)
        query += " ORDER BY name COLLATE NOCASE, id"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [mcp_server_from_row(row) for row in rows]

    def create_mcp_server(
        self,
        *,
        name: str,
        transport: str,
        command: str | None,
        args: list[str],
        url: str | None,
        enabled: bool,
        catalog_id: str | None = None,
        description: str | None = None,
        oauth_client_id: str | None = None,
        oauth_server_url: str | None = None,
        oauth_scopes: str | None = None,
        headers_helper_command: str | None = None,
    ) -> McpServer:
        now = utc_now()
        transport_lit = cast(Literal["stdio", "sse", "streamable_http"], transport)
        server = McpServer(
            id=str(uuid.uuid4()),
            name=name.strip(),
            transport=transport_lit,
            command=command.strip() if command else None,
            args=args,
            url=url.strip() if url else None,
            enabled=enabled,
            catalog_id=catalog_id.strip() if catalog_id else None,
            description=description.strip() if description else None,
            oauth_client_id=oauth_client_id.strip() if oauth_client_id else None,
            oauth_server_url=oauth_server_url.strip() if oauth_server_url else None,
            oauth_scopes=oauth_scopes.strip() if oauth_scopes else None,
            headers_helper_command=(
                headers_helper_command.strip() if headers_helper_command else None
            ),
            created_at=now,
            updated_at=now,
        )
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO mcp_servers(
                    id, name, transport, command, args, url, enabled, catalog_id,
                    description, oauth_client_id, oauth_server_url, oauth_scopes,
                    headers_helper_command, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    server.id,
                    server.name,
                    server.transport,
                    server.command,
                    json.dumps(server.args),
                    server.url,
                    int(server.enabled),
                    server.catalog_id,
                    server.description,
                    server.oauth_client_id,
                    server.oauth_server_url,
                    server.oauth_scopes,
                    server.headers_helper_command,
                    server.created_at.isoformat(),
                    server.updated_at.isoformat(),
                ),
            )
        return server

    def update_mcp_server(self, server_id: str, **changes: Any) -> McpServer | None:
        current = next(
            (server for server in self.list_mcp_servers() if server.id == server_id),
            None,
        )
        if current is None:
            return None
        data = current.model_dump()
        for key, value in changes.items():
            if key in data:
                data[key] = value
        data["updated_at"] = utc_now()
        # Response-only fields — never persist from callers.
        data.pop("header_names", None)
        data.pop("headers_configured", None)
        server = McpServer(**data)
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE mcp_servers
                SET name = ?, command = ?, args = ?, url = ?, enabled = ?,
                    catalog_id = ?, description = ?, oauth_client_id = ?,
                    oauth_server_url = ?, oauth_scopes = ?,
                    headers_helper_command = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    server.name,
                    server.command,
                    json.dumps(server.args),
                    server.url,
                    int(server.enabled),
                    server.catalog_id,
                    server.description,
                    server.oauth_client_id,
                    server.oauth_server_url,
                    server.oauth_scopes,
                    server.headers_helper_command,
                    server.updated_at.isoformat(),
                    server.id,
                ),
            )
        return server

    def delete_mcp_server(self, server_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM mcp_servers WHERE id = ?", (server_id,))
        return cursor.rowcount > 0
