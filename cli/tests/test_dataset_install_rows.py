"""Bench dataset row normalization, cache size, and uninstall."""

from __future__ import annotations

from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from agent_server.bench_service import dataset_install as install


def test_row_helpers_and_bytes(tmp_path, monkeypatch):
    assert install._as_list(None) == []
    assert install._as_list(("a",)) == ["a"]

    class _Arr:
        def tolist(self):
            return ["x"]

    assert install._as_list(_Arr()) == ["x"]

    class _Bad:
        def tolist(self):
            raise RuntimeError("no")

    assert install._as_list(_Bad()) == []
    assert install._as_list(3) == []
    assert install._human_bytes(12) == "12 B"
    assert "KB" in install._human_bytes(2048)

    assert install._normalize_mcq_row("mmlu", {"choices": ["a", "b"], "answer": 1, "question": "q", "subject": "bio"})["answer"] == "B"
    assert install._normalize_mcq_row("mmlu", {"choices": [], "answer": 0}) is None
    assert install._normalize_mcq_row("mmlu", {"choices": ["a"], "answer": "nope"}) is None
    pro = install._normalize_mcq_row(
        "mmlu-pro",
        {"options": ["a", "b"], "answer": "A", "question_id": "1", "question": "q", "category": "law"},
    )
    assert pro["answer"] == "A"
    assert install._normalize_mcq_row("mmlu-pro", {"options": ["a"], "answer": "Z"}) is None
    arc = install._normalize_mcq_row(
        "arc-challenge",
        {"choices": {"text": ["sun"], "label": ["A"]}, "answerKey": "A", "id": "9", "question": "q"},
    )
    assert arc["answer"] == "A"
    assert install._normalize_mcq_row("arc-challenge", {"choices": ["nope"]}) is None

    path = tmp_path / "rows.jsonl"
    install._write_jsonl(path, [{"q": "one"}, {"q": "two"}])
    assert install._count_lines(path) == 2

    monkeypatch.setattr(install, "bench_cache_root", lambda: tmp_path)
    cached = tmp_path / ".cache" / "mcq"
    cached.mkdir(parents=True)
    fixture = cached / install._MCQ_SOURCES["mmlu"]["fixture"]
    fixture.write_text('{"q": 1}\n')
    assert install.suite_installed_count("mmlu") == 1
    assert install.suite_installed_bytes("mmlu") > 0
    assert install.suite_cache_paths("nope") == []
    assert install.cache_root() == tmp_path / ".cache"
    assert install.total_cache_bytes() > 0

    chunks = []

    class _Resp:
        headers = {"Content-Length": "4"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, n):
            if self.headers:
                self.headers = {}
                return b"data"
            return b""

    monkeypatch.setattr(install, "urlopen", lambda req, timeout=300: _Resp())
    assert install._download_bytes("https://example.test/a", token="t", on_chunk=lambda done, total: chunks.append((done, total))) == b"data"
    assert chunks[0][1] == 4

    def _http(req, timeout=300):
        raise HTTPError(req.full_url, 429, "slow", hdrs=None, fp=BytesIO(b""))

    monkeypatch.setattr(install, "urlopen", _http)
    with pytest.raises(install.BenchInstallError) as http_exc:
        install._download_bytes("https://example.test/a")
    assert http_exc.value.http_status == 429

    def _url(req, timeout=300):
        raise URLError("dns")

    monkeypatch.setattr(install, "urlopen", _url)
    with pytest.raises(install.BenchInstallError):
        install._download_bytes("https://example.test/a")


def test_uninstall_suite(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "bench_cache_root", lambda: tmp_path)
    monkeypatch.setattr("agent_server.bench_service.install_jobs.is_installing", lambda key: False)
    monkeypatch.setattr("agent_server.bench_service.install_jobs.clear_install_job", lambda key: None)
    with pytest.raises(install.BenchInstallError):
        install.uninstall_suite("not-a-suite")
    monkeypatch.setattr("agent_server.bench_service.install_jobs.is_installing", lambda key: True)
    with pytest.raises(install.BenchInstallError):
        install.uninstall_suite("mmlu")
    monkeypatch.setattr("agent_server.bench_service.install_jobs.is_installing", lambda key: False)
    empty = install.uninstall_suite("mmlu")
    assert empty.freed_bytes == 0

    cached = tmp_path / ".cache" / "mcq"
    cached.mkdir(parents=True)
    fixture = cached / install._MCQ_SOURCES["mmlu"]["fixture"]
    fixture.write_text("row\n")
    removed = install.uninstall_suite("mmlu")
    assert removed.freed_bytes > 0
    assert not fixture.exists()

    folder = tmp_path / ".cache" / "bixbench-verified-50"
    folder.mkdir(parents=True)
    (folder / "capsule.bin").write_bytes(b"1234")
    monkeypatch.setattr(install.shutil, "rmtree", lambda path: (_ for _ in ()).throw(OSError("busy")))

    def _rmtree(path):
        raise OSError("busy")

    monkeypatch.setattr(install.shutil, "rmtree", _rmtree)
    with pytest.raises(install.BenchInstallError):
        install.uninstall_suite("bixbench-verified-50")
