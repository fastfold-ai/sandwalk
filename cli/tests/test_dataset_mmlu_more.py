"""Remaining dataset-install branches and the legacy MMLU runner.

HTTP and Hugging Face are mocked. These tests do not download datasets.
"""

from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path
from types import ModuleType
from urllib.error import HTTPError

import pytest

from agent_server.bench_service import dataset_install as di
from agent_server.bench_service import mmlu_runner as mr


def _config(monkeypatch: pytest.MonkeyPatch, load):
    import agent.config as agent_config

    class _Config:
        @staticmethod
        def load():
            return load()

    monkeypatch.setattr(agent_config, "Config", _Config)


def _block_modules(monkeypatch: pytest.MonkeyPatch, names: set[str]) -> None:
    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if name in names or any(name.startswith(prefix + ".") for prefix in names):
            raise ImportError(name)
        return real_import(name, globals, locals, fromlist, level)

    for loaded in list(sys.modules):
        if loaded in names or any(loaded.startswith(prefix + ".") for prefix in names):
            monkeypatch.delitem(sys.modules, loaded, raising=False)
    monkeypatch.setattr(builtins, "__import__", guarded)


def _mount_bixbench(monkeypatch: pytest.MonkeyPatch, download, jsonl_path) -> None:
    pkg = ModuleType("sandwalk_bench")
    pkg.__path__ = []
    mod = ModuleType("sandwalk_bench.bixbench")
    mod.download_jsonl = download
    mod.jsonl_path = jsonl_path
    pkg.bixbench = mod
    monkeypatch.setitem(sys.modules, "sandwalk_bench", pkg)
    monkeypatch.setitem(sys.modules, "sandwalk_bench.bixbench", mod)


def _mbpp_payload() -> bytes:
    lines = [
        "",
        "   ",
        json.dumps({"task_id": 2, "prompt": "low", "test_list": ["assert True"]}),
        json.dumps({"task_id": 900, "prompt": "high", "test_list": ["assert True"]}),
        json.dumps({"prompt": "missing id", "test_list": ["assert True"]}),
        json.dumps({"task_id": 30, "prompt": "   ", "test_list": ["assert True"]}),
        json.dumps({"task_id": 31, "prompt": "no tests", "test_list": []}),
    ]
    for tid in range(110, 10, -1):
        if tid == 11:
            lines.append(
                json.dumps({"task_id": tid, "text": "from text", "test_list": ["assert True"]})
            )
        else:
            lines.append(
                json.dumps({"task_id": tid, "prompt": f"p {tid}", "test_list": ["assert True"]})
            )
    return ("\n".join(lines) + "\n").encode()


def test_resolve_hf_token_saved_env_and_errors(monkeypatch: pytest.MonkeyPatch):
    class _Saved:
        def get(self, key):
            assert key == "mcp.huggingface_api_key"
            return "  saved-tok  "

    _config(monkeypatch, lambda: _Saved())
    monkeypatch.setenv("HF_TOKEN", "env-tok")
    assert di.resolve_hf_token() == "saved-tok"
    assert di.hf_token_configured() is True

    class _Blank:
        def get(self, key):
            return "   "

    _config(monkeypatch, lambda: _Blank())
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("HUGGING_FACE_HUB_TOKEN", "  hub-tok  ")
    assert di.resolve_hf_token() == "hub-tok"

    def _boom():
        raise RuntimeError("config unavailable")

    _config(monkeypatch, _boom)
    monkeypatch.setenv("HF_TOKEN", "  from-env  ")
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    assert di.resolve_hf_token() == "from-env"

    _config(monkeypatch, lambda: _Blank())
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    assert di.resolve_hf_token() == ""
    assert di.hf_token_configured() is False


