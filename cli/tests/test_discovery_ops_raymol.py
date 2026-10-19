"""Coverage for model discovery, workflow templates, and RayMol path lookup.

No network, no RayMol.app, and no downloads: HTTP is a stand-in for urlopen,
workflow files live under tmp_path, and process/Spotlight lookups are stubbed.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
from pathlib import Path

import pytest

import tools.ops_workflow as ops_workflow
from agent import model_discovery
from agent.mcps.raymol_mcp import paths as raymol_paths
from tools import registry as tool_registry
from tools.ops_common import _workflow_dir
from tools.ops_workflow import (
    _find_workflow_path,
    _normalize_workflow_steps,
    _slugify_name,
    workflow_delete,
    workflow_get,
    workflow_list,
    workflow_run,
    workflow_save,
    workflow_update,
)


class _StubConfig:
    def __init__(self, base_dir: Path):
        self._base_dir = base_dir

    def get(self, key: str, default=None):
        if key == "ops.base_dir":
            return str(self._base_dir)
        return default


class _StubSession:
    def __init__(self, base_dir: Path):
        self.config = _StubConfig(base_dir)


class _Body:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _OkTool:
    def run(self, **kwargs):
        return {"summary": "ok", "title": "hello", "n": kwargs.get("x", 1)}


class _BadTool:
    def run(self, **_kwargs):
        return {"error": "nope", "summary": "bad"}


class _BoomTool:
    def run(self, **_kwargs):
        raise RuntimeError("crashed")


class _EchoTool:
    def __init__(self):
        self.kwargs = None

    def run(self, **kwargs):
        self.kwargs = kwargs
        return {"summary": "echoed"}


class _ShortRef(str):
    """String that claims to be a step ref but splits into a single token."""

    def startswith(self, prefix, *args):
        return prefix == "$step."

    def split(self, sep=None, maxsplit=-1):
        return ["$step"]


class _ContinueThenStrict:
    """Truthy for the failing step, then strict so a dependent is skipped.

    A failed step returns immediately when continue_on_error is false, so the
    dependent-skip branch only runs if the flag flips after that failure is recorded.
    """

    def __init__(self) -> None:
        self._seen = False

    def __bool__(self) -> bool:
        if not self._seen:
            self._seen = True
            return True
        return False


def _session(tmp_path: Path) -> _StubSession:
    return _StubSession(tmp_path / "ops")


def _plant(session: _StubSession, stem: str, payload) -> Path:
    path = _workflow_dir(session) / f"{stem}.json"
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_steps() -> list[dict]:
    return [{"id": 1, "description": "note", "tool": "ops.note", "tool_args": {}}]


def _install_tools(monkeypatch, mapping: dict):
    real = tool_registry.get_tool

    def get_tool(name: str):
        if name in mapping:
            return mapping[name]
        return real(name)

    monkeypatch.setattr(tool_registry, "get_tool", get_tool)


def _executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


# --- model discovery -------------------------------------------------------


def test_url_builders_strip_v1_query_and_fill_prefix():
    assert (
        model_discovery.ollama_tags_url_from_base("http://127.0.0.1:11434/v1?x=1#frag")
        == "http://127.0.0.1:11434/api/tags"
    )
    assert (
        model_discovery.ollama_tags_url_from_base("http://127.0.0.1:11434/custom")
        == "http://127.0.0.1:11434/custom/api/tags"
    )
    assert (
        model_discovery.ollama_show_url_from_base("http://127.0.0.1:11434/v1")
        == "http://127.0.0.1:11434/api/show"
    )
    assert (
        model_discovery.ollama_show_url_from_base("http://h/custom") == "http://h/custom/api/show"
    )
    assert model_discovery.openai_models_url_from_base("http://h:8000") == "http://h:8000/v1/models"
    assert (
        model_discovery.openai_models_url_from_base("http://h:8000/custom")
        == "http://h:8000/custom/v1/models"
    )
    assert (
        model_discovery.openai_models_url_from_base("http://h:8000/v1") == "http://h:8000/v1/models"
    )
    assert model_discovery.openai_models_url_from_base("") == "/v1/models"


def test_request_json_posts_auth_and_parses_body(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=0):
        seen["req"] = req
        seen["timeout"] = timeout
        return _Body(b'{"models": []}')

    monkeypatch.setattr(model_discovery.urllib.request, "urlopen", fake_urlopen)
    payload, err = model_discovery._request_json(
        "http://example.test/api/show",
        "secret",
        timeout=3.5,
        method="POST",
        body={"model": "m"},
    )
    assert err is None
    assert payload == {"models": []}
    assert seen["timeout"] == 3.5
    assert seen["req"].get_header("Authorization") == "Bearer secret"
    assert seen["req"].get_method() == "POST"
    assert seen["req"].data == b'{"model": "m"}'


def test_request_json_empty_and_invalid_body(monkeypatch):
    monkeypatch.setattr(model_discovery.urllib.request, "urlopen", lambda *_a, **_k: _Body(b""))
    payload, err = model_discovery._request_json("http://example.test/v1/models", None)
    assert payload == {}
    assert err is None

    monkeypatch.setattr(model_discovery.urllib.request, "urlopen", lambda *_a, **_k: _Body(b"{"))
    payload, err = model_discovery._request_json("http://example.test/v1/models", None)
    assert payload is None
    assert err.startswith("Invalid JSON from")


def test_request_json_http_and_transport_errors(monkeypatch):
    cases = [
        urllib.error.HTTPError("http://example.test/v1/models", 401, "Unauthorized", None, None),
        urllib.error.HTTPError("http://example.test/v1/models", 500, "", None, None),
        urllib.error.URLError("refused"),
        TimeoutError("slow"),
        OSError("reset"),
    ]
    for exc in cases:

        def fake_urlopen(_req, timeout=0, exc=exc):
            raise exc

        monkeypatch.setattr(model_discovery.urllib.request, "urlopen", fake_urlopen)
        payload, err = model_discovery._request_json("http://example.test/v1/models", None)
        assert payload is None
        assert err is not None
        assert "http://example.test/v1/models" in err


def test_request_json_http_error_shapes(monkeypatch):
    def unauthorized(_req, timeout=0):
        raise urllib.error.HTTPError(
            "http://example.test/v1/models", 401, "Unauthorized", None, None
        )

    monkeypatch.setattr(model_discovery.urllib.request, "urlopen", unauthorized)
    _payload, err = model_discovery._request_json("http://example.test/v1/models", None)
    assert err.startswith("HTTP 401: Unauthorized")

    def bare(_req, timeout=0):
        raise urllib.error.HTTPError("http://example.test/v1/models", 500, "", None, None)

    monkeypatch.setattr(model_discovery.urllib.request, "urlopen", bare)
    _payload, err = model_discovery._request_json("http://example.test/v1/models", None)
    assert err.startswith("HTTP 500 (")
    assert ": " not in err.split("(", 1)[0]


def test_context_window_skips_bad_values_and_keeps_best():
    assert (
        model_discovery._context_window_from_model_item(
            {"max_model_len": "nope", "context_length": 0, "context_window": "12"}
        )
        == 12
    )
    assert model_discovery._context_window_from_model_item({"max_model_len": None}) is None
    assert (
        model_discovery._context_window_from_ollama_model_info(
            {
                "foo.context_length": "bad",
                "bar.context_length": 10,
                "context_length": 20,
            }
        )
        == 20
    )
    assert (
        model_discovery._context_window_from_ollama_model_info(
            {"foo.context_length": "bad", "max_model_len": 32}
        )
        == 32
    )
    assert (
        model_discovery._context_window_from_ollama_model_info(
            {"foo.context_length": 0, "embedding": "x"}
        )
        is None
    )


def test_fetch_ollama_show_context_rejects_bad_inputs(monkeypatch):
    assert model_discovery.fetch_ollama_show_context("http://h", "  ") is None

    monkeypatch.setattr(model_discovery, "_request_json", lambda *_a, **_k: (None, "down"))
    assert model_discovery.fetch_ollama_show_context("http://h", "m") is None

    monkeypatch.setattr(model_discovery, "_request_json", lambda *_a, **_k: ([], None))
    assert model_discovery.fetch_ollama_show_context("http://h", "m") is None

    monkeypatch.setattr(
        model_discovery, "_request_json", lambda *_a, **_k: ({"model_info": []}, None)
    )
    assert model_discovery.fetch_ollama_show_context("http://h", "m") is None


def test_fetch_openai_and_ollama_wrappers_and_dirty_payloads(monkeypatch):
    def fake(url, _api_key=None, **_kwargs):
        if url.endswith("/api/tags"):
            return (
                {
                    "models": [
                        "skip",
                        {"name": "  "},
                        {"name": "kept", "details": "nope", "context_length": 64},
                    ]
                },
                None,
            )
        return (
            {
                "data": [
                    "skip",
                    {"id": ""},
                    {"id": "m", "max_model_len": 8},
                    {"id": "plain"},
                ]
            },
            None,
        )

    monkeypatch.setattr(model_discovery, "_request_json", fake)
    names, err = model_discovery.fetch_openai_models("http://h:8000")
    assert err is None
    assert names == ["m", "plain"]
    names, err = model_discovery.fetch_ollama_tags("http://h:11434")
    assert err is None
    assert names == ["kept"]

    monkeypatch.setattr(model_discovery, "_request_json", lambda *_a, **_k: (None, "down"))
    assert model_discovery.fetch_openai_models_with_context("http://h")[2] == "down"
    assert model_discovery.fetch_ollama_tags_with_context("http://h")[2] == "down"

    monkeypatch.setattr(model_discovery, "_request_json", lambda *_a, **_k: ([], None))
    assert (
        "Unexpected /v1/models" in model_discovery.fetch_openai_models_with_context("http://h")[2]
    )
    assert "Unexpected /api/tags" in model_discovery.fetch_ollama_tags_with_context("http://h")[2]

    monkeypatch.setattr(
        model_discovery, "_request_json", lambda *_a, **_k: ({"data": "nope"}, None)
    )
    assert (
        "Unexpected /v1/models" in model_discovery.fetch_openai_models_with_context("http://h")[2]
    )
    monkeypatch.setattr(
        model_discovery, "_request_json", lambda *_a, **_k: ({"models": "nope"}, None)
    )
    assert "Unexpected /api/tags" in model_discovery.fetch_ollama_tags_with_context("http://h")[2]


@pytest.mark.parametrize(
    "backend",
    ["unsloth", "omlx", "ds4", "llama_cpp", "llama", "lm_studio"],
)
def test_discover_openai_compatible_backends(monkeypatch, backend):
    monkeypatch.setattr(
        model_discovery,
        "_request_json",
        lambda *_a, **_k: ({"data": [{"id": "local", "context_length": 1024}]}, None),
    )
    models, source, err, windows = model_discovery.discover_compatible_models(
        "http://h:8000", backend, api_key="k"
    )
    assert models == ["local"]
    assert source == "/v1/models"
    assert err is None
    assert windows == {"local": 1024}


def test_discover_openai_backend_reports_error(monkeypatch):
    monkeypatch.setattr(model_discovery, "_request_json", lambda *_a, **_k: (None, "endpoint down"))
    models, source, err, windows = model_discovery.discover_compatible_models(
        "http://h:8000", "lm_studio"
    )
    assert models == []
    assert source == "/v1/models"
    assert err == "endpoint down"
    assert windows == {}


def test_discover_ollama_falls_back_to_openai(monkeypatch):
    def fake(url, _api_key=None, **_kwargs):
        if url.endswith("/api/tags"):
            return None, "tags down"
        return {"data": [{"id": "fallback", "max_model_len": 4}]}, None

    monkeypatch.setattr(model_discovery, "_request_json", fake)
    models, source, err, windows = model_discovery.discover_compatible_models(
        "http://h:11434/v1", " Ollama "
    )
    assert models == ["fallback"]
    assert source == "/v1/models"
    assert err is None
    assert windows == {"fallback": 4}


def test_discover_ollama_joins_both_errors(monkeypatch):
    def fake(url, _api_key=None, **_kwargs):
        if url.endswith("/api/tags"):
            return None, "tags down"
        return None, "models down"

    monkeypatch.setattr(model_discovery, "_request_json", fake)
    models, source, err, _windows = model_discovery.discover_compatible_models(
        "http://h:11434", "ollama"
    )
    assert models == []
    assert source == "/v1/models"
    assert err == "tags down; models down"


def test_discover_other_backend_falls_back_to_ollama(monkeypatch):
    def fake(url, _api_key=None, **_kwargs):
        if "/v1/models" in url:
            return None, "openai down"
        return {"models": [{"name": "llama", "details": {"context_length": 2048}}]}, None

    monkeypatch.setattr(model_discovery, "_request_json", fake)
    models, source, err, windows = model_discovery.discover_compatible_models("http://h:9", "")
    assert models == ["llama"]
    assert source == "/api/tags"
    assert err is None
    assert windows == {"llama": 2048}

    monkeypatch.setattr(model_discovery, "_request_json", lambda *_a, **_k: (None, "nope"))
    models, source, err, _windows = model_discovery.discover_compatible_models(
        "http://h:9", "other"
    )
    assert models == []
    assert source == "/api/tags"
    assert err == "nope; nope"


def test_probe_error_and_no_models(monkeypatch):
    monkeypatch.setattr(model_discovery, "_request_json", lambda *_a, **_k: (None, "offline"))
    probe = model_discovery.probe_compatible_profile(
        base_url="http://h", backend="lm_studio", api_key=None
    )
    assert probe["health"] == "error"
    assert probe["error"] == "offline"
    assert probe["models"] == []

    def empty(url, _api_key=None, **_kwargs):
        if "/v1/models" in url:
            return {"data": []}, None
        return {"models": []}, None

    monkeypatch.setattr(model_discovery, "_request_json", empty)
    probe = model_discovery.probe_compatible_profile(
        base_url="http://h", backend="other", api_key=None
    )
    assert probe["health"] == "no_models"
    assert probe["error"] is None
    assert probe["models_source"] == "/api/tags"


# --- ops workflow ----------------------------------------------------------


def test_slugify_and_normalize_edges():
    assert _slugify_name("Hello!! World") == "hello-world"
    assert _slugify_name("A---B") == "a-b"
    assert _slugify_name("...") == "workflow"

    cleaned, err = _normalize_workflow_steps("[]")
    assert cleaned is None and "non-empty" in err
    cleaned, err = _normalize_workflow_steps("{}")
    assert cleaned is None and "non-empty" in err
    cleaned, err = _normalize_workflow_steps([{"tool": "t"}, "nope"])
    assert cleaned is None and "Step 2" in err

    cleaned, err = _normalize_workflow_steps(
        [
            {
                "tool": "t",
                "id": "3",
                "tool_args": "nope",
                "depends_on": ["x", 0, 2],
                "description": "d",
            }
        ]
    )
    assert err is None
    assert cleaned[0]["id"] == 3
    assert cleaned[0]["tool_args"] == {}
    assert cleaned[0]["depends_on"] == [2]


def test_workflow_save_rejects_missing_fields_and_write_errors(tmp_path, monkeypatch):
    session = _session(tmp_path)
    missing = workflow_save(name="  ", query="q", steps=_valid_steps(), _session=session)
    assert missing["error"] == "missing_name"
    missing = workflow_save(name="n", query="  ", steps=_valid_steps(), _session=session)
    assert missing["error"] == "missing_query"

    real_write = Path.write_text

    def boom(self, data, *args, **kwargs):
        if self.suffix == ".json":
            raise OSError("disk full")
        return real_write(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", boom)
    failed = workflow_save(name="N", query="Q", steps=_valid_steps(), _session=session)
    assert failed["error"] == "write_failed"


def test_find_workflow_by_slug_display_name_and_misses(tmp_path):
    session = _session(tmp_path)
    assert _find_workflow_path("  ", session)[1] == "Workflow identifier is required."
    assert _find_workflow_path("anything", session)[1] == "No saved workflows."

    saved = workflow_save(name="Hello World", query="q", steps=_valid_steps(), _session=session)
    found, err = _find_workflow_path("Hello World", session)
    assert err is None
    assert found == Path(saved["path"])

    _plant(session, "custom", {"name": "Fancy Name", "query": "q", "steps": _valid_steps()})
    _plant(session, "broken", "{")
    _plant(session, "array", [1, 2])
    found, err = _find_workflow_path("Fancy Name", session)
    assert err is None
    assert found.name == "custom.json"
    missing, err = _find_workflow_path("not-here", session)
    assert missing is None
    assert "not found" in err


def test_workflow_list_skips_bad_files_and_filters(tmp_path):
    session = _session(tmp_path)
    _plant(
        session,
        "older",
        {
            "name": "Older",
            "query": "alpha",
            "notes": "keep",
            "created_at": "2020-01-01",
            "steps": "not-a-list",
        },
    )
    _plant(
        session,
        "newer",
        {
            "name": "Newer",
            "query": "beta",
            "notes": None,
            "updated_at": "2024-01-01",
            "steps": [{"tool": "t"}],
        },
    )
    _plant(session, "broken", "{")
    _plant(session, "array", [1])

    listed = workflow_list(limit=0, query="keep", _session=session)
    assert listed["count"] == 1
    assert listed["workflows"][0]["id"] == "older"
    assert listed["workflows"][0]["n_steps"] == 0
    assert "filter='keep'" in listed["summary"]

    listed = workflow_list(limit=1000, query="beta", _session=session)
    assert [row["id"] for row in listed["workflows"]] == ["newer"]
    listed = workflow_list(limit="nope", query="missing", _session=session)
    assert listed["count"] == 0

    ranked = workflow_list(_session=session)
    assert [row["id"] for row in ranked["workflows"]] == ["newer", "older"]


def test_workflow_get_and_update_error_paths(tmp_path, monkeypatch):
    session = _session(tmp_path)
    assert workflow_get("missing", _session=session)["error"] == "not_found"
    _plant(session, "bad", "{")
    loaded = workflow_get("bad.json", _session=session)
    assert loaded["error"] == "workflow_error"
    _plant(session, "array", [1])
    assert workflow_get("array", _session=session)["error"] == "workflow_error"

    assert workflow_update("missing", name="x", _session=session)["error"] == "not_found"
    assert workflow_update("bad", name="x", _session=session)["error"] == "workflow_error"

    path = _plant(
        session,
        "edit",
        {"name": "Edit", "query": "q", "steps": _valid_steps(), "version": "nope"},
    )
    bad_steps = workflow_update("edit", steps=[], _session=session)
    assert bad_steps["error"] == "invalid_steps"
    assert workflow_update("edit", name="  ", _session=session)["error"] == "invalid_name"
    assert workflow_update("edit", query="  ", _session=session)["error"] == "invalid_query"
    path.write_text(
        json.dumps({"name": "Edit", "query": "q", "steps": []}),
        encoding="utf-8",
    )
    assert workflow_update("edit", _session=session)["error"] == "invalid_steps"

    path.write_text(
        json.dumps({"name": "Edit", "query": "q", "steps": _valid_steps()}),
        encoding="utf-8",
    )
    real_write = Path.write_text

    def boom(self, data, *args, **kwargs):
        if self.name == "edit.json":
            raise OSError("locked")
        return real_write(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", boom)
    failed = workflow_update("edit", notes="n", _session=session)
    assert failed["error"] == "write_failed"


def test_workflow_update_rewrites_fields(tmp_path):
    session = _session(tmp_path)
    saved = workflow_save(
        name="Edit", query="old", steps=_valid_steps(), notes="n", _session=session
    )
    updated = workflow_update(
        Path(saved["path"]).stem,
        name="Renamed",
        query="new query",
        notes="   ",
        steps=[{"tool": "ops.other", "description": "d2", "id": 4}],
        _session=session,
    )
    assert updated["workflow"]["name"] == "Renamed"
    assert updated["workflow"]["query"] == "new query"
    assert updated["workflow"]["notes"] is None
    assert updated["workflow"]["steps"][0]["tool"] == "ops.other"
    assert updated["workflow"]["version"] == 2


def test_workflow_delete_errors(tmp_path, monkeypatch):
    session = _session(tmp_path)
    assert workflow_delete("missing", _session=session)["error"] == "not_found"
    path = _plant(session, "gone", {"name": "Gone", "query": "q", "steps": _valid_steps()})

    def boom(self, *args, **kwargs):
        raise OSError("busy")

    monkeypatch.setattr(Path, "unlink", boom)
    failed = workflow_delete("gone", _session=session)
    assert failed["error"] == "delete_failed"
    assert path.exists()


def test_workflow_run_rejects_bad_templates(tmp_path):
    session = _session(tmp_path)
    assert workflow_run("missing", _session=session)["error"] == "not_found"
    _plant(session, "bad", "{")
    assert workflow_run("bad", _session=session)["error"] == "workflow_error"
    _plant(session, "empty", {"name": "E", "query": "q", "steps": []})
    failed = workflow_run("empty", _session=session)
    assert failed["error"] == "invalid_steps"


def test_workflow_run_missing_tool_strict_and_continue(tmp_path, monkeypatch):
    session = _session(tmp_path)
    _install_tools(monkeypatch, {"ok.tool": _OkTool()})
    saved = workflow_save(
        name="Missing",
        query="q",
        steps=[{"id": 1, "tool": "missing.tool", "description": "x"}],
        _session=session,
    )
    wid = Path(saved["path"]).stem
    strict = workflow_run(wid, _session=session)
    assert "tool not found" in strict["summary"]
    assert strict["status_by_step"][1] == "failed"

    saved = workflow_save(
        name="Continue",
        query="q",
        steps=[
            {"id": 1, "tool": "missing.tool"},
            {"id": 2, "tool": "ok.tool"},
        ],
        _session=session,
    )
    continued = workflow_run(Path(saved["path"]).stem, continue_on_error=True, _session=session)
    assert continued["status_by_step"][1] == "failed"
    assert continued["status_by_step"][2] == "completed"


def test_workflow_run_skips_failed_dependency_when_strict(tmp_path, monkeypatch):
    session = _session(tmp_path)
    _install_tools(monkeypatch, {})
    saved = workflow_save(
        name="Deps",
        query="q",
        steps=[
            {"id": 1, "tool": "missing.tool"},
            {"id": 2, "tool": "ok.tool", "depends_on": [1]},
        ],
        _session=session,
    )
    ran = workflow_run(
        Path(saved["path"]).stem,
        continue_on_error=_ContinueThenStrict(),
        _session=session,
    )
    assert ran["status_by_step"][1] == "failed"
    assert ran["status_by_step"][2] == "skipped"


def test_workflow_run_resolves_step_refs_and_cycles(tmp_path, monkeypatch):
    session = _session(tmp_path)
    echo = _EchoTool()
    _install_tools(monkeypatch, {"ok.tool": _OkTool(), "echo.tool": echo})
    saved = workflow_save(
        name="Refs",
        query="q",
        steps=[
            {"id": 1, "tool": "ok.tool", "tool_args": {"x": 3}},
            {
                "id": 2,
                "tool": "echo.tool",
                "depends_on": [1],
                "tool_args": {
                    "title": "$step.1.title",
                    "missing_step": "$step.9.title",
                    "missing_field": "$step.1.nope",
                    "short": "ref",
                },
            },
        ],
        _session=session,
    )
    # JSON cannot keep a str subclass, which is the only way a "$step." prefix
    # splits into fewer than two parts.
    real_load = ops_workflow._load_workflow_payload

    def load_with_short_ref(path: Path):
        payload, error = real_load(path)
        if payload and payload.get("name") == "Refs":
            for step in payload["steps"]:
                if step.get("tool") == "echo.tool":
                    step["tool_args"]["short"] = _ShortRef("ref")
        return payload, error

    monkeypatch.setattr(ops_workflow, "_load_workflow_payload", load_with_short_ref)
    ran = workflow_run(Path(saved["path"]).stem, _session=session, _prior_results={"seed": 1})
    assert ran["status_by_step"][2] == "completed"
    assert echo.kwargs["title"] == "hello"
    assert echo.kwargs["missing_step"] == "$step.9.title"
    assert echo.kwargs["missing_field"]["title"] == "hello"
    assert echo.kwargs["short"] == "ref"
    assert echo.kwargs["_prior_results"]["seed"] == 1

    saved = workflow_save(
        name="Cycle",
        query="q",
        steps=[
            {"id": 1, "tool": "ok.tool", "depends_on": [2]},
            {"id": 2, "tool": "ok.tool", "depends_on": [1]},
        ],
        _session=session,
    )
    cycled = workflow_run(Path(saved["path"]).stem, _session=session)
    assert cycled["status_by_step"] == {1: "skipped", 2: "skipped"}
    assert "0 completed" in cycled["summary"]


def test_workflow_run_tool_error_and_crash(tmp_path, monkeypatch):
    session = _session(tmp_path)
    _install_tools(monkeypatch, {"bad.tool": _BadTool(), "boom.tool": _BoomTool()})
    saved = workflow_save(
        name="Bad",
        query="q",
        steps=[{"id": 1, "tool": "bad.tool"}],
        _session=session,
    )
    failed = workflow_run(Path(saved["path"]).stem, _session=session)
    assert "failed at step 1" in failed["summary"]
    assert failed["executed"][0]["status"] == "failed"

    saved = workflow_save(
        name="Boom",
        query="q",
        steps=[
            {"id": 1, "tool": "boom.tool"},
            {"id": 2, "tool": "bad.tool"},
        ],
        _session=session,
    )
    crashed = workflow_run(Path(saved["path"]).stem, continue_on_error=True, _session=session)
    assert crashed["status_by_step"][1] == "failed"
    assert "crashed" in crashed["results"][1]["summary"]
    assert crashed["status_by_step"][2] == "failed"
    assert "0 completed, 2 failed" in crashed["summary"]


# --- RayMol paths ----------------------------------------------------------


def test_usable_resolve_error_and_non_binary(tmp_path, monkeypatch):
    binary = _executable(tmp_path / "RayMol")

    def boom(self, strict=False):
        raise OSError("resolve failed")

    monkeypatch.setattr(Path, "resolve", boom)
    assert raymol_paths._usable(binary) == binary

    note = tmp_path / "readme.txt"
    note.write_text("hi", encoding="utf-8")
    note.chmod(0o644)
    assert raymol_paths._usable(note) is None
    assert raymol_paths._usable(None) is None


def test_binaries_in_app_filters_and_errors(tmp_path, monkeypatch):
    assert raymol_paths._binaries_in_app(tmp_path / "Missing.app") == []

    app = tmp_path / "RayMol.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    (macos / "Resources").mkdir()
    (macos / "RayMol").write_text("a", encoding="utf-8")
    (macos / "PyMOL").write_text("b", encoding="utf-8")
    (macos / "raymol-helper").write_text("c", encoding="utf-8")
    (macos / "ignore-me").write_text("d", encoding="utf-8")
    names = [item.name for item in raymol_paths._binaries_in_app(app)]
    assert names[0] == "RayMol"
    assert set(names[1:]) == {"PyMOL", "raymol-helper"}

    real_iter = Path.iterdir

    def denied(self):
        if self == macos:
            raise OSError("denied")
        return real_iter(self)

    monkeypatch.setattr(Path, "iterdir", denied)
    assert raymol_paths._binaries_in_app(app) == []


def test_mdfind_parses_stdout_and_failures(tmp_path, monkeypatch):
    app = tmp_path / "RayMol.app"
    app.mkdir()
    decoy = tmp_path / "NotRayMol.app"
    decoy.write_text("x", encoding="utf-8")

    class _Proc:
        stdout = f"\n  \n{app}\n{decoy}\njust-text\n"

    monkeypatch.setattr(raymol_paths.subprocess, "run", lambda *_a, **_k: _Proc())
    assert raymol_paths._mdfind("kMDItemFSName == 'RayMol.app'") == [app]

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="mdfind", timeout=5)

    monkeypatch.setattr(raymol_paths.subprocess, "run", timeout)
    assert raymol_paths._mdfind("q") == []

    def missing(*_args, **_kwargs):
        raise OSError("no mdfind")

    monkeypatch.setattr(raymol_paths.subprocess, "run", missing)
    assert raymol_paths._mdfind("q") == []


def test_apps_from_mdfind_falls_back_to_name(tmp_path, monkeypatch):
    app = tmp_path / "RayMol.app"
    calls = []

    def fake(query: str):
        calls.append(query)
        if "CFBundleIdentifier" in query:
            return []
        return [app]

    monkeypatch.setattr(raymol_paths, "_mdfind", fake)
    assert raymol_paths._apps_from_mdfind() == [app]
    assert len(calls) == 2


def test_running_binaries_filters_ps_and_errors(monkeypatch):
    class _Proc:
        stdout = "\n".join(
            [
                "",
                "   ",
                "/usr/sbin/raymol-helper",
                "/tmp/RayMol",
                "/tmp/RayMol",
                "/Volumes/RayMol/RayMol.app/Contents/MacOS/RayMol",
            ]
        )

    monkeypatch.setattr(raymol_paths.subprocess, "run", lambda *_a, **_k: _Proc())
    found = raymol_paths.running_binaries()
    assert [str(path) for path in found] == [
        "/tmp/RayMol",
        "/Volumes/RayMol/RayMol.app/Contents/MacOS/RayMol",
    ]

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="ps", timeout=5)

    monkeypatch.setattr(raymol_paths.subprocess, "run", timeout)
    assert raymol_paths.running_binaries() == []

    def missing(*_args, **_kwargs):
        raise OSError("no ps")

    monkeypatch.setattr(raymol_paths.subprocess, "run", missing)
    assert raymol_paths.running_binaries() == []


def test_apps_on_volumes_scans_and_skips_failures(tmp_path, monkeypatch):
    real_is_dir = Path.is_dir

    def hidden(self):
        if str(self) == "/Volumes":
            return False
        return real_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", hidden)
    assert raymol_paths._apps_on_volumes() == []

    vol = tmp_path / "disk"
    (vol / "RayMol.app").mkdir(parents=True)
    (vol / "Other.app").mkdir()
    (vol / "note.txt").write_text("n", encoding="utf-8")
    locked = tmp_path / "locked"
    locked.mkdir()
    real_iter = Path.iterdir

    def fake_iter(self):
        if str(self) == "/Volumes":
            return iter([vol, locked])
        if self == locked:
            raise OSError("unmount")
        return real_iter(self)

    monkeypatch.setattr(Path, "is_dir", real_is_dir)
    monkeypatch.setattr(Path, "iterdir", fake_iter)
    assert raymol_paths._apps_on_volumes() == [vol / "RayMol.app"]

    def denied(self):
        if str(self) == "/Volumes":
            raise OSError("no volumes")
        return real_iter(self)

    monkeypatch.setattr(Path, "iterdir", denied)
    assert raymol_paths._apps_on_volumes() == []


def test_apps_from_homebrew_versions_and_errors(tmp_path, monkeypatch):
    ver = tmp_path / "cask" / "1.0"
    (ver / "RayMol.app").mkdir(parents=True)
    (ver / "ignore.txt").write_text("x", encoding="utf-8")
    bad = tmp_path / "cask" / "bad"
    bad.mkdir()
    real_is_dir = Path.is_dir
    real_iter = Path.iterdir

    def fake_is_dir(self):
        if str(self) in {"/opt/homebrew/Caskroom/raymol", "/usr/local/Caskroom/raymol"}:
            return True
        return real_is_dir(self)

    def fake_iter(self):
        text = str(self)
        if text == "/opt/homebrew/Caskroom/raymol":
            return iter([ver, bad])
        if self == bad or text == "/usr/local/Caskroom/raymol":
            raise OSError("unreadable")
        return real_iter(self)

    monkeypatch.setattr(Path, "is_dir", fake_is_dir)
    monkeypatch.setattr(Path, "iterdir", fake_iter)
    assert raymol_paths._apps_from_homebrew() == [ver / "RayMol.app"]


def test_candidate_apps_dedupes_and_survives_oserrors(tmp_path, monkeypatch):
    spot = tmp_path / "SpotRayMol.app"
    brew = tmp_path / "BrewRayMol.app"
    vol = tmp_path / "VolRayMol.app"
    monkeypatch.setattr(raymol_paths, "_apps_from_mdfind", lambda: [spot])
    monkeypatch.setattr(raymol_paths, "_apps_from_homebrew", lambda: [brew, spot])
    monkeypatch.setattr(raymol_paths, "_apps_on_volumes", lambda: [vol])
    real_resolve = Path.resolve
    real_is_dir = Path.is_dir
    real_iter = Path.iterdir
    home_apps = Path.home() / "Applications"

    def fake_resolve(self, strict=False):
        if self.name == "RayMol-nightly.app":
            raise OSError("bad path")
        return real_resolve(self, strict=strict)

    def fake_is_dir(self):
        if str(self) in {"/Applications", str(home_apps)}:
            return True
        return real_is_dir(self)

    def fake_iter(self):
        text = str(self)
        if text == "/Applications":
            return iter(
                [
                    Path("/Applications/RayMol-nightly.app"),
                    Path("/Applications/Notes.app"),
                    Path("/Applications/readme.txt"),
                ]
            )
        if text == str(home_apps):
            raise OSError("home apps denied")
        return real_iter(self)

    monkeypatch.setattr(Path, "resolve", fake_resolve)
    monkeypatch.setattr(Path, "is_dir", fake_is_dir)
    monkeypatch.setattr(Path, "iterdir", fake_iter)
    found = {path.name for path in raymol_paths._candidate_apps()}
    assert {
        "RayMol.app",
        "SpotRayMol.app",
        "BrewRayMol.app",
        "VolRayMol.app",
        "RayMol-nightly.app",
    } <= found
    assert "Notes.app" not in found


def test_config_override_exception_and_usable_path(tmp_path, monkeypatch):
    def explode():
        raise RuntimeError("config down")

    monkeypatch.setattr("agent.config.Config.load", explode)
    assert raymol_paths._config_override() is None

    binary = _executable(tmp_path / "RayMol")

    class _Cfg:
        def get(self, key, default=None):
            assert key == "mcp.raymol_binary"
            return str(binary)

    monkeypatch.setattr("agent.config.Config.load", lambda: _Cfg())
    found = raymol_paths._config_override()
    assert found == binary.resolve()


def test_on_removable_volume_when_resolve_fails(monkeypatch):
    def boom(self, strict=False):
        raise OSError("resolve failed")

    monkeypatch.setattr(Path, "resolve", boom)
    assert raymol_paths.on_removable_volume(Path("/Volumes/RayMol/RayMol.app")) is True
    assert raymol_paths.on_removable_volume(Path("/Applications/RayMol.app")) is False


def test_find_raymol_prefers_override_which_and_default(tmp_path, monkeypatch):
    binary = _executable(tmp_path / "RayMol")

    def fail(*_args, **_kwargs):
        raise AssertionError("later sources should not run")

    monkeypatch.setattr(raymol_paths, "_config_override", lambda: binary)
    monkeypatch.setattr(raymol_paths, "running_binaries", fail)
    assert raymol_paths.find_raymol_binary() == binary.resolve()

    other = _executable(tmp_path / "bin" / "raymol")

    def which(name: str):
        if name == "RayMol":
            return str(tmp_path / "absent")
        if name == "raymol":
            return str(other)
        return None

    monkeypatch.setattr(raymol_paths, "_config_override", lambda: None)
    monkeypatch.setattr(raymol_paths, "running_binaries", lambda: [])
    monkeypatch.setattr(raymol_paths.shutil, "which", which)
    monkeypatch.setattr(raymol_paths, "_candidate_apps", lambda: [])
    assert raymol_paths.find_raymol_binary() == other.resolve()

    default = _executable(tmp_path / "Applications" / "RayMol")
    monkeypatch.setattr(raymol_paths.shutil, "which", lambda _name: None)
    monkeypatch.setattr(raymol_paths, "DEFAULT_APP_BINARY", default)
    assert raymol_paths.find_raymol_binary() == default.resolve()


def test_handoff_ready_when_read_fails(tmp_path, monkeypatch):
    handoff = tmp_path / "mcp.json"
    handoff.write_text('{"port": 1, "token": "t"}', encoding="utf-8")
    monkeypatch.setattr(raymol_paths, "HANDOFF_PATH", handoff)
    real_read = Path.read_text

    def boom(self, *args, **kwargs):
        if self == handoff:
            raise OSError("denied")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom)
    assert raymol_paths.handoff_ready() is False
