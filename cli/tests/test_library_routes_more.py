"""Coverage for library routes and builtin tool-schema measurement."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.deepagents_runtime.prompt_budget import measure_deepagents_builtin_tool_schemas
from agent_server.models.library import (
    LibraryFileContent,
    LibraryItem,
    LibraryItemList,
    LibraryPagination,
    LibrarySyncResponse,
    UseLibraryInChatResponse,
)
from agent_server.routes.library import register_library_routes


def _item() -> LibraryItem:
    now = datetime.now(UTC)
    return LibraryItem(
        id="item-1",
        sha256="abc",
        bytes=4,
        mime="text/plain",
        original_name="note.txt",
        display_name="note.txt",
        kind="document",
        created_at=now,
        updated_at=now,
    )


def _file() -> LibraryFileContent:
    return LibraryFileContent(
        path="note.txt",
        content="hello",
        encoding="text",
        mime_type="text/plain",
        version="v1",
        size=5,
        mtime=datetime.now(UTC),
    )


def test_library_routes(tmp_path) -> None:
    item = _item()
    blob = tmp_path / "note.txt"
    blob.write_text("hello", encoding="utf-8")

    class Library:
        def list_items(self, **kwargs):
            return LibraryItemList(data=[item], pagination=LibraryPagination(), total_bytes=4)

        def sync_from_workspaces(self):
            return LibrarySyncResponse(scanned_sessions=1, ingested=1)

        def ingest_bytes(self, data, filename, mime):
            assert data == b"hello"
            return item

        def use_in_chat(self, item_ids, project_id=None, title=None):
            if item_ids == ["missing"]:
                raise KeyError("missing")
            if item_ids == ["bad"]:
                raise ValueError("bad")
            return UseLibraryInChatResponse(session_id="s1", paths=["note.txt"])

        def get_item(self, item_id):
            return None if item_id == "missing" else item

        def rename(self, item_id, display_name):
            if display_name == "bad":
                raise ValueError("bad")
            if item_id == "missing":
                return None
            return item

        def delete(self, item_id):
            return item_id != "missing"

        def content_path(self, item_id):
            return None if item_id == "noblob" else blob

        def read_file_content(self, item_id):
            return None if item_id == "missing" else _file()

        def write_content(self, item_id, data):
            if item_id == "missing":
                raise KeyError(item_id)
            if data == b"nope":
                raise ValueError("nope")

    app = FastAPI()
    register_library_routes(app, type("Deps", (), {"library_service": Library()})())
    client = TestClient(app)

    assert client.get("/v1/library", params={"kind": "document", "q": "note"}).status_code == 200
    assert client.post("/v1/library/sync").json()["ingested"] == 1
    uploaded = client.post(
        "/v1/library/upload",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert uploaded.status_code == 201
    assert client.post("/v1/library/use-in-chat", json={"item_ids": ["item-1"]}).status_code == 200
    assert client.post("/v1/library/use-in-chat", json={"item_ids": ["missing"]}).status_code == 404
    assert client.post("/v1/library/use-in-chat", json={"item_ids": ["bad"]}).status_code == 400
    assert client.get("/v1/library/item-1").status_code == 200
    assert client.get("/v1/library/missing").status_code == 404
    assert client.patch("/v1/library/item-1", json={"display_name": "renamed.txt"}).status_code == 200
    assert client.patch("/v1/library/item-1", json={"display_name": "bad"}).status_code == 400
    assert client.patch("/v1/library/missing", json={"display_name": "x"}).status_code == 404
    assert client.delete("/v1/library/item-1").status_code == 200
    assert client.delete("/v1/library/missing").status_code == 404
    assert client.get("/v1/library/item-1/content").status_code == 200
    assert client.get("/v1/library/noblob/content").status_code == 404
    assert client.get("/v1/library/item-1/file").status_code == 200
    assert client.get("/v1/library/missing/file").status_code == 404
    written = client.put(
        "/v1/library/item-1/content",
        json={"content": "aGVsbG8=", "encoding": "base64"},
    )
    assert written.status_code == 200
    assert client.put("/v1/library/item-1/content", json={"content": "!!!", "encoding": "base64"}).status_code == 400
    assert client.put("/v1/library/missing/content", json={"content": "hi"}).status_code == 404
    assert client.put("/v1/library/item-1/content", json={"content": "nope"}).status_code == 400


def test_builtin_tool_schema_measurement(tmp_path) -> None:
    text, names = measure_deepagents_builtin_tool_schemas(
        domain_tools=[],
        system_prompt="Budget",
        skills_sources=[],
        workspace_root=str(tmp_path / "ws"),
        include_domain_subagents=False,
        excluded_tools=frozenset({"task"}),
    )
    assert isinstance(text, str)
    assert isinstance(names, list)