def test_install_mbpp_filters_sorts_and_reports_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "bench_cache_root", lambda: tmp_path)
    events: list[dict] = []

    def fake_download(url, *, token=None, on_chunk=None):
        assert url == di._MBPP_URL
        assert on_chunk is not None
        on_chunk(8, 20)
        return _mbpp_payload()

    monkeypatch.setattr(di, "_download_bytes", fake_download)
    result = di.install_suite(
        "mbpp", force=True, on_progress=lambda **kwargs: events.append(kwargs)
    )
    assert result.ok
    assert "100 problems" in result.summary
    rows = [
        json.loads(line)
        for line in Path(result.path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["task_id"] for row in rows] == list(range(11, 111))
    assert rows[0]["prompt"] == "from text"
    assert rows[0]["test_setup_code"] == ""
    assert events[0]["summary"] == "Downloading MBPP…"
    assert any(event.get("bytes_done") == 8 and event.get("bytes_total") == 20 for event in events)
    assert events[-1]["label"] == "Done"


def test_install_mbpp_cache_hit_and_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "bench_cache_root", lambda: tmp_path)
    cached = tmp_path / ".cache" / "mcq" / "mbpp.jsonl"
    cached.parent.mkdir(parents=True)
    cached.write_text('{"task_id": 1}\n', encoding="utf-8")
    calls: list[str] = []

    def fake_download(url, *, token=None, on_chunk=None):
        calls.append(url)
        return b""

    monkeypatch.setattr(di, "_download_bytes", fake_download)
    hit = di.install_suite("mbpp")
    assert calls == []
    assert hit.path == str(cached)
    assert "1 problems" in hit.summary

    def one_row(url, *, token=None, on_chunk=None):
        return b'{"task_id": 11, "prompt": "only", "test_list": ["assert True"]}\n'

    monkeypatch.setattr(di, "_download_bytes", one_row)
    with pytest.raises(di.BenchInstallError) as exc:
        di.install_suite("mbpp", force=True)
    assert exc.value.status_code == 502
    assert "incomplete" in str(exc.value)


def _lcb_line(qid: str, **overrides) -> str:
    row = {
        "question_id": qid,
        "question_title": f"T {qid}",
        "question_content": f"body {qid}",
        "public_test_cases": "assert True",
        "starter_code": "",
        "difficulty": "",
    }
    row.update(overrides)
    return json.dumps(row)


