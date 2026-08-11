"""Unit tests for Bench suite dataset install helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_server.bench_service.dataset_install import (
    BenchInstallError,
    install_suite,
)


def test_install_suite_rejects_unknown():
    with pytest.raises(BenchInstallError) as exc:
        install_suite("not-a-suite")
    assert exc.value.status_code == 404


def test_install_mbpp_writes_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    payload = "\n".join(
        json.dumps(
            {
                "task_id": tid,
                "text": f"Write fn {tid}",
                "test_list": [f"assert True  # {tid}"],
                "test_setup_code": "",
            }
        )
        for tid in range(11, 111)
    ).encode("utf-8")
    # Signature mirrors the real helper (keyword-only token + progress callback).
    monkeypatch.setattr(
        mod,
        "_download_bytes",
        lambda url, *, token=None, on_chunk=None: payload,
    )

    result = install_suite("mbpp", force=True)
    assert result.ok
    out = tmp_path / ".cache" / "mcq" / "mbpp.jsonl"
    assert out.is_file()
    rows = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    assert len(rows) == 100
    assert rows[0]["prompt"].startswith("Write fn")
    assert "text" not in rows[0]


def test_install_bixbench_requires_token(monkeypatch: pytest.MonkeyPatch):
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "resolve_hf_token", lambda: "")
    monkeypatch.setattr(mod, "ensure_sandwalk_bench_importable", lambda: True)
    with pytest.raises(BenchInstallError) as exc:
        install_suite("bixbench-verified-50", force=True)
    assert exc.value.needs_hf_token is True
    assert "Hugging Face" in str(exc.value)


def test_start_install_returns_immediately(monkeypatch: pytest.MonkeyPatch):
    import threading
    import time

    from agent_server.bench_service import install_jobs as jobs
    from agent_server.models.bench import BenchInstallResponse

    monkeypatch.setattr(jobs, "_jobs", {})
    started = threading.Event()
    finished = threading.Event()

    def slow_install(suite_id: str, *, force: bool = False, on_progress=None):
        started.set()
        finished.wait(timeout=2)
        if on_progress is not None:
            on_progress(summary="halfway", files_done=1, files_total=2)
        return BenchInstallResponse(
            ok=True,
            suite_id=suite_id,
            summary="done",
            status="done",
        )

    monkeypatch.setattr(jobs, "install_suite", slow_install)
    result = jobs.start_install("mbpp")
    assert result.status == "installing"
    assert jobs.is_installing("mbpp")
    assert started.wait(timeout=1)
    finished.set()
    deadline = time.time() + 2
    while time.time() < deadline and jobs.is_installing("mbpp"):
        time.sleep(0.02)
    job = jobs.get_install_job("mbpp")
    assert job is not None
    assert job.status == "done"


def test_start_install_requires_hf_token_upfront(monkeypatch: pytest.MonkeyPatch):
    from agent_server.bench_service import install_jobs as jobs

    monkeypatch.setattr(jobs, "_jobs", {})
    monkeypatch.setattr(jobs, "resolve_hf_token", lambda: "")
    with pytest.raises(BenchInstallError) as exc:
        jobs.start_install("bixbench-verified-50")
    assert exc.value.needs_hf_token is True


def test_mcq_suites_are_installable():
    """MMLU / MMLU-Pro / ARC-C ship only sample fixtures; Install fetches the rest."""
    from agent_server.bench_service.dataset_install import INSTALLABLE_SUITE_IDS

    for suite_id in ("mmlu", "mmlu-pro", "arc-challenge"):
        assert suite_id in INSTALLABLE_SUITE_IDS


def test_install_mcq_pages_rows_and_normalizes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Rows-API fallback pages through the corpus when no parquet reader exists."""
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(mod, "_HF_ROWS_PAGE", 2)
    monkeypatch.setattr(mod, "_HF_ROWS_PAGE_PAUSE", 0)
    monkeypatch.setattr(mod, "resolve_hf_token", lambda: "")
    # Force the fallback path.
    monkeypatch.setattr(mod, "_parquet_reader", lambda: None)

    rows = [
        {
            "row": {
                "question": f"Q{i}",
                "choices": ["a", "b", "c", "d"],
                "answer": i % 4,
                "subject": "algebra",
            }
        }
        for i in range(5)
    ]

    def fake_download(url: str, *, token=None, on_chunk=None) -> bytes:
        offset = int(url.split("offset=")[1].split("&")[0])
        page = rows[offset : offset + 2]
        return json.dumps({"num_rows_total": len(rows), "rows": page}).encode()

    monkeypatch.setattr(mod, "_download_bytes", fake_download)

    result = mod.install_suite("mmlu", force=True)
    assert result.ok
    out = tmp_path / ".cache" / "mcq" / "mmlu_test.jsonl"
    assert out.is_file()
    written = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    assert len(written) == 5
    # Integer answer indexes become letters the grader can compare.
    assert written[0]["answer"] == "A"
    assert written[1]["answer"] == "B"
    assert written[0]["subject"] == "algebra"


