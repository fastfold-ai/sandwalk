"""Library content-addressed store, filters, materialize, and GC."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_server.app import create_app
from agent_server.library.blobs import LibraryBlobStore
from agent_server.library.kind import library_kind_for_name
from agent_server.library.service import LibraryService
from agent_server.service import AgentService
from agent_server.store import AgentStore


def test_library_kind_mapping() -> None:
    assert library_kind_for_name("photo.PNG") == "image"
    assert library_kind_for_name("notes.pdf") == "document"
    assert library_kind_for_name("model.cif") == "structure"
    assert library_kind_for_name("script.py") == "code"
    assert library_kind_for_name("archive.zip") == "other"


def test_blob_dedup_and_hardlink_materialize(tmp_path: Path) -> None:
    blobs = LibraryBlobStore(tmp_path / "library")
    data = b"hello library"
    sha_a, size_a = blobs.put_bytes(data)
    sha_b, size_b = blobs.put_bytes(data)
    assert sha_a == sha_b
    assert size_a == size_b == len(data)
    assert list((tmp_path / "library" / "blobs").iterdir()) == [
        blobs.path_for(sha_a)
    ]

    dest = tmp_path / "uploads" / "hello.txt"
    blobs.materialize(sha_a, dest)
    assert dest.read_bytes() == data
    # Prefer hardlink when same volume (inode match).
    assert dest.stat().st_ino == blobs.path_for(sha_a).stat().st_ino


def test_library_service_filter_rename_delete_gc(tmp_path: Path) -> None:
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    service = AgentService(store)
    library = LibraryService(
        store,
        service,
        blobs=LibraryBlobStore(tmp_path / "library"),
    )

    pdf = library.ingest_bytes(
        b"%PDF-1.4 demo",
        filename="report.pdf",
        origin_session_id=None,
    )
    py = library.ingest_bytes(
        b"print('hi')",
        filename="run.py",
    )
    assert pdf.kind == "document"
    assert py.kind == "code"

    docs = library.list_items(kind="document")
    assert [item.id for item in docs.data] == [pdf.id]
    codes = library.list_items(query="run")
    assert [item.id for item in codes.data] == [py.id]

    renamed = library.rename(pdf.id, "Quarterly.pdf")
    assert renamed is not None
    assert renamed.display_name == "Quarterly.pdf"

    # Same bytes again → one blob, two items.
    pdf2 = library.ingest_bytes(b"%PDF-1.4 demo", filename="copy.pdf")
    assert pdf2.sha256 == pdf.sha256
    assert library.blobs.exists(pdf.sha256)

    assert library.delete(pdf.id) is True
    assert library.blobs.exists(pdf.sha256)  # still referenced by pdf2
    assert library.delete(pdf2.id) is True
    assert not library.blobs.exists(pdf.sha256)  # GC


def test_use_in_chat_materializes_uploads(tmp_path: Path) -> None:
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    service = AgentService(store)
    library = LibraryService(
        store,
        service,
        blobs=LibraryBlobStore(tmp_path / "library"),
    )
    item = library.ingest_bytes(b"structure data", filename="protein.cif")
    result = library.use_in_chat([item.id], title="From library")
    session = store.get_session(result.session_id)
    assert session is not None
    assert session.workspace_path
    assert result.paths == ["uploads/protein.cif"]
    materialized = Path(session.workspace_path) / result.paths[0]
    assert materialized.read_bytes() == b"structure data"


def test_library_http_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        upload = client.post(
            "/v1/library/upload",
            files={"file": ("notes.md", b"# hello", "text/markdown")},
        )
        assert upload.status_code == 201
        item = upload.json()
        assert item["kind"] == "document"
        assert item["displayName"] == "notes.md"
        assert item["originalName"] == "notes.md"

        listed = client.get("/v1/library", params={"kind": "document"})
        assert listed.status_code == 200
        listed_body = listed.json()
        assert len(listed_body["data"]) == 1
        assert listed_body["pagination"]["total"] == 1
        assert listed_body["pagination"]["page"] == 0
        assert listed_body["pagination"]["hasMore"] is False

        renamed = client.patch(
            f"/v1/library/{item['id']}",
            json={"displayName": "readme.md"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["displayName"] == "readme.md"

        content = client.get(f"/v1/library/{item['id']}/content")
        assert content.status_code == 200
        assert content.content == b"# hello"

        file_payload = client.get(f"/v1/library/{item['id']}/file")
        assert file_payload.status_code == 200
        assert file_payload.json()["encoding"] == "text"
        assert file_payload.json()["content"] == "# hello"

        written = client.put(
            f"/v1/library/{item['id']}/content",
            json={"content": "# updated\n", "encoding": "text"},
        )
        assert written.status_code == 200
        assert written.json()["content"] == "# updated\n"
        assert client.get(f"/v1/library/{item['id']}/content").content == b"# updated\n"

        used = client.post(
            "/v1/library/use-in-chat",
            json={"itemIds": [item["id"]], "title": "Lib chat"},
        )
        assert used.status_code == 200
        body = used.json()
        assert body["sessionId"]
        assert body["paths"] == ["uploads/readme.md"]

        deleted = client.delete(f"/v1/library/{item['id']}")
        assert deleted.status_code == 200
        assert client.get("/v1/library").json()["data"] == []


def test_session_upload_ingests_into_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        session = client.post("/v1/sessions", json={"title": "Chat"}).json()
        uploaded = client.post(
            f"/v1/sessions/{session['id']}/files/upload",
            files={"file": ("data.csv", b"a,b\n1,2\n", "text/csv")},
        )
        assert uploaded.status_code == 200
        library = client.get("/v1/library", params={"kind": "document"}).json()
        assert len(library["data"]) == 1
        assert library["data"][0]["originalName"] == "data.csv"
        assert library["data"][0]["originSessionId"] == session["id"]


def test_library_list_filters_by_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        project_a = client.post("/v1/projects", json={"name": "Alpha"}).json()
        project_b = client.post("/v1/projects", json={"name": "Beta"}).json()
        session_a = client.post(
            "/v1/sessions",
            json={"title": "A chat", "projectId": project_a["id"]},
        ).json()
        session_b = client.post(
            "/v1/sessions",
            json={"title": "B chat", "projectId": project_b["id"]},
        ).json()
        client.post(
            f"/v1/sessions/{session_a['id']}/files/upload",
            files={"file": ("a.txt", b"alpha", "text/plain")},
        )
        client.post(
            f"/v1/sessions/{session_b['id']}/files/upload",
            files={"file": ("b.txt", b"beta", "text/plain")},
        )

        all_items = client.get("/v1/library").json()
        assert all_items["pagination"]["total"] == 2

        scoped = client.get(
            "/v1/library", params={"projectId": project_a["id"]}
        ).json()
        assert scoped["pagination"]["total"] == 1
        assert scoped["data"][0]["originalName"] == "a.txt"
        assert scoped["data"][0]["originSessionId"] == session_a["id"]


def test_backfill_indexes_existing_workspace_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    service = AgentService(store)
    library = LibraryService(
        store,
        service,
        blobs=LibraryBlobStore(tmp_path / "library"),
    )
    session = service.create_session(title="Old chat", workspace_path=None)
    root = Path(session.workspace_path or "")
    (root / "uploads" / "legacy.pdf").write_bytes(b"%PDF-legacy")
    (root / "outputs" / "result.cif").write_text("data_legacy\n", encoding="utf-8")

    # First list triggers one-time workspace backfill.
    listed = library.list_items(per_page=50)
    names = {item.original_name for item in listed.data}
    assert "legacy.pdf" in names
    assert "result.cif" in names
    assert listed.pagination.total >= 2
    assert listed.pagination.page == 0

    sync = library.sync_from_workspaces()
    assert sync.ingested == 0
    assert sync.linked >= 2


def test_library_pagination(tmp_path: Path) -> None:
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    service = AgentService(store)
    library = LibraryService(
        store,
        service,
        blobs=LibraryBlobStore(tmp_path / "library"),
    )
    for index in range(5):
        library.ingest_bytes(
            f"page-body-{index}".encode(),
            filename=f"file-{index}.txt",
        )
    first = library.list_items(page=0, per_page=2)
    assert len(first.data) == 2
    assert first.pagination.total == 5
    assert first.pagination.has_more is True
    second = library.list_items(page=1, per_page=2)
    assert len(second.data) == 2
    assert second.pagination.has_more is True
    third = library.list_items(page=2, per_page=2)
    assert len(third.data) == 1
    assert third.pagination.has_more is False
    ids = {item.id for item in [*first.data, *second.data, *third.data]}
    assert len(ids) == 5