def test_install_livecodebench_merges_files(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "bench_cache_root", lambda: tmp_path)
    special = _lcb_line(
        "special",
        question_title="Title",
        question_content="body",
        public_test_cases=[{"input": "1"}],
        starter_code="code",
        difficulty="hard",
    )
    junk = "\n".join(
        [
            "",
            json.dumps({"question_content": "no id", "public_test_cases": "x"}),
            json.dumps({"question_id": "   ", "question_content": "blank", "public_test_cases": "x"}),
            json.dumps({"question_id": "empty-body", "question_content": "  ", "public_test_cases": "x"}),
            json.dumps({"question_id": "no-public", "question_content": "c", "public_test_cases": None}),
            json.dumps({"question_id": "blank-public", "question_content": "c", "public_test_cases": ""}),
            json.dumps({"question_id": "list-public", "question_content": "c", "public_test_cases": []}),
            special,
        ]
    )
    goods = "\n".join(_lcb_line(f"q{i}") for i in range(400))
    payloads = {
        "test.jsonl": (junk + "\n" + goods + "\n").encode(),
        "test2.jsonl": (_lcb_line("special") + "\n" + _lcb_line("extra") + "\n").encode(),
    }
    for name in di._LCB_FILES[2:]:
        payloads[name] = b"\n"
    urls: list[str] = []
    events: list[dict] = []

    def fake_download(url, *, token=None, on_chunk=None):
        urls.append(url)
        assert on_chunk is not None
        on_chunk(3, 9)
        on_chunk(1, None)
        on_chunk(1, 0)
        return payloads[url.rsplit("/", 1)[-1]]

    monkeypatch.setattr(di, "_download_bytes", fake_download)
    result = di.install_suite(
        " livecodebench ",
        force=True,
        on_progress=lambda **kwargs: events.append(kwargs),
    )
    assert result.ok
    assert len(urls) == len(di._LCB_FILES)
    rows = [
        json.loads(line)
        for line in Path(result.path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_id = {row["question_id"]: row for row in rows}
    assert "special" in by_id and "extra" in by_id and "q0" in by_id
    assert len(rows) == 402
    assert json.loads(by_id["special"]["public_test_cases"]) == [{"input": "1"}]
    assert by_id["q0"]["starter_code"] == ""
    assert by_id["q0"]["difficulty"] == ""
    assert any(event.get("bytes_total") == 9 for event in events)
    assert any(event.get("bytes_total") is None and event.get("bytes_done") for event in events)
    assert "402 problems" in result.summary

    cached = di.install_suite("livecodebench")
    assert cached.path == result.path
    assert len(urls) == len(di._LCB_FILES)


def test_install_livecodebench_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "bench_cache_root", lambda: tmp_path)

    def fake_download(url, *, token=None, on_chunk=None):
        if on_chunk is not None:
            on_chunk(1, None)
        name = url.rsplit("/", 1)[-1]
        return (_lcb_line(name) + "\n").encode()

    monkeypatch.setattr(di, "_download_bytes", fake_download)
    with pytest.raises(di.BenchInstallError) as exc:
        di.install_suite("livecodebench", force=True)
    assert exc.value.status_code == 502
    assert "incomplete" in str(exc.value)
    assert not (tmp_path / ".cache" / "mcq" / "livecodebench.jsonl").exists()


def test_install_bixbench_success_and_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "resolve_hf_token", lambda: "hf-tok")
    monkeypatch.setattr(di, "ensure_sandwalk_bench_importable", lambda: True)
    dest = tmp_path / "bix.jsonl"
    dest.write_text('{"task": 1}\n{"task": 2}\n', encoding="utf-8")
    events: list[dict] = []

    def download(token, force):
        assert token == "hf-tok" and force is True
        return dest

    _mount_bixbench(monkeypatch, download, lambda: tmp_path / "unused.jsonl")
    result = di.install_suite(
        "bixbench-verified-50",
        force=True,
        on_progress=lambda **kwargs: events.append(kwargs),
    )
    assert result.ok
    assert result.path == str(dest)
    assert "2 tasks" in result.summary
    assert any(event.get("label") == "Done" and event.get("bytes_done") == dest.stat().st_size for event in events)

    missing = tmp_path / "absent.jsonl"
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")

    def download_missing(token, force):
        return missing

    _mount_bixbench(monkeypatch, download_missing, lambda: empty)
    fallback = di.install_suite("bixbench-verified-50", force=True)
    assert fallback.path == str(empty)
    assert "0 tasks" in fallback.summary

    def download_gone(token, force):
        return missing

    _mount_bixbench(monkeypatch, download_gone, lambda: missing)
    progress: list[dict] = []
    path = di._install_bixbench(force=False, on_progress=lambda **kwargs: progress.append(kwargs))
    assert path == missing
    assert any(event.get("bytes_total") is None and event.get("label") == "Done" for event in progress)