def test_install_mcq_prefers_parquet_single_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """One parquet request beats ~141 rows-API pages, so it must win when available."""
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(mod, "resolve_hf_token", lambda: "")

    calls: list[str] = []

    def fake_download(url: str, *, token=None, on_chunk=None) -> bytes:
        calls.append(url)
        return b"fake-parquet-bytes"

    monkeypatch.setattr(mod, "_download_bytes", fake_download)
    monkeypatch.setattr(
        mod,
        "_parquet_reader",
        lambda: lambda raw: [
            {"question": "Q1", "choices": ["a", "b"], "answer": 1, "subject": "math"}
        ],
    )

    result = mod.install_suite("mmlu", force=True)
    assert result.ok
    assert len(calls) == 1
    assert calls[0].endswith(".parquet")
    out = tmp_path / ".cache" / "mcq" / "mmlu_test.jsonl"
    row = json.loads(out.read_text().splitlines()[0])
    assert row["answer"] == "B"


def test_install_mcq_falls_back_when_parquet_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A corrupt parquet must not fail the install — page the rows API instead."""
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(mod, "_HF_ROWS_PAGE_PAUSE", 0)
    monkeypatch.setattr(mod, "resolve_hf_token", lambda: "")

    def boom(_raw: bytes):
        raise ValueError("not a parquet file")

    monkeypatch.setattr(mod, "_parquet_reader", lambda: boom)

    payload = {
        "num_rows_total": 1,
        "rows": [{"row": {"question": "Q", "choices": ["a", "b"], "answer": 0}}],
    }

    def fake_download(url: str, *, token=None, on_chunk=None) -> bytes:
        if url.endswith(".parquet"):
            return b"garbage"
        return json.dumps(payload).encode()

    monkeypatch.setattr(mod, "_download_bytes", fake_download)

    result = mod.install_suite("mmlu", force=True)
    assert result.ok
    out = tmp_path / ".cache" / "mcq" / "mmlu_test.jsonl"
    assert json.loads(out.read_text().splitlines()[0])["answer"] == "A"


def test_count_lines_ignores_unicode_line_separators(tmp_path: Path):
    """Some MMLU questions embed U+0085; splitlines would over-count records."""
    from agent_server.bench_service.dataset_install import _count_lines

    path = tmp_path / "rows.jsonl"
    path.write_text(
        json.dumps({"question": "a\u0085b"}) + "\n" + json.dumps({"question": "c"}) + "\n",
        encoding="utf-8",
    )
    assert _count_lines(path) == 2


def test_suite_sizes_and_total_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    mcq = tmp_path / ".cache" / "mcq"
    mcq.mkdir(parents=True)
    (mcq / "mmlu_test.jsonl").write_text(
        json.dumps({"question": "q"}) * 0 + ('{"question":"q"}\n' * 10),
        encoding="utf-8",
    )

    assert mod.suite_installed_count("mmlu") == 10
    assert mod.suite_installed_bytes("mmlu") > 0
    # Nothing cached for another suite yet.
    assert mod.suite_installed_bytes("mbpp") == 0
    assert mod.suite_installed_count("mbpp") is None
    assert mod.total_cache_bytes() == mod.suite_installed_bytes("mmlu")
    assert mod.cache_root() == tmp_path / ".cache"


def test_uninstall_suite_removes_file_and_reports_freed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    mcq = tmp_path / ".cache" / "mcq"
    mcq.mkdir(parents=True)
    target = mcq / "mmlu_test.jsonl"
    target.write_text('{"question":"q"}\n' * 50, encoding="utf-8")
    size = target.stat().st_size

    result = mod.uninstall_suite("mmlu")
    assert result.ok
    assert result.freed_bytes == size
    assert result.removed == ["mmlu_test.jsonl"]
    assert not target.exists()

    # Idempotent: removing again is a no-op, not an error.
    again = mod.uninstall_suite("mmlu")
    assert again.ok
    assert again.freed_bytes == 0


def test_uninstall_suite_removes_capsule_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """BixBench caches capsule data in a directory, which dwarfs the JSONL."""
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    caps = tmp_path / ".cache" / "bixbench-verified-50" / "nested"
    caps.mkdir(parents=True)
    (caps / "capsule.bin").write_bytes(b"0" * 4096)

    result = mod.uninstall_suite("bixbench-verified-50")
    assert result.ok
    assert result.freed_bytes >= 4096
    assert not (tmp_path / ".cache" / "bixbench-verified-50").exists()


def test_uninstall_rejects_unknown_suite(monkeypatch: pytest.MonkeyPatch):
    from agent_server.bench_service import dataset_install as mod

    with pytest.raises(BenchInstallError) as exc:
        mod.uninstall_suite("not-a-suite")
    assert exc.value.status_code == 404


def test_uninstall_blocked_while_installing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Deleting a half-written dataset mid-download would corrupt the install."""
    from agent_server.bench_service import dataset_install as mod
    from agent_server.bench_service import install_jobs as jobs

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(jobs, "_jobs", {})
    jobs._jobs["mmlu"] = jobs.InstallJob(suite_id="mmlu", status="installing")

    with pytest.raises(BenchInstallError) as exc:
        mod.uninstall_suite("mmlu")
    assert exc.value.status_code == 409


