"""Coverage for Llama runtime routes, Define-XML lint, and todo tools."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_server.routes.llama_runtime import register_llama_runtime_routes
from tools.ops_todo import todo_add, todo_delete, todo_get, todo_list, todo_update
from tools.regulatory_define_xml import define_xml_lint


def test_llama_runtime_routes_map_errors(monkeypatch) -> None:
    app = FastAPI()
    register_llama_runtime_routes(app, None)
    mod = "agent_server.routes.llama_runtime"
    monkeypatch.setattr(f"{mod}.status", lambda: {"running": False})
    monkeypatch.setattr(f"{mod}.ensure", lambda: {"phase": "ready"})
    monkeypatch.setattr(f"{mod}.publish_profile", lambda: None)
    monkeypatch.setattr(f"{mod}.catalog", lambda q: {"q": q, "models": []})
    monkeypatch.setattr(f"{mod}.memory_tiers", lambda model: {"model": model, "tiers": []})
    monkeypatch.setattr(f"{mod}.update_engine", lambda: {"phase": "idle"})
    monkeypatch.setattr(f"{mod}.load_model", lambda model: {"loaded": model})
    monkeypatch.setattr(f"{mod}.unload_model", lambda model: {"unloaded": model})
    monkeypatch.setattr(f"{mod}.set_context", lambda model, context: {"model": model, "context": context})
    monkeypatch.setattr(f"{mod}.install_model", lambda repo, quant: {"repo": repo, "quant": quant})
    monkeypatch.setattr(f"{mod}.remove_model", lambda model: {"removed": model})
    client = TestClient(app)

    assert client.get("/v1/local-runtimes/llama").json()["running"] is False
    assert client.post("/v1/local-runtimes/llama/ensure").json()["phase"] == "ready"
    assert client.get("/v1/local-runtimes/llama/catalog", params={"q": "gemma"}).json()["q"] == "gemma"
    assert client.get("/v1/local-runtimes/llama/memory", params={"model": "gemma"}).json()["model"] == "gemma"
    assert client.post("/v1/local-runtimes/llama/update").json()["phase"] == "idle"
    assert client.post("/v1/local-runtimes/llama/load", json={"model": "gemma"}).json()["loaded"] == "gemma"
    assert client.post("/v1/local-runtimes/llama/unload", json={"model": "gemma"}).json()["unloaded"] == "gemma"
    assert client.post(
        "/v1/local-runtimes/llama/context", json={"model": "gemma", "context": 4096}
    ).json()["context"] == 4096
    assert client.post(
        "/v1/local-runtimes/llama/install", json={"repo": "org/model", "quant": "Q4"}
    ).json()["quant"] == "Q4"
    assert client.post("/v1/local-runtimes/llama/remove", json={"model": "gemma"}).json()["removed"] == "gemma"

    def bad(*_args, **_kwargs):
        raise ValueError("no")

    for name in ("update_engine", "load_model", "unload_model", "set_context", "install_model", "remove_model"):
        monkeypatch.setattr(f"{mod}.{name}", bad)
    assert client.post("/v1/local-runtimes/llama/update").status_code == 400
    assert client.post("/v1/local-runtimes/llama/load", json={"model": "gemma"}).status_code == 400
    assert client.post("/v1/local-runtimes/llama/context", json={"model": "gemma", "context": 1}).status_code == 400
    assert client.post("/v1/local-runtimes/llama/install", json={"repo": "org/model"}).status_code == 400
    assert client.post("/v1/local-runtimes/llama/remove", json={"model": "gemma"}).status_code == 400

    def http_down(*_args, **_kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(f"{mod}.unload_model", http_down)
    assert client.post("/v1/local-runtimes/llama/unload", json={"model": "gemma"}).status_code == 502


def test_define_xml_lint_reports_structure_and_bad_refs(tmp_path: Path) -> None:
    assert define_xml_lint("")["error"] == "missing_define_xml_path"
    assert define_xml_lint(str(tmp_path / "missing.xml"))["error"] == "file_not_found"
    assert define_xml_lint(str(tmp_path))["error"] == "path_is_directory"

    broken = tmp_path / "bad.xml"
    broken.write_text("<ODM>", encoding="utf-8")
    assert define_xml_lint(str(broken))["error"] == "xml_parse_error"

    unreadable = tmp_path / "locked.xml"
    unreadable.write_text("<ODM/>", encoding="utf-8")

    def boom(_path):
        raise OSError("blocked")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("xml.etree.ElementTree.parse", boom)
    try:
        assert define_xml_lint(str(unreadable))["error"] == "read_failed"
    finally:
        monkeypatch.undo()

    xml = """
    <ODM>
      <Study/>
      <MetaDataVersion>
        <ItemGroupDef OID="IG" Name="G"/>
        <ItemGroupDef OID="IG" Name="G2"/>
        <ItemDef OID="IT" DataType="text"/>
        <ItemDef OID="IT"/>
        <ItemRef/>
        <ItemRef ItemOID="MISSING"/>
        <CodeList OID="CL"/>
        <CodeList OID="CL"/>
        <CodeListRef/>
        <CodeListRef CodeListOID="NOPE"/>
        <ValueListDef OID="VL"/>
        <ValueListRef/>
        <ValueListRef ValueListOID="NOPE"/>
        <WhereClauseDef OID="WH"/>
        <WhereClauseRef/>
        <WhereClauseRef WhereClauseOID="OTHER"/>
        <leaf href=""/>
      </MetaDataVersion>
    </ODM>
    """
    path = tmp_path / "define.xml"
    path.write_text(xml, encoding="utf-8")
    report = define_xml_lint(str(path), strict=True, max_issues=0)
    codes = {issue["code"] for issue in report["issues"]}
    assert "duplicate_itemdef_oid" in codes
    assert "itemdef_missing_name" in codes
    assert "itemref_missing_itemoid" in codes
    assert "codelistref_unknown_oid" in codes
    assert "valuelistref_unknown_oid" in codes
    assert "whereclauseref_unknown_oid" in codes
    assert "leaf_missing_href" in codes
    assert report["error_count"] >= 1


def test_todo_tools_cover_validation_and_persistence(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "todos.json"
    monkeypatch.setattr("tools.ops_todo._todos_path", lambda _session=None: path)

    assert todo_add("  ")["error"] == "missing_task"
    assert todo_add("ship", priority="urgent")["error"] == "invalid_priority"
    assert todo_add("ship", due_date="yesterday")["error"] == "invalid_due_date"
    path.write_text("{", encoding="utf-8")
    assert todo_add("ship")["error"] == "todo_db_error"
    path.write_text("{}", encoding="utf-8")
    assert todo_add("ship")["error"] == "todo_db_error"

    path.write_text("[]", encoding="utf-8")
    added = todo_add("ship", priority="high", due_date="2026-10-19", owner="ada")
    item_id = added["item"]["id"]
    assert added["open_count"] == 1

    assert todo_list(status="later")["error"] == "invalid_status"
    listed = todo_list(status="all", limit=0)
    assert listed["count"] == 1
    assert todo_get("")["error"] == "missing_todo_id"
    assert todo_get(item_id)["task"] == "ship"
    assert todo_get("missing")["error"] == "not_found"

    assert todo_update("")["error"] == "missing_todo_id"
    assert todo_update("missing")["error"] == "not_found"
    assert todo_update(item_id, status="nope")["error"] == "invalid_status"
    assert todo_update(item_id, priority="nope")["error"] == "invalid_priority"
    assert todo_update(item_id, due_date="nope")["error"] == "invalid_due_date"
    assert todo_update(item_id, task="   ")["error"] == "invalid_task"
    updated = todo_update(item_id, task="ship it", status="done", priority="low", due_date="", owner="")
    assert updated["item"]["status"] == "done"
    assert updated["item"]["due_date"] is None

    assert todo_delete("")["error"] == "missing_todo_id"
    assert todo_delete("missing")["error"] == "not_found"
    assert todo_delete(item_id)["count"] == 0

    def unwritable(todos, _session=None):
        return path, "disk full"

    monkeypatch.setattr("tools.ops_todo._save_todos", unwritable)
    path.write_text("[]", encoding="utf-8")
    assert todo_add("again")["error"] == "todo_db_error"
    path.write_text(json.dumps([{"id": "keep", "task": "x", "status": "open"}]), encoding="utf-8")
    assert todo_delete("keep")["error"] == "todo_db_error"
    assert todo_update("keep", task="y")["error"] == "todo_db_error"
