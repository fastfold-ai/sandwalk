"""SQLite persistence for locally registered static sites."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from urllib.parse import urlparse

from agent_server.models.sites import Site, SiteDeployment
from agent_server.store.util import utc_now


def _site(row: sqlite3.Row) -> Site:
    published = datetime.fromisoformat(row["published_at"]) if row["published_at"] else None
    host = urlparse(row["cloud_url"]).hostname if row["cloud_url"] else None
    slug = host.split(".", 1)[0] if host and "." in host else None
    deployment = (
        SiteDeployment(
            id=row["cloud_site_id"] or row["id"],
            status="published",
            slug=slug or "",
            public_url=row["cloud_url"],
            size_bytes=int(row["bytes"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            published_at=published,
        )
        if row["cloud_url"]
        else None
    )
    return Site(
        id=row["id"],
        name=row["name"],
        slug=slug,
        status="published" if deployment else "ready",
        source_session_id=row["origin_session_id"],
        source_project_id=row["origin_project_id"],
        source_path=row["source_path"],
        origin_session_id=row["origin_session_id"],
        origin_project_id=row["origin_project_id"],
        storage_path=row["storage_path"],
        content_sha256=row["content_sha256"],
        file_count=int(row["file_count"]),
        bytes=int(row["bytes"]),
        size_bytes=int(row["bytes"]),
        cloud_site_id=row["cloud_site_id"],
        cloud_url=row["cloud_url"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        deployment=deployment,
        published_at=published,
    )


class SiteMixin:
    def create_site(
        self,
        *,
        name: str,
        source_path: str,
        storage_path: str,
        content_sha256: str,
        file_count: int,
        bytes_count: int,
        origin_session_id: str | None = None,
        origin_project_id: str | None = None,
        site_id: str | None = None,
    ) -> Site:
        now = utc_now().isoformat()
        normalized_id = site_id or str(uuid.uuid4())
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sites(
                    id, name, source_path, origin_session_id, origin_project_id,
                    storage_path, content_sha256, file_count, bytes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_id,
                    name,
                    source_path,
                    origin_session_id,
                    origin_project_id,
                    storage_path,
                    content_sha256,
                    file_count,
                    bytes_count,
                    now,
                    now,
                ),
            )
        result = self.get_site(normalized_id)
        if result is None:
            raise RuntimeError("Failed to persist site.")
        return result

    def get_site(self, site_id: str) -> Site | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone()
        return _site(row) if row is not None else None

    def list_sites(self) -> list[Site]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sites ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [_site(row) for row in rows]

    def update_site_content(
        self,
        site_id: str,
        *,
        source_path: str,
        storage_path: str,
        content_sha256: str,
        file_count: int,
        bytes_count: int,
        origin_session_id: str | None,
        origin_project_id: str | None,
    ) -> Site | None:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sites
                SET source_path = ?, storage_path = ?, content_sha256 = ?,
                    file_count = ?, bytes = ?, origin_session_id = ?,
                    origin_project_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    source_path,
                    storage_path,
                    content_sha256,
                    file_count,
                    bytes_count,
                    origin_session_id,
                    origin_project_id,
                    utc_now().isoformat(),
                    site_id,
                ),
            )
        return self.get_site(site_id) if cursor.rowcount else None

    def rename_site(self, site_id: str, name: str) -> Site | None:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE sites SET name = ?, updated_at = ? WHERE id = ?",
                (name, utc_now().isoformat(), site_id),
            )
        return self.get_site(site_id) if cursor.rowcount else None

    def mark_site_published(
        self,
        site_id: str,
        *,
        cloud_site_id: str | None,
        cloud_url: str,
    ) -> Site | None:
        now = utc_now().isoformat()
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sites
                SET cloud_site_id = ?, cloud_url = ?, published_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (cloud_site_id, cloud_url, now, now, site_id),
            )
        return self.get_site(site_id) if cursor.rowcount else None

    def delete_site(self, site_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM sites WHERE id = ?", (site_id,))
        return cursor.rowcount > 0