def test_uninstall_clears_stale_install_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A prior error must not keep showing after the dataset is removed."""
    from agent_server.bench_service import dataset_install as mod
    from agent_server.bench_service import install_jobs as jobs

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(jobs, "_jobs", {})
    jobs._jobs["mmlu"] = jobs.InstallJob(
        suite_id="mmlu", status="error", summary="boom", error="boom"
    )

    mod.uninstall_suite("mmlu")
    assert jobs.install_error("mmlu") is None


def test_missing_parquet_dependency_hint(monkeypatch: pytest.MonkeyPatch):
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "_parquet_reader", lambda: None)
    hint = mod.missing_parquet_dependency()
    assert hint is not None
    assert "bench" in hint
    assert mod.parquet_reader_available() is False

    monkeypatch.setattr(mod, "_parquet_reader", lambda: (lambda raw: []))
    assert mod.missing_parquet_dependency() is None
    assert mod.parquet_reader_available() is True


def test_bench_packs_route_exposes_cache_and_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The catalog carries cache totals, and DELETE reclaims a suite's space."""
    from fastapi.testclient import TestClient

    from agent_server.app import create_app
    from agent_server.bench_service import dataset_install as mod
    from agent_server.bench_service import mcq_suites as mcq

    # Both modules import bench_root separately; patch each so the catalog and the
    # uninstall path agree on where the cache lives.
    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(mcq, "bench_root", lambda: tmp_path)
    mcq_dir = tmp_path / ".cache" / "mcq"
    mcq_dir.mkdir(parents=True)
    (mcq_dir / "mmlu_test.jsonl").write_text(
        '{"question":"q"}\n' * 40, encoding="utf-8"
    )

    app = create_app(store_path=tmp_path / "agent.db")
    with TestClient(app) as client:
        payload = client.get("/v1/bench/packs").json()
        assert payload["cacheBytes"] > 0
        assert payload["cachePath"].endswith(".cache")
        mmlu = next(c for c in payload["data"] if c["id"] == "mmlu")
        assert mmlu["installed"] is True
        assert mmlu["installedCount"] == 40

        removed = client.delete("/v1/bench/packs/mmlu/install")
        assert removed.status_code == 200
        body = removed.json()
        assert body["ok"] is True
        assert body["freedBytes"] > 0

        after = client.get("/v1/bench/packs").json()
        mmlu_after = next(c for c in after["data"] if c["id"] == "mmlu")
        assert mmlu_after["installed"] is False
        # Sizes fall back to what the bundled sample fixture can serve.
        assert max(mmlu_after["sampleSizes"]) <= 30

        assert client.delete("/v1/bench/packs/not-a-suite/install").status_code == 404