def test_install_bixbench_token_import_and_download_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "resolve_hf_token", lambda: "hf-tok")
    monkeypatch.setattr(di, "ensure_sandwalk_bench_importable", lambda: False)
    with pytest.raises(di.BenchInstallError) as missing_pkg:
        di.install_suite("bixbench-verified-50")
    assert missing_pkg.value.status_code == 500

    monkeypatch.setattr(di, "ensure_sandwalk_bench_importable", lambda: True)

    def raise_http(code: int):
        def download(token, force):
            raise HTTPError("https://huggingface.co/bix", code, "no", hdrs=None, fp=None)

        return download

    _mount_bixbench(monkeypatch, raise_http(401), lambda: tmp_path / "x")
    with pytest.raises(di.BenchInstallError) as denied:
        di.install_suite("bixbench-verified-50")
    assert denied.value.status_code == 401
    assert denied.value.needs_hf_token is True

    _mount_bixbench(monkeypatch, raise_http(403), lambda: tmp_path / "x")
    with pytest.raises(di.BenchInstallError) as forbidden:
        di.install_suite("bixbench-verified-50")
    assert forbidden.value.needs_hf_token is True

    _mount_bixbench(monkeypatch, raise_http(500), lambda: tmp_path / "x")
    with pytest.raises(di.BenchInstallError) as http_fail:
        di.install_suite("bixbench-verified-50")
    assert http_fail.value.status_code == 502
    assert "HTTP 500" in str(http_fail.value)

    def raise_token(token, force):
        raise RuntimeError("HF_TOKEN was rejected")

    _mount_bixbench(monkeypatch, raise_token, lambda: tmp_path / "x")
    with pytest.raises(di.BenchInstallError) as token_exc:
        di.install_suite("bixbench-verified-50")
    assert token_exc.value.status_code == 400
    assert token_exc.value.needs_hf_token is True

    def raise_other(token, force):
        raise RuntimeError("network down")

    _mount_bixbench(monkeypatch, raise_other, lambda: tmp_path / "x")
    with pytest.raises(di.BenchInstallError) as other:
        di.install_suite("bixbench-verified-50")
    assert other.value.status_code == 502
    assert "network down" in str(other.value)


def test_install_mcq_cache_empty_and_partial_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "bench_cache_root", lambda: tmp_path)
    monkeypatch.setattr(di, "_parquet_reader", lambda: None)
    monkeypatch.setattr(di, "_HF_ROWS_PAGE_PAUSE", 0)
    cached = tmp_path / ".cache" / "mcq" / di._MCQ_SOURCES["mmlu"]["fixture"]
    cached.parent.mkdir(parents=True)
    cached.write_text('{"question": "cached"}\n', encoding="utf-8")
    hit = di.install_suite("mmlu")
    assert hit.path == str(cached)
    assert "1 questions" in hit.summary

    cached.unlink()

    def empty_page(url, *, token=None, on_chunk=None):
        return b"{}"

    monkeypatch.setattr(di, "_download_bytes", empty_page)
    with pytest.raises(di.BenchInstallError) as empty:
        di.install_suite("mmlu", force=True)
    assert empty.value.status_code == 502
    assert "no usable" in str(empty.value)

    partial = cached.with_name(cached.name + ".partial")
    partial.write_text("{not-json\n", encoding="utf-8")
    real_unlink = Path.unlink

    def flaky_unlink(self, *args, **kwargs):
        if self.name.endswith(".partial"):
            raise OSError("busy")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    page = {
        "num_rows_total": 1,
        "rows": [{"row": {"question": "Q", "choices": ["a", "b"], "answer": 0, "subject": "math"}}],
    }
    monkeypatch.setattr(
        di,
        "_download_bytes",
        lambda url, *, token=None, on_chunk=None: json.dumps(page).encode(),
    )
    repaired = di.install_suite("mmlu", force=False)
    assert repaired.ok
    written = json.loads(Path(repaired.path).read_text(encoding="utf-8").splitlines()[0])
    assert written["answer"] == "A"
    assert partial.is_file()


