"""Bench result list pagination, search, stale status, and rename."""

from __future__ import annotations

import json
from pathlib import Path

from agent_server.bench_service import results_store as rs


def _write(root: Path, run_id: str, **fields) -> None:
    payload = {
        "run_id": run_id,
        "model_id": fields.pop("model_id", "qwen/qwen3.7-max"),
        "benchmark": fields.pop("benchmark", "mmlu"),
        "accuracy": fields.pop("accuracy", 0.8),
        "correct": fields.pop("correct", 8),
        "total": fields.pop("total", 10),
        "time_s": fields.pop("time_s", 12.0),
        "status": fields.pop("status", "completed"),
        **fields,
    }
    (root / f"{run_id}.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_stale_running_lists_as_interrupted(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {})
    _write(tmp_path, "old-mmlu", status="running", benchmark="mmlu")
    rows = rs.list_results()
    assert rows[0]["status"] == "interrupted"


def test_live_inflight_lists_as_running(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {"live-mmlu": "running"})
    _write(tmp_path, "live-mmlu", status="running", benchmark="mmlu")
    rows = rs.list_results()
    assert rows[0]["status"] == "running"


def test_provider_from_environment_and_model_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    _write(
        tmp_path,
        "env-prov",
        model_id="gemini-3.1-flash-lite",
        environment={"runtime": {"provider": "google"}},
    )
    _write(tmp_path, "prefix-prov", model_id="deepseek/deepseek-v4-flash")
    page = rs.list_results_page(limit=10)
    by_id = {row["run_id"]: row for row in page["data"]}
    assert by_id["env-prov"]["provider"] == "google"
    assert by_id["prefix-prov"]["provider"] == "deepseek"


def test_local_profile_is_not_openai(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(
        rs, "_profile_backend_lookup", lambda: {"omlx": "omlx", "unsloth": "unsloth"}
    )
    _write(
        tmp_path,
        "local-omlx",
        provider="openai",
        model_id="Qwen3.6-35B-A3B-OptiQ-4bit",
        environment={
            "runtime": {"provider": "openai", "openai_profile_id": "omlx"}
        },
    )
    _write(
        tmp_path,
        "cloud-openai",
        provider="openai",
        model_id="gpt-5",
        environment={
            "runtime": {"provider": "openai", "openai_profile_id": "openai_cloud"}
        },
    )
    page = rs.list_results_page(limit=10)
    by_id = {row["run_id"]: row for row in page["data"]}
    assert by_id["local-omlx"]["provider"] == "omlx"
    assert by_id["cloud-openai"]["provider"] == "openai"
    assert "omlx" in page["providers"]


def test_search_and_suite_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    _write(tmp_path, "a", benchmark="mmlu", name="nightly sweep")
    _write(tmp_path, "b", benchmark="arc-challenge", model_id="openai/gpt-5")
    page = rs.list_results_page(q="nightly")
    assert [row["run_id"] for row in page["data"]] == ["a"]
    page = rs.list_results_page(suite="arc-challenge")
    assert [row["run_id"] for row in page["data"]] == ["b"]


def test_cursor_pagination(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    for i in range(5):
        _write(tmp_path, f"run-{i}", benchmark="mmlu")
        path = tmp_path / f"run-{i}.json"
        path.touch()
        path.stat()
    # Distinct mtimes
    import os
    import time

    for i in range(5):
        os.utime(tmp_path / f"run-{i}.json", (time.time() + i, time.time() + i))
    first = rs.list_results_page(limit=2)
    assert len(first["data"]) == 2
    assert first["next_cursor"]
    assert first["total"] == 5
    second = rs.list_results_page(limit=2, cursor=first["next_cursor"])
    first_ids = {row["run_id"] for row in first["data"]}
    second_ids = {row["run_id"] for row in second["data"]}
    assert not first_ids & second_ids
    assert second["total"] == 5


def test_provider_filter_and_date_sort(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    _write(tmp_path, "g", provider="google", benchmark="mmlu")
    _write(tmp_path, "o", provider="openai", benchmark="mmlu")
    page = rs.list_results_page(provider="google")
    assert [row["run_id"] for row in page["data"]] == ["g"]
    assert "google" in page["providers"]
    assert "openai" in page["providers"]
    page = rs.list_results_page(provider="google,openai")
    assert {row["run_id"] for row in page["data"]} == {"g", "o"}


def test_date_asc_and_offset_cursor(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    import os
    import time

    for i in range(4):
        _write(tmp_path, f"run-{i}", benchmark="mmlu")
        os.utime(tmp_path / f"run-{i}.json", (time.time() + i, time.time() + i))
    oldest = rs.list_results_page(limit=2, sort="date_asc")
    assert [row["run_id"] for row in oldest["data"]] == ["run-0", "run-1"]
    next_page = rs.list_results_page(
        limit=2, sort="date_asc", cursor=oldest["next_cursor"]
    )
    assert [row["run_id"] for row in next_page["data"]] == ["run-2", "run-3"]
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    _write(tmp_path, "named", name="old")
    row = rs.rename_result("named", "  KEAP1 sweep  ")
    assert row["name"] == "KEAP1 sweep"
    loaded = rs.get_result("named")
    assert loaded["name"] == "KEAP1 sweep"
