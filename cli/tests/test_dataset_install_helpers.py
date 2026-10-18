"""Bench dataset row shaping, cache sizes, and uninstall."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError

import pytest

from agent_server.bench_service import dataset_install as di


def test_as_list_and_mcq_rows():
    assert di._as_list(None) == []
    assert di._as_list(("a", "b")) == ["a", "b"]

    class _Arr:
        def tolist(self):
            return ["x"]

    assert di._as_list(_Arr()) == ["x"]

    class _Bad:
        def tolist(self):
            raise RuntimeError("no")

    assert di._as_list(_Bad()) == []
    assert di._as_list("nope") == []

    row = di._normalize_mcq_row(
        "mmlu",
        {"question": "Q", "choices": ["a", "b"], "answer": 1, "subject": "math"},
    )
    assert row["answer"] == "B"
    assert di._normalize_mcq_row("mmlu", {"choices": [], "answer": 0}) is None
    assert di._normalize_mcq_row("mmlu", {"choices": ["a"], "answer": "no"}) is None

    pro = di._normalize_mcq_row(
        "mmlu-pro",
        {"question_id": "9", "question": "Q", "options": ["a", "b"], "answer": "b", "category": "law"},
    )
    assert pro["answer"] == "B" and pro["id"] == "9"
    assert di._normalize_mcq_row("mmlu-pro", {"options": ["a"], "answer": "Z"}) is None

    arc = di._normalize_mcq_row(
        "arc-challenge",
        {
            "id": "arc1",
            "question": "Why?",
            "choices": {"text": ["up", "down"], "label": ["A", "B"]},
            "answerKey": "B",
        },
    )
    assert arc["answer"] == "B"
    assert di._normalize_mcq_row("arc-challenge", {"choices": ["a"]}) is None


def test_download_write_and_cache_sizes(monkeypatch, tmp_path):
    class _Resp:
        headers = {"Content-Length": "4"}

        def read(self, n):
            if not hasattr(self, "_done"):
                self._done = True
                return b"data"
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    seen = []
    monkeypatch.setattr(di, "urlopen", lambda req, timeout=300: _Resp())
    body = di._download_bytes("https://example.test/a", token="tok", on_chunk=lambda done, total: seen.append((done, total)))
    assert body == b"data" and seen == [(4, 4)]

    def boom(req, timeout=300):
        raise HTTPError("https://example.test/a", 429, "no", hdrs=None, fp=None)

    monkeypatch.setattr(di, "urlopen", boom)
    with pytest.raises(di.BenchInstallError) as exc:
        di._download_bytes("https://example.test/a")
    assert exc.value.http_status == 429

    monkeypatch.setattr(di, "urlopen", lambda req, timeout=300: (_ for _ in ()).throw(URLError("dns")))
    with pytest.raises(di.BenchInstallError):
        di._download_bytes("https://example.test/a")

    path = tmp_path / "rows.jsonl"
    di._write_jsonl(path, [{"q": "café"}])
    assert di._count_lines(path) == 1
    assert json.loads(path.read_text(encoding="utf-8"))["q"] == "café"

    monkeypatch.setattr(di, "bench_cache_root", lambda: tmp_path)
    assert di.suite_cache_paths("nope") == []
    assert di.suite_cache_paths("bixbench-verified-50")[0].name == "bixbench-verified-50"
    target = di.suite_cache_paths("mmlu")[0]
    target.parent.mkdir(parents=True)
    target.write_text('{"a":1}\n\n', encoding="utf-8")
    assert di.suite_installed_count("mmlu") == 1
    assert di.suite_installed_bytes("mmlu") == target.stat().st_size
    nested = tmp_path / ".cache" / "dir"
    nested.mkdir()
    (nested / "a.txt").write_text("hi", encoding="utf-8")
    assert di._path_size(nested) >= 2
    assert di.total_cache_bytes() >= 2
    assert di._human_bytes(12) == "12 B"
    assert di._human_bytes(2048).endswith("KB")

    monkeypatch.setattr("agent_server.bench_service.install_jobs.is_installing", lambda key: False)
    monkeypatch.setattr("agent_server.bench_service.install_jobs.clear_install_job", lambda key: None)
    gone = di.uninstall_suite("mmlu")
    assert gone.ok and gone.freed_bytes > 0
    empty = di.uninstall_suite("mmlu")
    assert "Nothing cached" in empty.summary
    with pytest.raises(di.BenchInstallError):
        di.uninstall_suite("not-a-suite")
    monkeypatch.setattr("agent_server.bench_service.install_jobs.is_installing", lambda key: True)
    with pytest.raises(di.BenchInstallError):
        di.uninstall_suite("mmlu")