def test_install_mcq_skips_unusable_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A row without choices or with an out-of-range answer must not be written."""
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(mod, "_HF_ROWS_PAGE_PAUSE", 0)
    monkeypatch.setattr(mod, "resolve_hf_token", lambda: "")
    monkeypatch.setattr(mod, "_parquet_reader", lambda: None)

    payload = {
        "num_rows_total": 3,
        "rows": [
            {"row": {"question": "ok", "choices": ["a", "b"], "answer": 1}},
            {"row": {"question": "no choices", "choices": [], "answer": 0}},
            {"row": {"question": "bad index", "choices": ["a"], "answer": 9}},
        ],
    }
    monkeypatch.setattr(
        mod,
        "_download_bytes",
        lambda url, *, token=None, on_chunk=None: json.dumps(payload).encode(),
    )

    mod.install_suite("mmlu", force=True)
    out = tmp_path / ".cache" / "mcq" / "mmlu_test.jsonl"
    written = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    assert len(written) == 1
    assert written[0]["answer"] == "B"


def test_install_mcq_arc_maps_label_dict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(mod, "_HF_ROWS_PAGE_PAUSE", 0)
    monkeypatch.setattr(mod, "resolve_hf_token", lambda: "")
    monkeypatch.setattr(mod, "_parquet_reader", lambda: None)

    payload = {
        "num_rows_total": 1,
        "rows": [
            {
                "row": {
                    "id": "Mercury_1",
                    "question": "Why?",
                    "choices": {
                        "text": ["one", "two", "three"],
                        "label": ["A", "B", "C"],
                    },
                    "answerKey": "C",
                }
            }
        ],
    }
    monkeypatch.setattr(
        mod,
        "_download_bytes",
        lambda url, *, token=None, on_chunk=None: json.dumps(payload).encode(),
    )

    mod.install_suite("arc-challenge", force=True)
    out = tmp_path / ".cache" / "mcq" / "arc_challenge.jsonl"
    row = json.loads(out.read_text().splitlines()[0])
    assert row["choices"] == ["one", "two", "three"]
    assert row["labels"] == ["A", "B", "C"]
    assert row["answer"] == "C"


def test_install_mcq_retries_then_reports_rate_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """429s are retried; a persistent one becomes an actionable message."""
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(mod, "_HF_ROWS_RETRIES", 3)
    monkeypatch.setattr(mod, "_HF_ROWS_BACKOFF", 0)
    monkeypatch.setattr(mod, "_HF_ROWS_PAGE_PAUSE", 0)
    monkeypatch.setattr(mod, "resolve_hf_token", lambda: "")
    monkeypatch.setattr(mod, "_parquet_reader", lambda: None)

    calls = {"n": 0}

    def always_429(url: str, *, token=None, on_chunk=None) -> bytes:
        calls["n"] += 1
        raise BenchInstallError("rate limited", status_code=502, http_status=429)

    monkeypatch.setattr(mod, "_download_bytes", always_429)

    with pytest.raises(BenchInstallError) as exc:
        mod.install_suite("mmlu", force=True)
    assert calls["n"] == 3
    assert "rate-limited" in str(exc.value)
    assert "Hugging Face token" in str(exc.value)


def test_install_mcq_recovers_after_transient_429(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(mod, "_HF_ROWS_RETRIES", 3)
    monkeypatch.setattr(mod, "_HF_ROWS_BACKOFF", 0)
    monkeypatch.setattr(mod, "_HF_ROWS_PAGE_PAUSE", 0)
    monkeypatch.setattr(mod, "resolve_hf_token", lambda: "")
    monkeypatch.setattr(mod, "_parquet_reader", lambda: None)

    state = {"failed": False}
    payload = {
        "num_rows_total": 1,
        "rows": [{"row": {"question": "ok", "choices": ["a", "b"], "answer": 0}}],
    }

    def flaky(url: str, *, token=None, on_chunk=None) -> bytes:
        if not state["failed"]:
            state["failed"] = True
            raise BenchInstallError("rate limited", status_code=502, http_status=429)
        return json.dumps(payload).encode()

    monkeypatch.setattr(mod, "_download_bytes", flaky)

    result = mod.install_suite("mmlu", force=True)
    assert result.ok
    assert state["failed"] is True


def test_install_mcq_does_not_retry_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from agent_server.bench_service import dataset_install as mod

    monkeypatch.setattr(mod, "bench_root", lambda: tmp_path)
    monkeypatch.setattr(mod, "_HF_ROWS_RETRIES", 4)
    monkeypatch.setattr(mod, "_HF_ROWS_BACKOFF", 0)
    monkeypatch.setattr(mod, "resolve_hf_token", lambda: "")
    monkeypatch.setattr(mod, "_parquet_reader", lambda: None)

    calls = {"n": 0}

    def gone(url: str, *, token=None, on_chunk=None) -> bytes:
        calls["n"] += 1
        raise BenchInstallError("missing", status_code=502, http_status=404)

    monkeypatch.setattr(mod, "_download_bytes", gone)

    with pytest.raises(BenchInstallError):
        mod.install_suite("mmlu", force=True)
    assert calls["n"] == 1  # no retries for a non-retryable status
