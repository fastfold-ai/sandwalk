from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from agent_server.sites_service.cloud import PublishedSite
from agent_server.sites_service.core import SitesService
from agent_server.store import AgentStore


class Publisher:
    def __init__(self) -> None:
        self.files: list[str] = []
        self.deleted: list[str] = []

    def publish(self, *, artifact: Path, **kwargs):
        with zipfile.ZipFile(artifact) as archive:
            self.files = archive.namelist()
        assert kwargs["expanded_size_bytes"] > 0
        assert kwargs["file_count"] == 2
        return PublishedSite(url="https://example.sandwalk.site", site_id="cloud-site")

    def delete(self, site_id: str) -> None:
        self.deleted.append(site_id)


def test_local_site_lifecycle(tmp_path):
    source = tmp_path / "workspace" / "dist"
    source.mkdir(parents=True)
    (source / "index.html").write_text("<h1>Site</h1>", encoding="utf-8")
    (source / "app.js").write_text("console.log('site')", encoding="utf-8")
    store = AgentStore(tmp_path / "agent.db")
    publisher = Publisher()
    service = SitesService(store, root=tmp_path / "managed", publisher=publisher)
    try:
        site = service.register(
            name="Example",
            source=source,
            workspace_root=tmp_path / "workspace",
        )
        assert site.status == "ready"
        assert Path(site.storage_path, "index.html").is_file()

        url, _ = service.create_preview(site.id)
        token = url.rstrip("/").rsplit("/", 1)[-1]
        route_service = SitesService(store, root=tmp_path / "managed")
        assert route_service.preview_site(site.id, token) is not None

        published = service.publish(site.id)
        assert published.status == "published"
        assert published.slug == "example"
        assert publisher.files == ["app.js", "index.html"]

        (source / "index.html").write_text("<h1>Updated site</h1>", encoding="utf-8")
        updated = service.register(
            site_id=site.id,
            name=site.name,
            source=source,
            workspace_root=tmp_path / "workspace",
        )
        assert updated.id == site.id
        assert updated.status == "ready"
        assert updated.cloud_site_id == "cloud-site"
        assert updated.cloud_url is None
        assert updated.published_at is None

        service.delete(site.id)
        assert publisher.deleted == ["cloud-site"]
        assert store.get_site(site.id) is None
    finally:
        store.close()


@pytest.mark.parametrize("relative", [".env", "private-key.pem", "assets/api_key.txt"])
def test_local_site_rejects_hidden_and_secret_files(tmp_path, relative):
    source = tmp_path / "workspace" / "dist"
    source.mkdir(parents=True)
    (source / "index.html").write_text("<h1>Site</h1>", encoding="utf-8")
    target = source / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("SECRET=value", encoding="utf-8")
    store = AgentStore(tmp_path / "agent.db")
    service = SitesService(store, root=tmp_path / "managed")
    try:
        with pytest.raises(ValueError, match="hidden or secret"):
            service.register(
                name="Example",
                source=source,
                workspace_root=tmp_path / "workspace",
            )
    finally:
        store.close()
