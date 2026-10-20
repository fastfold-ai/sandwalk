"""Coverage for PDB search, workspace files, case prep, and schema drift."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import tools.data_api  # noqa: F401  finish the package cycle before the split module
from agent.model_benchmark.case_prep import (
    check_expectations,
    expand_cases,
    extract_text,
    usage_from_message,
)
from agent.model_benchmark.models import BenchmarkQuestion, BenchmarkTarget
from agent_server.models import WorkspaceFileContent
from agent_server.routes.sessions_workspace import register_workspace_routes
from agent_server.workspace import WorkspaceConflictError
from kb.schema_monitor import SchemaMonitor, _schema_paths
from tools.data_api_pdb_query import build_search_query, run_search


def test_pdb_query_build_and_retry(monkeypatch) -> None:
    query, method, error = build_search_query(["kinase"], None, 5)
    assert error is None and method is None and query["return_type"] == "entry"
    empty, method, error = build_search_query(["kinase"], "nope", 5)
    assert empty == {} and "Invalid method" in error["error"]
    query, method, error = build_search_query(["kinase"], "em", 5)
    assert method == "ELECTRON MICROSCOPY"

    class Resp:
        def __init__(self, code, payload):
            self.status_code = code
            self.payload = payload

        def json(self):
            if isinstance(self.payload, Exception):
                raise self.payload
            return self.payload

    calls = {"n": 0}

    def post(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return Resp(500, {})
        if calls["n"] == 2:
            raise RuntimeError("down")
        if calls["n"] == 3:
            return Resp(200, {"total_count": 0, "result_set": []})
        return Resp(200, {"total_count": 1, "result_set": [{"id": "1ABC"}]})

    monkeypatch.setattr("tools.data_api._http_post", post)
    rows, total, note, err = run_search({}, ["a"], None, None, 5, "a")
    assert err and total == 0
    rows, total, note, err = run_search({}, ["a", "b"], None, None, 5, "a b")
    assert err and "down" in err["error"]
    rows, total, note, err = run_search({}, ["a", "b"], "EM", "ELECTRON MICROSCOPY", 5, "a b")
    assert rows == [{"id": "1ABC"}]
    assert "broadened" in note


def test_workspace_routes(tmp_path) -> None:
    content = WorkspaceFileContent(
        path="note.txt",
        content="hi",
        mime_type="text/plain",
        version="v1",
        size=2,
        mtime=datetime.now(UTC),
    )
    file_path = tmp_path / "note.txt"
    file_path.write_text("hi", encoding="utf-8")

    file_content = content

    class Workspace:
        def list(self, path, recursive=True):
            if path == "bad":
                raise FileNotFoundError(path)
            return []

        def read(self, path):
            if path == "bad":
                raise FileNotFoundError(path)
            return content

        def write(self, path, content, encoding, base_version):
            if base_version == "stale":
                raise WorkspaceConflictError(file_content)
            if path == "bad":
                raise ValueError("bad")
            return content if isinstance(content, WorkspaceFileContent) else file_content

        def resolve(self, path, must_exist=True):
            if path == "dir":
                return tmp_path
            if path == "bad":
                raise FileNotFoundError(path)
            return file_path

        root = tmp_path

    def http_error(exc):
        return HTTPException(status_code=400, detail=str(exc))

    app = FastAPI()
    register_workspace_routes(
        app,
        SimpleNamespace(session_workspace=lambda _sid: Workspace(), workspace_http_error=http_error),
    )
    client = TestClient(app)
    assert client.get("/v1/sessions/s/files").status_code == 200
    assert client.get("/v1/sessions/s/files", params={"path": "bad"}).status_code == 400
    assert client.get("/v1/sessions/s/files/content", params={"path": "note.txt"}).status_code == 200
    assert client.get("/v1/sessions/s/files/content", params={"path": "bad"}).status_code == 400
    written = client.put(
        "/v1/sessions/s/files/content",
        json={"path": "note.txt", "content": "hi"},
    )
    assert written.status_code == 200
    conflict = client.put(
        "/v1/sessions/s/files/content",
        json={"path": "note.txt", "content": "hi", "base_version": "stale"},
    )
    assert conflict.status_code == 409
    assert client.put(
        "/v1/sessions/s/files/content",
        json={"path": "bad", "content": "hi"},
    ).status_code == 400
    assert client.get("/v1/sessions/s/files/download", params={"path": "note.txt"}).status_code == 200
    assert client.get("/v1/sessions/s/files/download", params={"path": "dir"}).status_code == 400


def test_case_prep_and_schema_monitor(tmp_path) -> None:
    target = BenchmarkTarget(provider="openai", model="gpt", label="GPT", supports_reasoning_effort=True)
    plain = BenchmarkTarget(provider="openai", model="gpt", label="GPT")
    question = BenchmarkQuestion(id="q", prompt="What?")
    cases = expand_cases([target, plain], [question], efforts=["", "high", "high", "nope"])
    assert any(case.effort == "high" for case in cases)
    assert any(case.effort is None for case in cases)
    assert expand_cases([plain], [question], efforts=["nope"])
    assert extract_text(None) == ""
    assert extract_text("  hi ") == "hi"
    assert extract_text([{"type": "text", "text": "A"}, {"text": "B"}, SimpleNamespace(text="C"), {"type": "reasoning"}, "D"]) == "ABCD"
    assert extract_text(SimpleNamespace(text="  z ")) == "z"
    assert extract_text(12) == "12"
    message = SimpleNamespace(usage_metadata={"input_tokens": 1, "output": 2, "total": 3})
    assert usage_from_message(message)["input"] == 1
    assert usage_from_message(SimpleNamespace(usage_metadata=None, usage=None)) is None
    assert usage_from_message(SimpleNamespace(usage_metadata={}, usage={"input": 1}))["input"] == 1
    assert usage_from_message(SimpleNamespace(usage=SimpleNamespace(input_tokens=3, output_tokens=4)))["output"] == 4
    assert check_expectations("Hello", []) is None
    assert check_expectations("Hello World", ["hello", "world"]) is True

    paths = _schema_paths({"a": [1, None]})
    assert "$:object" in paths
    assert "$.a:array" in paths
    baseline = tmp_path / "base.json"
    baseline.write_text("{", encoding="utf-8")
    monitor = SchemaMonitor(baseline_path=baseline, monitors={"ok": lambda: {"a": 1}, "bad": lambda: None})

    def bad():
        raise RuntimeError("x")

    monitor.monitors["bad"] = bad
    results = monitor.check()
    assert {item.status for item in results} == {"new", "error"}
    monitor._baseline = {"version": 1, "monitors": {"ok": {"paths": ["$.missing:int"]}}}
    drifted = monitor.check(monitor="ok")
    assert drifted[0].status == "drift"
    monitor._baseline["monitors"]["ok"]["paths"] = sorted(_schema_paths({"a": 1}))
    assert monitor.check(monitor="ok")[0].status == "ok"
    updated = monitor.update_baseline(monitor="ok")
    assert updated and baseline.is_file()
    assert SchemaMonitor.summarize(results)["total"] == 2
    blank = SchemaMonitor(baseline_path=tmp_path / "missing.json", monitors={})
    assert blank._baseline["monitors"] == {}
    weird = tmp_path / "weird.json"
    weird.write_text("[]", encoding="utf-8")
    assert SchemaMonitor(baseline_path=weird, monitors={})._baseline["monitors"] == {}
