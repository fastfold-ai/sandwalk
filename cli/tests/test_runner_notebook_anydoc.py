"""Coverage for runner helper, notebook, and anydoc branches the suite still misses."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import agent.runner  # finish the runner/helpers import cycle before helpers loads
from agent import runner_helpers as helpers
from agent.skills.deps import anydoc as anydoc_mod
from tools import ops_notebook as notebook


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


class _PayloadError(Exception):
    def __init__(self, message: str = "provider failed", **attrs):
        super().__init__(message)
        for key, value in attrs.items():
            setattr(self, key, value)


class _JsonResponse:
    def __init__(self, payload=None, *, text="", json_error=False, text_error=False):
        self._payload = payload
        self._text = text
        self._json_error = json_error
        self._text_error = text_error

    def json(self):
        if self._json_error:
            raise ValueError("response is not json")
        return self._payload

    @property
    def text(self):
        if self._text_error:
            raise RuntimeError("text unavailable")
        return self._text


def _completed(args, code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args, code, stdout=stdout, stderr=stderr)


def _bind_anydoc_home(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(anydoc_mod, "_config_dir", lambda: tmp_path)
    return tmp_path


def _patch_which(monkeypatch, *, node="/usr/bin/node", npm="/usr/bin/npm"):
    def which(cmd: str):
        if cmd == "node":
            return node
        if cmd == "npm":
            return npm
        return None

    monkeypatch.setattr(anydoc_mod.shutil, "which", which)


def _patch_run(monkeypatch, handler):
    def fake_run(args, **kwargs):
        return handler(list(args), kwargs)

    monkeypatch.setattr(anydoc_mod.subprocess, "run", fake_run)


def _make_binary(home: Path, body: str = "#!/bin/sh\n") -> Path:
    binary = home / "skill-deps" / "anydoc" / "node_modules" / ".bin" / "anydoc"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text(body, encoding="utf-8")
    binary.chmod(0o755)
    return binary


# --- runner helpers ---------------------------------------------------------


def test_extract_provider_payload_from_body_response_and_cause():
    parsed = helpers._extract_provider_error_payload(_PayloadError(body='{"message": "from body"}'))
    assert parsed == {"message": "from body"}

    assert helpers._extract_provider_error_payload(_PayloadError(body="{not-json")) is None
    assert helpers._extract_provider_error_payload(_PayloadError(body="[1, 2]")) is None
    assert helpers._extract_provider_error_payload(_PayloadError(body="plain")) is None

    from_response = helpers._extract_provider_error_payload(
        _PayloadError(response=_JsonResponse({"error": {"message": "from response"}}))
    )
    assert from_response["error"]["message"] == "from response"

    listed = helpers._extract_provider_error_payload(
        _PayloadError(
            response=_JsonResponse(
                ["nope"],
                json_error=False,
                text='{"message": "from text"}',
            )
        )
    )
    assert listed == {"message": "from text"}

    assert (
        helpers._extract_provider_error_payload(
            _PayloadError(response=_JsonResponse(None, json_error=True, text="{still bad"))
        )
        is None
    )
    assert (
        helpers._extract_provider_error_payload(
            _PayloadError(response=_JsonResponse(None, json_error=True, text="not-an-object"))
        )
        is None
    )
    assert (
        helpers._extract_provider_error_payload(
            _PayloadError(response=_JsonResponse(None, json_error=True, text_error=True))
        )
        is None
    )

    via_response_json = helpers._extract_provider_error_payload(
        _PayloadError(response_json='{"message": "second slot"}')
    )
    assert via_response_json == {"message": "second slot"}


def test_format_openrouter_provider_detail_branches():
    assert helpers._format_openrouter_provider_detail({"error": "boom"}) is None
    assert helpers._format_openrouter_provider_detail({}) is None
    assert helpers._format_openrouter_provider_detail({"error": {}}) is None

    prefixed = helpers._format_openrouter_provider_detail(
        {
            "error": {
                "message": "Provider returned error",
                "metadata": {"raw": "disk full", "provider_name": "Groq"},
            }
        }
    )
    assert prefixed == "Groq: disk full"

    raw_only = helpers._format_openrouter_provider_detail(
        {"message": "ignored", "metadata": {"raw": "Groq: disk full", "provider": "Groq"}}
    )
    assert raw_only == "Groq: disk full"

    with_provider = helpers._format_openrouter_provider_detail(
        {"error": {"message": "bad model", "metadata": {"provider": "ollama"}}}
    )
    assert with_provider == "ollama: bad model"

    assert helpers._format_openrouter_provider_detail({"message": "quota hit"}) == "quota hit"
    assert (
        helpers._format_openrouter_provider_detail(
            {"error": {"message": "Provider returned error", "metadata": {"provider_name": "Groq"}}}
        )
        == "Groq: Provider returned error"
    )


def test_provider_error_detail_uses_cause_markers_and_limit():
    nested = _PayloadError("inner")
    nested.body = {"error": {"message": "schema rejected", "metadata": {"provider": "lmstudio"}}}
    outer = _PayloadError("outer wrapper")
    outer.__cause__ = nested
    assert helpers._provider_error_detail(outer).startswith("lmstudio: schema rejected")

    cause = TimeoutError("timed out waiting on socket")
    wrapped = _PayloadError("wrapper")
    wrapped.__cause__ = cause
    assert "timed out waiting on socket" in helpers._provider_error_detail(wrapped)

    marker = "x" * 50 + " See also `http_socket_options` please tune the client"
    trimmed = helpers._provider_error_detail(_PayloadError(marker))
    assert "http_socket_options" not in trimmed
    assert trimmed.endswith(".")

    plain_marker = "y" * 50 + " See also http_socket_options for details"
    trimmed_plain = helpers._provider_error_detail(_PayloadError(plain_marker))
    assert "for details" not in trimmed_plain

    early = helpers._provider_error_detail(
        _PayloadError(" See also `http_socket_options` too early to trim")
    )
    assert "too early" in early

    long_text = "z" * 400
    limited = helpers._provider_error_detail(_PayloadError(long_text), limit=40)
    assert len(limited) == 40
    assert limited.endswith("…")


def test_transient_transport_error_includes_cause_text():
    cause = ConnectionError("ssl: bad record mac")
    exc = RuntimeError("unhelpful wrapper")
    exc.__cause__ = cause
    assert helpers._is_transient_transport_error(exc) is True
    assert helpers._is_transient_transport_error(TimeoutError("timed out")) is True
    assert helpers._is_transient_transport_error(RuntimeError("all good")) is False


def test_classify_llm_error_load_unavailable_and_recursion():
    title, body = helpers._classify_llm_error(_PayloadError("failed to load model weights"))
    assert title == "Model failed to load"
    assert "llama update" in body

    title, body = helpers._classify_llm_error(_PayloadError("unknown model architecture 'qwen3'"))
    assert title == "Model failed to load"

    title, body = helpers._classify_llm_error(_PayloadError("nope", status_code=503))
    assert title == "Provider unavailable"
    assert "temporarily unavailable" in body

    title, _body = helpers._classify_llm_error(_PayloadError("service unavailable"))
    assert title == "Provider unavailable"

    title, body = helpers._classify_llm_error(_PayloadError("Recursion limit of 25 reached"))
    assert title == "Agent step limit reached"
    assert "safety cap" in body


def test_discover_task_output_when_roots_are_missing(monkeypatch, tmp_path):
    missing = tmp_path / "missing.output"

    def _direct(_task_id: str) -> str:
        return str(missing)

    monkeypatch.setattr(agent.runner, "_default_local_task_output_path", _direct)
    monkeypatch.setattr(helpers.os, "getuid", lambda: 987654321)
    assert helpers._discover_local_task_output_file("task_missing") == ""


def test_discover_task_output_globs_redirected_tmp(monkeypatch, tmp_path):
    hit = tmp_path / "task_hit.output"
    hit.write_text("done", encoding="utf-8")
    real_path = helpers.Path

    class _RedirectPath:
        def __init__(self, raw):
            self.raw = str(raw)

        def exists(self):
            if "claude-" in self.raw:
                return self.raw.startswith("/tmp/claude-")
            return real_path(self.raw).exists()

        def glob(self, _pattern):
            if self.raw.startswith("/tmp/claude-"):
                return [hit]
            return []

    def _no_direct(_task_id: str) -> str:
        return ""

    monkeypatch.setattr(helpers, "Path", _RedirectPath)
    monkeypatch.setattr(agent.runner, "_default_local_task_output_path", _no_direct)
    monkeypatch.setattr(helpers.os, "getuid", lambda: 424242)
    assert helpers._discover_local_task_output_file("task_hit") == str(hit)


def test_parse_task_probe_json_embedded_object_and_empty_keys():
    embedded = helpers._parse_task_probe_json('note before {"": "running", "t": "stopped"} tail')
    assert embedded == {"t": "stopped"}
    assert helpers._parse_task_probe_json('{"": "running"}') == {}
    assert helpers._parse_task_probe_json('{"task": null}') == {"task": "unknown"}


def test_task_path_warp_and_notification_edges(monkeypatch):
    paths = helpers._extract_task_output_paths_from_text(
        ["see /tmp/tasks/abc.output, and /var/tasks/def.output)"]
    )
    assert paths["abc"] == "/tmp/tasks/abc.output"
    assert paths["def"] == "/var/tasks/def.output"
    assert helpers._extract_task_output_paths_from_text(None) == {}

    assert helpers._looks_like_unverified_execution_claim("see fold_abc123xyz later", []) is True
    assert helpers._looks_like_unverified_execution_claim("the process is running", []) is False

    monkeypatch.setenv("TERM_PROGRAM", "WarpTerminal")
    assert helpers._is_warp_terminal_env() is True
    assert helpers._sanitize_notification_text(None) == ""
    assert helpers._sanitize_notification_text("a;b") == "a,b"


def test_default_local_task_output_path_uses_cwd(monkeypatch, tmp_path):
    monkeypatch.setattr(helpers.os, "getuid", lambda: 77)
    monkeypatch.chdir(tmp_path)
    path = helpers._default_local_task_output_path("task_77")
    assert path.endswith("/tasks/task_77.output")
    assert "/private/tmp/claude-77/" in path


# --- notebook ---------------------------------------------------------------


def test_normalize_tags_non_list_duplicates_and_cap():
    assert notebook._normalize_tags(12) == ["12"]
    assert notebook._normalize_tags("Alpha, alpha, , beta") == ["alpha", "beta"]
    tags = notebook._normalize_tags([f"t{i}" for i in range(25)])
    assert tags == [f"t{i}" for i in range(20)]
    assert notebook._normalize_tags(None) == []


def test_notebook_add_validates_and_survives_write_errors(tmp_path):
    session = _StubSession(tmp_path)
    missing_title = notebook.notebook_add(title="  ", content="body", _session=session)
    assert missing_title["error"] == "missing_title"
    missing_content = notebook.notebook_add(title="Title", content="  ", _session=session)
    assert missing_content["error"] == "missing_content"

    numeric = notebook.notebook_add(
        title="Nums",
        content="body",
        tags=7,
        _session=session,
    )
    assert numeric["entry"]["tags"] == ["7"]

    path = tmp_path / "notebook.jsonl"
    path.unlink()
    path.mkdir()
    failed = notebook.notebook_add(title="Title", content="body", _session=session)
    assert failed["error"] == "write_failed"


def test_notebook_search_edges(tmp_path):
    session = _StubSession(tmp_path)
    empty = notebook.notebook_search(query="anything", _session=session)
    assert empty["count"] == 0
    assert empty["matches"] == []

    long_content = "line1\n" + ("y" * 200)
    path = tmp_path / "notebook.jsonl"
    rows = [
        "",
        "{bad",
        "[]",
        json.dumps(
            {
                "id": "old",
                "created_at": "2020-01-01T00:00:00",
                "title": "Old note",
                "content": "short",
                "tags": ["keep"],
                "linked_query": "q-old",
            }
        ),
        json.dumps(
            {
                "id": "new",
                "created_at": "2024-05-01T00:00:00",
                "title": "New note",
                "content": long_content,
                "tags": ["other"],
                "linked_query": None,
            }
        ),
        json.dumps({"id": "bare", "created_at": "2023-01-01", "title": "Bare", "content": "x"}),
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    by_tag = notebook.notebook_search(query="", tag="keep", limit=100, _session=session)
    assert [row["id"] for row in by_tag["matches"]] == ["old"]
    assert by_tag["skipped_malformed_lines"] == 2
    assert "malformed" in by_tag["summary"]

    listed = notebook.notebook_search(limit=0, _session=session)
    assert listed["count"] == 1
    assert listed["matches"][0]["id"] == "new"
    assert "\n" not in listed["matches"][0]["preview"]
    assert listed["matches"][0]["preview"].endswith("...")
    assert len(listed["matches"][0]["preview"]) == 180
    assert "query=" not in listed["summary"]


def test_notebook_load_errors_surface_on_each_command(tmp_path):
    session = _StubSession(tmp_path)
    path = tmp_path / "notebook.jsonl"
    path.mkdir()

    loaded, skipped, error = notebook._load_notebook_entries(session)
    assert loaded == []
    assert skipped == 0
    assert error and "Failed to read notebook" in error

    for result in (
        notebook.notebook_get(entry_id="abc", _session=session),
        notebook.notebook_list(_session=session),
        notebook.notebook_update(entry_id="abc", title="T", _session=session),
        notebook.notebook_delete(entry_id="abc", _session=session),
    ):
        assert result["error"] == "notebook_error"


def test_notebook_get_list_and_skipped_lines(tmp_path):
    session = _StubSession(tmp_path)
    assert notebook.notebook_get(entry_id="  ", _session=session)["error"] == "missing_entry_id"
    assert notebook.notebook_list(tag="@@@", _session=session)["error"] == "invalid_tag"

    empty_list = notebook.notebook_list(_session=session)
    assert empty_list["count"] == 0

    long_content = "p\n" + ("z" * 180)
    path = tmp_path / "notebook.jsonl"
    path.write_text(
        "\n".join(
            [
                "",
                "{nope",
                "123",
                json.dumps(
                    {
                        "id": "keep-me",
                        "created_at": "2024-01-02",
                        "title": "Kept",
                        "content": long_content,
                        "tags": ["project"],
                    }
                ),
                json.dumps(
                    {
                        "id": "drop-me",
                        "created_at": "2024-01-03",
                        "title": "Other",
                        "content": "plain",
                        "tags": None,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    got = notebook.notebook_get(entry_id="keep-me", _session=session)
    assert got["title"] == "Kept"
    assert "Skipped 2 malformed" in got["summary"]

    listing = notebook.notebook_list(tag="project", limit="5", _session=session)
    assert listing["count"] == 1
    assert listing["entries"][0]["preview"].endswith("...")
    assert len(listing["entries"][0]["preview"]) == 140
    assert "tag=project" in listing["summary"]
    assert "Skipped 2 malformed" in listing["summary"]

    assert notebook.notebook_get(entry_id="missing", _session=session)["error"] == "not_found"


def test_notebook_update_and_delete_edges(tmp_path, monkeypatch):
    session = _StubSession(tmp_path)
    assert notebook.notebook_update(entry_id="", _session=session)["error"] == "missing_entry_id"
    assert notebook.notebook_delete(entry_id="", _session=session)["error"] == "missing_entry_id"
    assert (
        notebook.notebook_update(entry_id="nope", title="T", _session=session)["error"]
        == "not_found"
    )
    assert notebook.notebook_delete(entry_id="nope", _session=session)["error"] == "not_found"

    path = tmp_path / "notebook.jsonl"
    path.write_text(
        "{bad}\n"
        + json.dumps(
            {
                "id": "other",
                "created_at": "2023-01-01",
                "title": "Other",
                "content": "Keep",
                "tags": [],
            }
        )
        + "\n"
        + json.dumps(
            {
                "id": "e1",
                "created_at": "2024-01-01",
                "title": "Title",
                "content": "Body",
                "tags": ["a"],
                "linked_query": "old",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    blank_title = notebook.notebook_update(entry_id="e1", title="   ", _session=session)
    assert blank_title["error"] == "invalid_title"
    blank_content = notebook.notebook_update(entry_id="e1", content="  ", _session=session)
    assert blank_content["error"] == "invalid_content"

    updated = notebook.notebook_update(entry_id="e1", linked_query="   ", _session=session)
    assert updated["entry"]["linked_query"] is None
    assert "Skipped 1 malformed" in updated["summary"]

    real_open = open

    def _fail_write(file, mode="r", *args, **kwargs):
        if "w" in str(mode):
            raise OSError("disk full")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _fail_write)
    save_error = notebook.notebook_update(entry_id="e1", title="Next", _session=session)
    assert save_error["error"] == "notebook_error"
    assert "Failed to persist notebook" in save_error["summary"]

    delete_error = notebook.notebook_delete(entry_id="e1", _session=session)
    assert delete_error["error"] == "notebook_error"


def test_notebook_delete_reports_skipped_lines(tmp_path):
    session = _StubSession(tmp_path)
    path = tmp_path / "notebook.jsonl"
    path.write_text(
        "[]\n" + json.dumps({"id": "gone", "title": "T", "content": "C", "tags": []}) + "\n",
        encoding="utf-8",
    )
    deleted = notebook.notebook_delete(entry_id="gone", _session=session)
    assert deleted["count"] == 0
    assert "Skipped 1 malformed" in deleted["summary"]
    _path, error = notebook._save_notebook_entries([{"id": "x"}], session)
    assert error is None


def test_notebook_save_reports_os_error(tmp_path, monkeypatch):
    session = _StubSession(tmp_path)
    real_open = open

    def _fail_write(file, mode="r", *args, **kwargs):
        if "w" in str(mode):
            raise OSError("read only")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _fail_write)
    _path, error = notebook._save_notebook_entries([{"id": "x"}], session)
    assert error and "Failed to persist notebook" in error


# --- anydoc -----------------------------------------------------------------


def test_anydoc_paths_command_and_sample_csv(monkeypatch, tmp_path):
    _bind_anydoc_home(monkeypatch, tmp_path)
    home = anydoc_mod.anydoc_home()
    binary = anydoc_mod.anydoc_bin()
    assert home == tmp_path / "skill-deps" / "anydoc"
    assert binary == home / "node_modules" / ".bin" / "anydoc"
    assert anydoc_mod.preferred_command() == "npx -y @firecrawl/anydoc"
    steps = anydoc_mod.setup_steps()
    assert len(steps) == 3
    assert steps[0].title.startswith("Install Node")

    sample = anydoc_mod._sample_csv_path(home)
    assert "hello,1" in sample.read_text(encoding="utf-8")
    sample.write_text("custom\n", encoding="utf-8")
    assert anydoc_mod._sample_csv_path(home).read_text(encoding="utf-8") == "custom\n"

    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o644)
    assert anydoc_mod._binary_ready() is False
    assert anydoc_mod.preferred_command() == "npx -y @firecrawl/anydoc"
    binary.chmod(0o755)
    assert anydoc_mod._binary_ready() is True
    assert anydoc_mod.preferred_command() == str(binary)


def test_anydoc_run_merges_env_and_cwd(monkeypatch, tmp_path):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _completed(args, stdout="ok")

    monkeypatch.setattr(anydoc_mod.subprocess, "run", fake_run)
    monkeypatch.setenv("SANDWALK_TEST_KEEP", "1")
    proc = anydoc_mod._run(["echo", "hi"], cwd=tmp_path, timeout=12, env={"EXTRA": "2"})
    assert proc.stdout == "ok"
    assert captured["kwargs"]["cwd"] == str(tmp_path)
    assert captured["kwargs"]["timeout"] == 12
    assert captured["kwargs"]["check"] is False
    assert captured["kwargs"]["env"]["EXTRA"] == "2"
    assert captured["kwargs"]["env"]["SANDWALK_TEST_KEEP"] == "1"

    anydoc_mod._run(["echo"], env=None)
    assert captured["kwargs"]["cwd"] is None
    assert "EXTRA" not in captured["kwargs"]["env"]


def test_node_major_and_find_node_failures(monkeypatch):
    assert anydoc_mod._node_major("v20.11.1") == 20
    assert anydoc_mod._node_major("node version v18.0.0") == 18
    assert anydoc_mod._node_major("not a version") is None
    assert anydoc_mod._node_major("") is None

    _patch_which(monkeypatch, node=None, npm=None)
    assert anydoc_mod._find_node() == (None, "Node.js not found on PATH")
    assert anydoc_mod._find_npm() is None

    _patch_which(monkeypatch, node="/usr/bin/node", npm="/usr/bin/npm")
    assert anydoc_mod._find_npm() == "/usr/bin/npm"

    def _timeout(args, _kwargs):
        raise subprocess.TimeoutExpired(args, 10)

    _patch_run(monkeypatch, _timeout)
    node, detail = anydoc_mod._find_node()
    assert node is None
    assert "Could not run node" in detail

    def _os_error(_args, _kwargs):
        raise OSError("exec failed")

    _patch_run(monkeypatch, _os_error)
    _node, detail = anydoc_mod._find_node()
    assert "exec failed" in detail

    def _empty(args, _kwargs):
        return _completed(args, stdout="", stderr="")

    _patch_run(monkeypatch, _empty)
    _node, detail = anydoc_mod._find_node()
    assert "Unrecognized node version" in detail
    assert "(empty)" in detail

    def _old(args, _kwargs):
        return _completed(args, stdout="", stderr="v18.13.0")

    _patch_run(monkeypatch, _old)
    _node, detail = anydoc_mod._find_node()
    assert "need v20+" in detail

    def _ok(args, _kwargs):
        return _completed(args, stdout="v22.4.0\n")

    _patch_run(monkeypatch, _ok)
    found, text = anydoc_mod._find_node()
    assert found == "/usr/bin/node"
    assert text == "v22.4.0"


def test_convert_sample_success_and_failures(monkeypatch, tmp_path):
    _bind_anydoc_home(monkeypatch, tmp_path)
    binary = _make_binary(tmp_path)

    def _ok(args, _kwargs):
        assert args[0] == str(binary)
        assert "--format" in args
        return _completed(args, stdout="| name | hello |\n")

    _patch_run(monkeypatch, _ok)
    assert anydoc_mod._convert_sample(binary) == (True, "Sample CSV converted to Markdown")

    def _unexpected(args, _kwargs):
        return _completed(args, stdout="nothing useful")

    _patch_run(monkeypatch, _unexpected)
    ok, detail = anydoc_mod._convert_sample(binary)
    assert ok is False
    assert "unexpected" in detail

    def _stderr(args, _kwargs):
        return _completed(args, code=2, stderr="bad csv")

    _patch_run(monkeypatch, _stderr)
    ok, detail = anydoc_mod._convert_sample(binary)
    assert ok is False
    assert detail == "bad csv"

    def _empty_fail(args, _kwargs):
        return _completed(args, code=3)

    _patch_run(monkeypatch, _empty_fail)
    ok, detail = anydoc_mod._convert_sample(binary)
    assert ok is False
    assert detail == "anydoc exited 3"

    def _timeout(args, _kwargs):
        raise subprocess.TimeoutExpired(args, 60)

    _patch_run(monkeypatch, _timeout)
    ok, detail = anydoc_mod._convert_sample(binary)
    assert ok is False
    assert detail.startswith("Sample convert failed")

    def _os_error(_args, _kwargs):
        raise OSError("cannot exec")

    _patch_run(monkeypatch, _os_error)
    ok, detail = anydoc_mod._convert_sample(binary)
    assert ok is False
    assert "cannot exec" in detail


def test_doctor_reports_error_when_sample_convert_fails(monkeypatch, tmp_path):
    _bind_anydoc_home(monkeypatch, tmp_path)
    _make_binary(tmp_path)
    _patch_which(monkeypatch)

    def _run(args, _kwargs):
        name = Path(args[0]).name
        if name == "node":
            return _completed(args, stdout="v20.0.0\n")
        return _completed(args, code=1, stderr="convert boom")

    _patch_run(monkeypatch, _run)
    status = anydoc_mod.doctor()
    assert status.status == "error"
    assert status.summary == "anydoc health check failed"
    sample = next(check for check in status.checks if check.name == "sample_convert")
    assert sample.status == "error"
    assert "reinstall" in sample.fix
    assert status.command.endswith("/anydoc")


def test_doctor_ok_and_missing_binary(monkeypatch, tmp_path):
    _bind_anydoc_home(monkeypatch, tmp_path)
    _patch_which(monkeypatch, node="/usr/bin/node", npm=None)

    def _node_only(args, _kwargs):
        return _completed(args, stdout="v21.0.0\n")

    _patch_run(monkeypatch, _node_only)
    missing = anydoc_mod.doctor()
    assert missing.status == "missing"
    assert any(check.name == "npm" and check.status == "missing" for check in missing.checks)
    assert any(
        check.name == "sample_convert" and check.status == "missing" for check in missing.checks
    )

    _make_binary(tmp_path)
    _patch_which(monkeypatch)

    def _healthy(args, _kwargs):
        name = Path(args[0]).name
        if name == "node":
            return _completed(args, stdout="v22.1.0\n")
        return _completed(args, stdout="hello from name column\n")

    _patch_run(monkeypatch, _healthy)
    healthy = anydoc_mod.doctor()
    assert healthy.status == "ok"
    assert healthy.summary == "anydoc dependencies healthy"


def test_install_requires_npm_and_rejects_old_node(monkeypatch, tmp_path):
    _bind_anydoc_home(monkeypatch, tmp_path)
    _patch_which(monkeypatch, npm=None)

    def _node(args, _kwargs):
        return _completed(args, stdout="v22.0.0\n")

    _patch_run(monkeypatch, _node)
    missing_npm = anydoc_mod.install(force=False)
    assert missing_npm.ok is False
    assert missing_npm.summary == "npm not found on PATH"

    _patch_which(monkeypatch)

    def _old(args, _kwargs):
        return _completed(args, stdout="v12.0.0\n")

    _patch_run(monkeypatch, _old)
    old = anydoc_mod.install(force=False)
    assert old.ok is False
    assert "need v20+" in old.summary


def test_install_force_npm_failures_and_success(monkeypatch, tmp_path):
    home_root = _bind_anydoc_home(monkeypatch, tmp_path)
    home = home_root / "skill-deps" / "anydoc"
    marker = home / "node_modules" / "marker.txt"
    marker.parent.mkdir(parents=True)
    marker.write_text("old", encoding="utf-8")
    (home / "package.json").write_text('{"keep": true}\n', encoding="utf-8")
    _patch_which(monkeypatch)
    seen = {}

    def _timeout(args, _kwargs):
        name = Path(args[0]).name
        if name == "node":
            return _completed(args, stdout="v20.0.0\n")
        seen["marker_before_npm"] = marker.exists()
        raise subprocess.TimeoutExpired(args, 300)

    _patch_run(monkeypatch, _timeout)
    timed = anydoc_mod.install(force=True)
    assert timed.ok is False
    assert "npm install failed" in timed.summary
    assert seen["marker_before_npm"] is False
    package = json.loads((home / "package.json").read_text(encoding="utf-8"))
    assert package["dependencies"][anydoc_mod.NPM_PACKAGE] == "latest"

    def _os_error(args, _kwargs):
        if Path(args[0]).name == "node":
            return _completed(args, stdout="v20.0.0\n")
        raise OSError("npm missing")

    _patch_run(monkeypatch, _os_error)
    crashed = anydoc_mod.install(force=False)
    assert crashed.ok is False
    assert "npm missing" in crashed.summary

    def _npm_fail(args, _kwargs):
        if Path(args[0]).name == "node":
            return _completed(args, stdout="v20.0.0\n")
        return _completed(args, code=1, stderr="registry down")

    _patch_run(monkeypatch, _npm_fail)
    failed = anydoc_mod.install(force=False)
    assert failed.ok is False
    assert failed.summary == "registry down"

    def _npm_empty(args, _kwargs):
        if Path(args[0]).name == "node":
            return _completed(args, stdout="v20.0.0\n")
        return _completed(args, code=4)

    _patch_run(monkeypatch, _npm_empty)
    empty = anydoc_mod.install(force=False)
    assert empty.ok is False
    assert empty.summary == "npm install exited 4"

    def _no_binary(args, kwargs):
        name = Path(args[0]).name
        if name == "node":
            return _completed(args, stdout="v20.0.0\n")
        assert kwargs["cwd"] == str(home)
        return _completed(args, stdout="added")

    _patch_run(monkeypatch, _no_binary)
    missing_bin = anydoc_mod.install(force=False)
    assert missing_bin.ok is False
    assert "binary missing" in missing_bin.summary

    binary = home / "node_modules" / ".bin" / "anydoc"

    def _success(args, _kwargs):
        name = Path(args[0]).name
        if name == "node":
            return _completed(args, stdout="v20.0.0\n")
        if name == "npm":
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_text("#!/bin/sh\n", encoding="utf-8")
            binary.chmod(0o755)
            return _completed(args, stdout="added")
        return _completed(args, stdout="| name | hello |\n")

    _patch_run(monkeypatch, _success)
    installed = anydoc_mod.install(force=False)
    assert installed.ok is True
    assert installed.summary.startswith("Installed ")
    assert str(home) in installed.summary

    reinstalled = anydoc_mod.install(force=True)
    assert reinstalled.ok is True
    assert reinstalled.summary.startswith("Reinstalled ")


def test_install_skips_npm_when_binary_exists_but_unhealthy(monkeypatch, tmp_path):
    home_root = _bind_anydoc_home(monkeypatch, tmp_path)
    home = home_root / "skill-deps" / "anydoc"
    _make_binary(home_root)
    (home / "package.json").write_text("{}\n", encoding="utf-8")
    _patch_which(monkeypatch)
    calls = []

    def _run(args, _kwargs):
        name = Path(args[0]).name
        calls.append(name)
        if name == "node":
            return _completed(args, stdout="v20.0.0\n")
        if name == "npm":
            raise AssertionError("npm should not run")
        return _completed(args, code=1, stdout="", stderr="")

    _patch_run(monkeypatch, _run)
    result = anydoc_mod.install(force=False)
    assert result.ok is False
    assert result.summary == "anydoc already installed"
    assert "npm" not in calls
    assert (home / "package.json").read_text(encoding="utf-8") == "{}\n"


def test_install_preserves_existing_package_json(monkeypatch, tmp_path):
    home_root = _bind_anydoc_home(monkeypatch, tmp_path)
    home = home_root / "skill-deps" / "anydoc"
    home.mkdir(parents=True)
    (home / "package.json").write_text('{"keep": true}\n', encoding="utf-8")
    _patch_which(monkeypatch)

    def _fail(args, _kwargs):
        if Path(args[0]).name == "node":
            return _completed(args, stdout="v20.0.0\n")
        return _completed(args, code=1, stderr="nope")

    _patch_run(monkeypatch, _fail)
    result = anydoc_mod.install(force=False)
    assert result.ok is False
    assert (home / "package.json").read_text(encoding="utf-8") == '{"keep": true}\n'
