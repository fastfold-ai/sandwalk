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
    monkeypatch.setattr(mod, "_download_bytes", lambda url, token=None: payload)

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
