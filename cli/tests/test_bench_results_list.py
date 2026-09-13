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


def test_partial_completed_lists_as_interrupted(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {})
    _write(
        tmp_path,
        "partial-bix",
        status="completed",
        benchmark="bixbench-verified-50",
        correct=24,
        total=50,
        accuracy=0.48,
        questions=[{"question_id": f"q{i}", "correct": True} for i in range(24)],
    )
    rows = rs.list_results()
    assert rows[0]["status"] == "interrupted"
    assert rows[0]["resumable"] is True
    assert rows[0]["answered"] == 24
    assert rows[0]["correct"] == 24
    ckpt = rs.build_resume_checkpoint("partial-bix")
    assert ckpt is not None
    assert ckpt["suite_id"] == "bixbench-verified-50"
    assert len(ckpt["completed_question_ids"]) == 24


def test_checkpoint_without_result_lists_as_resumable(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {})
    payload = {
        "run_id": "ckpt-only",
        "status": "running",
        "suite_id": "mmlu",
        "model_id": "qwen/qwen3.7-max",
        "remaining_question_ids": ["q2", "q3"],
        "completed_question_ids": ["q1"],
    }
    (tmp_path / "ckpt-only.checkpoint.json").write_text(
        json.dumps(payload) + "\n", encoding="utf-8"
    )
    rows = rs.list_results()
    assert rows[0]["run_id"] == "ckpt-only"
    assert rows[0]["status"] == "interrupted"
    assert rows[0]["resumable"] is True


class _FakeStore:
    def __init__(self, leftover=None, project_tokens=None, session_projects=None):
        self.leftover = leftover or {}
        self.project_tokens = project_tokens or {}
        self.session_projects = session_projects or {}

    def interrupted_bench_questions_by_project(self, project_ids):
        return {pid: list(self.leftover.get(pid) or []) for pid in project_ids}

    def lifetime_tokens_by_project(self, project_ids):
        return {pid: int(self.project_tokens.get(pid) or 0) for pid in project_ids}

    def list_sessions_by_ids(self, ids):
        out = []
        for sid in ids:
            pid = self.session_projects.get(sid)
            if pid:
                out.append(type("S", (), {"project_id": pid})())
        return out


def test_project_usage_and_interrupted_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {})
    _write(
        tmp_path,
        "kimi-bix",
        status="completed",
        project_id="proj-1",
        correct=24,
        total=50,
        questions=[{"question_id": f"bix-{i}-q1"} for i in range(50)],
    )
    rows = rs.list_results()
    attached = rs.attach_usage_and_resume(
        rows,
        stores=[_FakeStore(leftover={"proj-1": ["bix-53-q5"]}, project_tokens={"proj-1": 5_852_925})],
        run_tokens={"kimi-bix": 0},
    )
    assert attached[0]["lifetime_tokens"] == 5_852_925
    assert attached[0]["status"] == "interrupted"
    assert attached[0]["resumable"] is True
    ckpt = rs.build_resume_checkpoint(
        "kimi-bix",
        stores=[_FakeStore(leftover={"proj-1": ["bix-53-q5"]})],
    )
    assert ckpt is not None
    assert ckpt["remaining_question_ids"] == ["bix-53-q5"]
    assert "bix-53-q5" not in ckpt["completed_question_ids"]


def test_leftover_session_for_graded_question_stays_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {})
    _write(
        tmp_path,
        "done-bix",
        status="completed",
        project_id="proj-1",
        correct=35,
        total=50,
        questions=[{"question_id": f"bix-{i}-q1"} for i in range(50)],
    )
    attached = rs.attach_usage_and_resume(
        rs.list_results(),
        stores=[_FakeStore(leftover={"proj-1": ["bix-0-q1", "bix-1-q1"]})],
    )
    assert attached[0]["status"] == "completed"
    assert attached[0]["resumable"] is False


def test_old_project_sessions_do_not_keep_finished_run_resumable(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {})
    _write(
        tmp_path,
        "gemini-bix",
        status="completed",
        project_id="new-proj",
        correct=36,
        total=50,
        questions=[
            {"question_id": f"q{i}", "session_id": "sess-1", "correct": True}
            for i in range(50)
        ],
    )
    attached = rs.attach_usage_and_resume(
        rs.list_results(),
        stores=[
            _FakeStore(
                leftover={"old-proj": ["bix-31-q2", "bix-38-q1"]},
                project_tokens={"new-proj": 0, "old-proj": 16_400_000},
                session_projects={"sess-1": "old-proj"},
            )
        ],
        run_tokens={"gemini-bix": 0},
    )
    assert attached[0]["lifetime_tokens"] == 16_400_000
    assert attached[0]["status"] == "completed"
    assert attached[0]["resumable"] is False


