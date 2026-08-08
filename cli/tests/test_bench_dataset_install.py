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
