"""Local static-site validation, promotion, preview, and publishing."""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent.config import CONFIG_DIR
from agent_server.models.sites import Site
from agent_server.sites_service.cloud import FastFoldSitesClient, SitesPublisher
from agent_server.store import AgentStore

PREVIEW_TTL_SECONDS = 300
MAX_SITE_BYTES = 100 * 1024 * 1024
MAX_SITE_FILES = 5_000
SECRET_PARTS = {
    ".env",
    ".git",
    ".npmrc",
    ".ssh",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
}


@dataclass(frozen=True)
class SiteContent:
    root: Path
    sha256: str
    file_count: int
    bytes: int


class SitesService:
    def __init__(
        self,
        store: AgentStore,
        *,
        root: Path | None = None,
        public_base_url: str = "http://127.0.0.1:8787",
        publisher: SitesPublisher | None = None,
        preview_ttl: int = PREVIEW_TTL_SECONDS,
    ) -> None:
        self.store = store
        self.root = (root or (CONFIG_DIR / "sites")).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_base_url = public_base_url.rstrip("/")
        self.publisher = publisher
        self.preview_ttl = preview_ttl
        self._tokens: dict[str, tuple[str, datetime]] = {}
        self._token_lock = threading.Lock()

    @staticmethod
    def _name(name: str) -> str:
        value = str(name or "").strip()
        if not value:
            raise ValueError("Site name cannot be empty.")
        if len(value) > 100:
            raise ValueError("Site name cannot exceed 100 characters.")
        return value

    def _allowed_roots(
        self,
        *,
        session_id: str | None,
        project_id: str | None,
        workspace_root: Path | None,
    ) -> list[Path]:
        roots: list[Path] = []
        if workspace_root is not None:
            roots.append(workspace_root.expanduser().resolve(strict=True))
        session = self.store.get_session(session_id) if session_id else None
        if session_id and session is None:
            raise ValueError("Session not found.")
        if session is not None:
            if not session.workspace_path:
                raise ValueError("Session has no workspace.")
            roots.append(Path(session.workspace_path).expanduser().resolve(strict=True))
        project = self.store.get_project(project_id) if project_id else None
        if project_id and project is None:
            raise ValueError("Project not found.")
        if project is not None:
            if not project.folder_path:
                raise ValueError("Project has no folder path.")
            roots.append(Path(project.folder_path).expanduser().resolve(strict=True))
        if session is not None and project_id and session.project_id != project_id:
            raise ValueError("Session does not belong to the specified project.")
        if not roots:
            raise ValueError("A session workspace or project folder is required.")
        return list(dict.fromkeys(roots))

    def resolve_source(
        self,
        source: str | Path,
        *,
        session_id: str | None = None,
        project_id: str | None = None,
        workspace_root: Path | None = None,
    ) -> Path:
        roots = self._allowed_roots(
            session_id=session_id,
            project_id=project_id,
            workspace_root=workspace_root,
        )
        raw = Path(source).expanduser()
        candidate = raw if raw.is_absolute() else roots[0] / raw
        resolved = candidate.resolve(strict=True)
        if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
            raise ValueError("Site path must stay within the session workspace or project folder.")
        if resolved == self.root or resolved.is_relative_to(self.root):
            raise ValueError("A site cannot be registered from Sandwalk's managed site storage.")
        return resolved

    @staticmethod
    def validate(root: Path) -> SiteContent:
        if not root.is_dir():
            raise ValueError("Site path must be a directory.")
        index = root / "index.html"
        if not index.is_file() or index.is_symlink():
            raise ValueError("Site output must contain a regular index.html file.")
        digest = hashlib.sha256()
        count = 0
        size = 0
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
            if path.is_symlink():
                raise ValueError(f"Site output cannot contain symlinks: {path.relative_to(root)}")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            parts = Path(relative).parts
            if any(part.startswith(".") or part.lower() in SECRET_PARTS for part in parts):
                raise ValueError(f"Site output cannot contain hidden or secret files: {relative}")
            data = path.read_bytes()
            digest.update(relative.encode())
            digest.update(b"\0")
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
            count += 1
            size += len(data)
            if count > MAX_SITE_FILES:
                raise ValueError(f"Site output cannot contain more than {MAX_SITE_FILES} files.")
            if size > MAX_SITE_BYTES:
                raise ValueError("Site output cannot exceed 100 MB.")
        return SiteContent(root=root, sha256=digest.hexdigest(), file_count=count, bytes=size)

    def _promote(self, source: Path, site_id: str) -> tuple[SiteContent, Path, Path | None]:
        stage = self.root / f".staging-{site_id}-{secrets.token_hex(6)}"
        target = self.root / site_id
        backup = self.root / f".backup-{site_id}-{secrets.token_hex(6)}"
        try:
            shutil.copytree(source, stage)
            content = self.validate(stage)
            previous = backup if target.exists() else None
            if previous is not None:
                os.replace(target, previous)
            os.replace(stage, target)
            return content, target, previous
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            if backup.exists() and not target.exists():
                os.replace(backup, target)
            raise

    def register(
        self,
        *,
        name: str,
        source: str | Path,
        session_id: str | None = None,
        project_id: str | None = None,
        workspace_root: Path | None = None,
        site_id: str | None = None,
    ) -> Site:
        normalized_name = self._name(name)
        source_path = self.resolve_source(
            source,
            session_id=session_id,
            project_id=project_id,
            workspace_root=workspace_root,
        )
        self.validate(source_path)
        current = self.store.get_site(site_id) if site_id else None
        if site_id and current is None:
            raise KeyError("Site not found.")
        next_id = current.id if current else secrets.token_hex(16)
        content, target, backup = self._promote(source_path, next_id)
        try:
            if current is None:
                result = self.store.create_site(
                    site_id=next_id,
                    name=normalized_name,
                    source_path=str(source_path),
                    storage_path=str(target),
                    content_sha256=content.sha256,
                    file_count=content.file_count,
                    bytes_count=content.bytes,
                    origin_session_id=session_id,
                    origin_project_id=project_id,
                )
            else:
                if normalized_name != current.name:
                    self.store.rename_site(next_id, normalized_name)
                result = self.store.update_site_content(
                    next_id,
                    source_path=str(source_path),
                    storage_path=str(target),
                    content_sha256=content.sha256,
                    file_count=content.file_count,
                    bytes_count=content.bytes,
                    origin_session_id=session_id,
                    origin_project_id=project_id,
                )
                if result is None:
                    raise RuntimeError("Failed to update site.")
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            if backup is not None and backup.exists():
                os.replace(backup, target)
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
        return result

    def rename(self, site_id: str, name: str) -> Site:
        result = self.store.rename_site(site_id, self._name(name))
        if result is None:
            raise KeyError("Site not found.")
        return result

    def delete(self, site_id: str) -> None:
        site = self.store.get_site(site_id)
        if site is None:
            raise KeyError("Site not found.")
        target = Path(site.storage_path)
        trash = self.root / f".deleting-{site_id}-{secrets.token_hex(6)}"
        if target.exists():
            os.replace(target, trash)
        if not self.store.delete_site(site_id):
            if trash.exists():
                os.replace(trash, target)
            raise KeyError("Site not found.")
        shutil.rmtree(trash, ignore_errors=True)
        with self._token_lock:
            self._tokens = {
                token: value for token, value in self._tokens.items() if value[0] != site_id
            }

    def create_preview(self, site_id: str) -> tuple[str, datetime]:
        if self.store.get_site(site_id) is None:
            raise KeyError("Site not found.")
        token = secrets.token_urlsafe(24)
        expires = datetime.now(UTC) + timedelta(seconds=self.preview_ttl)
        with self._token_lock:
            self._tokens[token] = (site_id, expires)
        return (
            f"{self.public_base_url}/v1/sites/{site_id}/preview/{token}/",
            expires,
        )

    def preview_site(self, site_id: str, token: str) -> Site | None:
        now = datetime.now(UTC)
        with self._token_lock:
            self._tokens = {
                key: value for key, value in self._tokens.items() if value[1] > now
            }
            value = self._tokens.get(token)
        if value is None or value[0] != site_id:
            return None
        return self.store.get_site(site_id)

    def publish(self, site_id: str, *, slug: str | None = None) -> Site:
        site = self.store.get_site(site_id)
        if site is None:
            raise KeyError("Site not found.")
        content = self.validate(Path(site.storage_path))
        if content.sha256 != site.content_sha256:
            raise ValueError("Managed site content changed; update the site before publishing.")
        publisher = self.publisher or FastFoldSitesClient()
        with tempfile.TemporaryDirectory(prefix="sandwalk-site-") as directory:
            artifact = Path(directory) / "site.zip"
            with zipfile.ZipFile(
                artifact,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                for path in sorted(content.root.rglob("*")):
                    if path.is_file():
                        relative = path.relative_to(content.root).as_posix()
                        info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                        info.compress_type = zipfile.ZIP_DEFLATED
                        info.external_attr = 0o100644 << 16
                        archive.writestr(info, path.read_bytes())
            archive_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
            published = publisher.publish(
                artifact=artifact,
                name=site.name,
                local_site_id=site.id,
                content_sha256=archive_sha256,
                expanded_size_bytes=content.bytes,
                file_count=content.file_count,
                slug=slug,
                cloud_site_id=site.cloud_site_id,
            )
        result = self.store.mark_site_published(
            site.id,
            cloud_site_id=published.site_id,
            cloud_url=published.url,
        )
        if result is None:
            raise RuntimeError("Site was published but local metadata could not be updated.")
        return result