def test_usage_follows_question_sessions_not_tiny_rollup(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {})
    _write(
        tmp_path,
        "kimi-bix",
        status="paused",
        project_id="new-empty",
        lifetime_tokens=6490,
        questions=[
            {"question_id": "bix-11-q1", "session_id": "sess-1"},
            {"question_id": "bix-12-q2", "session_id": "sess-2"},
        ],
    )
    rows = rs.list_results()
    attached = rs.attach_usage_and_resume(
        rows,
        stores=[
            _FakeStore(
                project_tokens={"new-empty": 0, "old-proj": 5_852_925},
                session_projects={"sess-1": "old-proj", "sess-2": "old-proj"},
            )
        ],
        run_tokens={"kimi-bix": 6490},
    )
    assert attached[0]["lifetime_tokens"] == 5_852_925


def test_stalled_leftover_is_not_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {})
    _write(
        tmp_path,
        "stalled-bix",
        status="completed",
        project_id="proj-1",
        correct=36,
        total=50,
        questions=[
            *[{"question_id": f"q{i}", "correct": True} for i in range(49)],
            {
                "question_id": "bix-31-q2",
                "correct": False,
                "eval_mode": "error",
                "terminal": True,
                "judge": {"error": "Cell stalled — no model progress"},
            },
        ],
    )
    (tmp_path / "stalled-bix.checkpoint.json").write_text(
        json.dumps(
            {
                "run_id": "stalled-bix",
                "status": "running",
                "remaining_question_ids": ["bix-31-q2"],
                "completed_question_ids": [f"q{i}" for i in range(49)],
                "project_id": "proj-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    attached = rs.attach_usage_and_resume(
        rs.list_results(),
        stores=[_FakeStore(leftover={"proj-1": ["bix-31-q2"]})],
    )
    assert attached[0]["status"] == "completed"
    assert attached[0]["resumable"] is True
    retry = rs.build_retry_failed_checkpoint("stalled-bix")
    assert retry is not None
    assert retry["remaining_question_ids"] == ["bix-31-q2"]
    rebuilt = rs.build_resume_checkpoint(
        "stalled-bix",
        stores=[_FakeStore(leftover={"proj-1": ["bix-31-q2"]})],
    )
    assert rebuilt is None or not rebuilt.get("remaining_question_ids")


def test_open_bench_ids_need_one_interrupt_or_running():
    from agent_server.store.session_queries import (
        exhausted_bench_question_ids,
        open_bench_question_ids,
    )

    counts = {
        "fresh": {"running": 0, "interrupted": 1},
        "live": {"running": 1, "interrupted": 4},
        "loop": {"running": 0, "interrupted": 5},
    }
    assert set(open_bench_question_ids(counts)) == {"fresh", "live"}
    assert exhausted_bench_question_ids(counts) == ["loop"]


def test_retryable_failures_exclude_graded_wrong(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    _write(
        tmp_path,
        "retry-bix",
        status="completed",
        correct=26,
        total=50,
        questions=[
            {"question_id": "ok", "correct": True, "eval_mode": "str_verifier"},
            {"question_id": "wrong", "correct": False, "eval_mode": "str_verifier"},
            {
                "question_id": "stall",
                "correct": False,
                "eval_mode": "error",
                "terminal": True,
                "judge": {"error": "Cell stalled"},
            },
            {
                "question_id": "dns",
                "correct": False,
                "eval_mode": "llm_verifier",
                "judge": {"error": "[Errno 8] nodename nor servname provided"},
            },
            {
                "question_id": "rate",
                "correct": False,
                "eval_mode": "llm_verifier",
                "raw_response": "Error: 429 rate limit exceeded",
            },
        ],
    )
    row = rs.get_result("retry-bix")
    assert rs.retryable_failure_ids(row) == ["stall", "dns", "rate"]
    ckpt = rs.build_retry_failed_checkpoint("retry-bix")
    assert ckpt is not None
    assert ckpt["force_retry"] is True
    assert ckpt["remaining_question_ids"] == ["stall", "dns", "rate"]
    one = rs.build_retry_failed_checkpoint("retry-bix", question_ids=["wrong"])
    assert one is not None
    assert one["remaining_question_ids"] == ["wrong"]
    assert "wrong" in ckpt["completed_question_ids"]
    assert "ok" in ckpt["completed_question_ids"]
    rows = rs.list_results()
    assert rows[0]["failed_count"] == 3


def test_finished_run_is_not_resumable(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {})
    _write(
        tmp_path,
        "done-bix",
        status="completed",
        correct=24,
        total=50,
        accuracy=0.48,
        questions=[{"question_id": f"q{i}"} for i in range(50)],
    )
    rows = rs.list_results()
    assert rows[0]["status"] == "completed"
    assert rows[0]["resumable"] is False
    assert rs.build_resume_checkpoint("done-bix") is None


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


def test_completed_stack_sibling_is_not_running(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(rs, "_live_run_statuses", lambda: {"suite-pro": "running"})
    _write(tmp_path, "suite-mmlu", status="completed", benchmark="mmlu")
    _write(tmp_path, "suite-pro", status="running", benchmark="mmlu-pro")
    by_id = {row["run_id"]: row["status"] for row in rs.list_results()}
    assert by_id["suite-mmlu"] == "completed"
    assert by_id["suite-pro"] == "running"


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