def test_install_mcq_resumes_partial_and_short_page(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "bench_cache_root", lambda: tmp_path)
    monkeypatch.setattr(di, "_parquet_reader", lambda: None)
    monkeypatch.setattr(di, "_HF_ROWS_PAGE", 10)
    monkeypatch.setattr(di, "_HF_ROWS_PAGE_PAUSE", 0)
    out = tmp_path / ".cache" / "mcq" / di._MCQ_SOURCES["arc-challenge"]["fixture"]
    out.parent.mkdir(parents=True)
    kept = {
        "id": "old",
        "question": "kept",
        "choices": ["up"],
        "labels": ["A"],
        "answer": "A",
        "subject": "science",
    }
    partial = out.with_name(out.name + ".partial")
    partial.write_text("\n   \n" + json.dumps(kept) + "\n", encoding="utf-8")
    events: list[dict] = []

    def fake_fetch(src, *, offset, length):
        assert src["dataset"] == "allenai/ai2_arc"
        assert offset == 1 and length == 10
        return {
            "num_rows_total": "many",
            "rows": [
                None,
                {"row": ["nope"]},
                {"row": {"choices": {"text": [], "label": ["A"]}, "answerKey": "A"}},
                {
                    "row": {
                        "id": "new",
                        "question": "Why?",
                        "choices": {"text": ["one", "two"], "label": ["A", "B"]},
                        "answerKey": "B",
                    }
                },
            ],
        }

    monkeypatch.setattr(di, "_fetch_hf_rows", fake_fetch)
    result = di.install_suite(
        "arc-challenge",
        on_progress=lambda **kwargs: events.append(kwargs),
    )
    assert result.ok
    rows = [
        json.loads(line)
        for line in Path(result.path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["id"] for row in rows] == ["old", "new"]
    assert rows[1]["answer"] == "B"
    assert not partial.exists()
    assert any(event.get("questions_done") == 2 for event in events)


def test_fetch_hf_rows_rejects_bad_payloads_and_rate_limit(monkeypatch):
    monkeypatch.setattr(di, "resolve_hf_token", lambda: "")
    monkeypatch.setattr(di, "_HF_ROWS_BACKOFF", 0)
    src = di._MCQ_SOURCES["mmlu"]

    monkeypatch.setattr(di, "_download_bytes", lambda url, *, token=None, on_chunk=None: b"not-json")
    with pytest.raises(di.BenchInstallError) as bad_json:
        di._fetch_hf_rows(src, offset=0, length=10)
    assert bad_json.value.status_code == 502

    monkeypatch.setattr(di, "_download_bytes", lambda url, *, token=None, on_chunk=None: b"[1]")
    with pytest.raises(di.BenchInstallError) as bad_type:
        di._fetch_hf_rows(src, offset=0, length=10)
    assert "Unexpected response" in str(bad_type.value)

    calls = {"n": 0}

    def always_429(url, *, token=None, on_chunk=None):
        assert token == "hf-tok"
        calls["n"] += 1
        raise di.BenchInstallError("limited", status_code=502, http_status=429)

    monkeypatch.setattr(di, "resolve_hf_token", lambda: "hf-tok")
    monkeypatch.setattr(di, "_HF_ROWS_RETRIES", 2)
    monkeypatch.setattr(di, "_download_bytes", always_429)
    with pytest.raises(di.BenchInstallError) as limited:
        di._fetch_hf_rows(src, offset=3, length=10)
    assert calls["n"] == 2
    assert limited.value.http_status == 429
    assert "Install again." in str(limited.value)
    assert "add a Hugging Face token" not in str(limited.value)


def test_mcq_parquet_without_url_and_chunk_progress(monkeypatch):
    assert di._mcq_rows_from_parquet("mmlu", {"fixture": "mmlu_test.jsonl", "title": "MMLU"}) is None
    events: list[dict] = []

    def fake_download(url, *, token=None, on_chunk=None):
        assert token == "hf-tok"
        assert url.endswith(".parquet")
        assert on_chunk is not None
        on_chunk(4, 9)
        on_chunk(4, None)
        return b"parquet-bytes"

    monkeypatch.setattr(di, "resolve_hf_token", lambda: "hf-tok")
    monkeypatch.setattr(di, "_download_bytes", fake_download)
    monkeypatch.setattr(
        di,
        "_parquet_reader",
        lambda: lambda raw: [
            {"question": "Q", "choices": ["a", "b"], "answer": 1, "subject": "math"},
            {"choices": [], "answer": 0},
        ],
    )
    rows = di._mcq_rows_from_parquet(
        "mmlu",
        di._MCQ_SOURCES["mmlu"],
        on_progress=lambda **kwargs: events.append(kwargs),
    )
    assert rows is not None and rows[0]["answer"] == "B"
    assert any(event.get("bytes_done") == 4 for event in events)
    assert any(event.get("questions_done") == 1 for event in events)

    monkeypatch.setattr(di, "_parquet_reader", lambda: lambda raw: [{"choices": [], "answer": 0}])
    assert di._mcq_rows_from_parquet("mmlu", di._MCQ_SOURCES["mmlu"]) is None


def test_parquet_reader_pyarrow_duckdb_and_missing(monkeypatch):
    reader = di._parquet_reader()
    assert reader is not None
    failed = False
    try:
        reader(b"not-a-parquet-file")
    except Exception:
        failed = True
    assert failed is True

    _block_modules(monkeypatch, {"pyarrow"})

    class _Rel:
        columns = ("question",)

        def fetchall(self):
            return [("hello",)]

    fake = ModuleType("duckdb")

    def _sql(query: str):
        assert "read_parquet" in query
        return _Rel()

    fake.sql = _sql
    monkeypatch.setitem(sys.modules, "duckdb", fake)
    duck = di._parquet_reader()
    assert duck is not None
    assert duck(b"parquet") == [{"question": "hello"}]

    _block_modules(monkeypatch, {"pyarrow", "duckdb"})
    assert di._parquet_reader() is None
    assert di.parquet_reader_available() is False
    hint = di.missing_parquet_dependency()
    assert hint is not None and "bench" in hint


def test_normalize_arc_and_size_errors(monkeypatch):
    assert (
        di._normalize_mcq_row(
            "arc-challenge",
            {"choices": {"text": [], "label": ["A"]}, "answerKey": "A"},
        )
        is None
    )
    assert (
        di._normalize_mcq_row(
            "arc-challenge",
            {"choices": {"text": ["sun"], "label": ["A"]}, "answerKey": "Z"},
        )
        is None
    )

    class _Stat:
        def __init__(self, size: int) -> None:
            self.st_size = size

    class _Child:
        def __init__(self, size: int | None) -> None:
            self._size = size

        def is_file(self) -> bool:
            return True

        def stat(self):
            if self._size is None:
                raise OSError("stat")
            return _Stat(self._size)

    class _Dir:
        def is_file(self) -> bool:
            return False

        def is_dir(self) -> bool:
            return True

        def rglob(self, pattern: str):
            return [_Child(None), _Child(4)]

    class _BrokenFile:
        def is_file(self) -> bool:
            return True

        def stat(self):
            raise OSError("stat")

    assert di._path_size(_BrokenFile()) == 0
    assert di._path_size(_Dir()) == 4

    class _Unreadable:
        def is_file(self) -> bool:
            return True

        def open(self, *args, **kwargs):
            raise OSError("denied")

    monkeypatch.setattr(di, "suite_cache_paths", lambda suite_id: [_Unreadable()])
    assert di.suite_installed_count("mmlu") is None


class _Settings:
    provider = "anthropic"
    model = "orig-model"


class _Content:
    def __init__(self, content) -> None:
        self.content = content


class _NoContent:
    content = None

    def __str__(self) -> str:
        return "Answer: C"


def _bind_mmlu(monkeypatch: pytest.MonkeyPatch, model, settings: _Settings | None = None):
    import agent.config as agent_config
    import agent.deepagents_runtime.chat_model as chat_model
    import agent_server.bench_service.environment as environment
    import agent_server.settings_service as settings_mod

    current = settings or _Settings()
    updates: list[tuple[str | None, str | None]] = []
    saved: dict = {}
    seen: dict = {}

    class _Config:
        @staticmethod
        def load():
            return {"loaded": True}

    class _Service:
        @staticmethod
        def get():
            return current

        @staticmethod
        def update(payload):
            updates.append((payload.provider, payload.model))
            return current

    def capture(*args, **kwargs):
        seen["env_args"] = args
        seen["env"] = kwargs
        return {"snapshot": True}

    def save_result(result):
        saved["result"] = result

    monkeypatch.setattr(agent_config, "Config", _Config)
    monkeypatch.setattr(chat_model, "build_chat_model", lambda config: model)
    monkeypatch.setattr(environment, "capture_bench_environment", capture)
    # Bound at import time in mmlu_runner, so patch the names it actually calls.
    monkeypatch.setattr(mr, "new_run_id", lambda: "run-mmlu")
    monkeypatch.setattr(mr, "save_result", save_result)
    monkeypatch.setattr(settings_mod, "SettingsService", _Service)
    return updates, saved, seen


def test_mmlu_wrappers_delegate(monkeypatch):
    monkeypatch.setattr(mr, "load_mcq_items", lambda suite, n=30: [{"suite": suite, "n": n}])
    assert mr.load_mmlu_items(4) == [{"suite": "mmlu", "n": 4}]
    item = {"question": "What?", "choices": ["no", "yes"], "answer": "B", "subject": "math"}
    prompt = mr.format_mmlu_prompt(item)
    assert "What?" in prompt
    assert "Answer:" in prompt


def test_run_mmlu_grades_text_list_and_errors(monkeypatch):
    items = [
        {"question": "Q text", "choices": ["no", "yes"], "answer": "A", "subject": "math"},
        {"question": "Q list", "choices": ["no", "yes"], "answer": "B", "subject": "law"},
        {"question": "Q none", "choices": ["no", "yes"], "answer": "C", "subject": "bio"},
        {"question": "Q err", "choices": ["no", "yes"], "answer": "D", "subject": "chem"},
    ]
    monkeypatch.setattr(mr, "load_mcq_items", lambda suite, n=30: items)
    progress: list[dict] = []

    class _Model:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def invoke(self, prompt: str):
            self.prompts.append(prompt)
            if "Q list" in prompt:
                return _Content([7, {"text": "Answer: B"}])
            if "Q none" in prompt:
                return _NoContent()
            if "Q err" in prompt:
                raise RuntimeError("model down")
            return _Content("Answer: A")

    model = _Model()
    updates, saved, seen = _bind_mmlu(monkeypatch, model)
    result = mr.run_mmlu(
        model_id="model-a",
        provider="openai",
        sample_size=4,
        thinking=True,
        on_progress=lambda event: progress.append(event),
    )
    assert result["run_id"] == "run-mmlu"
    assert result["model_id"] == "model-a"
    assert result["benchmark"] == "mmlu"
    assert result["thinking_used"] is True
    assert result["correct"] == 3
    assert result["total"] == 4
    assert result["questions"][0]["correct"] is True
    assert result["questions"][0]["category"] == "math"
    assert result["questions"][1]["predicted"] == "B"
    assert result["questions"][2]["predicted"] == "C"
    assert result["questions"][3]["raw_response"].startswith("ERROR: model down")
    assert result["questions"][3]["correct"] is False
    assert saved["result"] is result
    assert seen["env_args"] == (None,)
    assert seen["env"]["model_id"] == "model-a"
    assert seen["env"]["provider"] == "openai"
    assert seen["env"]["thinking"] is True
    assert seen["env"]["suite_id"] == "mmlu"
    assert updates == [("openai", "model-a"), ("anthropic", "orig-model")]
    assert [event["bench_current"] for event in progress] == [0, 1, 2, 3]
    assert progress[0]["benchmark"] == "mmlu"
    assert len(model.prompts) == 4


def test_run_mmlu_cancel_uses_current_settings(monkeypatch):
    monkeypatch.setattr(
        mr,
        "load_mcq_items",
        lambda suite, n=30: [
            {"question": "Q", "choices": ["a", "b"], "answer": "A", "subject": "math"}
        ],
    )

    class _Model:
        def invoke(self, prompt: str):
            raise AssertionError("cancelled before invoke")

    updates, saved, seen = _bind_mmlu(monkeypatch, _Model())
    result = mr.run_mmlu(
        model_id="",
        provider=None,
        sample_size=1,
        thinking=False,
        on_progress=None,
        cancel_check=lambda: True,
    )
    assert result["questions"] == []
    assert result["model_id"] == "orig-model"
    assert result["accuracy"] == 0.0
    assert result["environment"]["snapshot"] is True
    assert seen["env"]["provider"] == "anthropic"
    assert seen["env"]["thinking"] is False
    assert updates == [("anthropic", "orig-model")]
    assert saved["result"]["total"] == 0
