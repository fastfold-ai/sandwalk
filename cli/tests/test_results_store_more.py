"""Extra coverage for bench result files, resume checkpoints, and providers."""

from __future__ import annotations

import base64
import json
import os
import time

import agent.config as agent_config
from agent_server.bench_service import checkpoint as checkpoint_mod
from agent_server.bench_service import results_store as rs


def _dir_of(path):
    def _results_dir():
        return path

    return _results_dir


def _no_live():
    return {}


def _no_profiles():
    return {}


def _isolate(monkeypatch, tmp_path):
    results = _dir_of(tmp_path)
    monkeypatch.setattr(rs, "results_dir", results)
    monkeypatch.setattr(checkpoint_mod, "results_dir", results)
    monkeypatch.setattr(rs, "_live_run_statuses", _no_live)
    monkeypatch.setattr(rs, "_profile_backend_lookup", _no_profiles)


def _write_json(path, payload):
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


class _Session:
    def __init__(self, project_id):
        self.project_id = project_id


class _NoLookup:
    """Store with none of the optional bench lookups."""


class _BoomStore:
    def list_sessions_by_ids(self, ids):
        raise RuntimeError("sessions down")

    def interrupted_bench_questions_by_project(self, project_ids):
        raise RuntimeError("leftover down")

    def lifetime_tokens_by_project(self, project_ids):
        raise RuntimeError("tokens down")

    def bench_question_session_counts(self, project_ids):
        raise RuntimeError("counts down")


class _UsageStore:
    def list_sessions_by_ids(self, ids):
        return [
            {"project_id": "from-dict"},
            {"project_id": ""},
            _Session("from-obj"),
        ]

    def interrupted_bench_questions_by_project(self, project_ids):
        return {"proj-live": ["q-open"], "from-dict": ["q-old"]}

    def lifetime_tokens_by_project(self, project_ids):
        return {"proj-live": 15, "from-dict": "9"}


class _BoomLeftover:
    def interrupted_bench_questions_by_project(self, project_ids):
        raise RuntimeError("leftover down")


class _LeftoverStore:
    def interrupted_bench_questions_by_project(self, project_ids):
        return {project_ids[0]: ["q-left", "q-stall", " "]}


class _EmptyCounts:
    def bench_question_session_counts(self, project_ids):
        return None


class _ExhaustedStore:
    def bench_question_session_counts(self, project_ids):
        return {
            project_ids[0]: {
                "q1": {"running": 0, "interrupted": 2},
                "q-extra": {"running": 0, "interrupted": 2},
            }
        }


class _DeleteStore:
    def __init__(self):
        self.sessions = []
        self.projects = []

    def list_sessions(self, project_id=None, include_bench=True):
        return [{"id": "sess-del"}]

    def delete_session(self, sid):
        self.sessions.append(sid)
        return True

    def delete_project(self, pid):
        self.projects.append(pid)


class _ClearStore:
    def __init__(self, root):
        self.root = root
        self.sessions = []
        self.projects = []

    def list_sessions(self, project_id=None, include_bench=True):
        _write_json(
            self.root / "late.checkpoint.json",
            {"run_id": "late", "status": "paused"},
        )
        return [{"id": "sess-1"}]

    def delete_session(self, sid):
        self.sessions.append(sid)
        return True

    def delete_project(self, pid):
        self.projects.append(pid)


def test_resolve_provider_and_swallowed_lookup_errors(monkeypatch):
    assert rs.resolve_bench_provider("openai", profile_id="ollama", profiles={}) == "ollama"
    assert (
        rs.resolve_bench_provider("openai", profile_id="box", profiles={"box": "other"})
        == "box"
    )
    assert rs.resolve_bench_provider("openai", profiles={"": "other"}) == "other"
    assert rs.resolve_bench_provider("openai", profile_id="lab", profiles={}) == "lab"
    assert (
        rs.resolve_bench_provider("local", profile_id="lab", profiles={"lab": "openai"})
        == "openai"
    )
    assert (
        rs.resolve_bench_provider(
            environment={"model_id": "anthropic/claude"}, profiles={}
        )
        == "anthropic"
    )
    assert (
        rs.resolve_bench_provider(
            environment={"model": {"model_id": "google/gemini"}}, profiles={}
        )
        == "google"
    )
    assert (
        rs._provider_from_row({"model_id": "mistral/mixtral", "provider": ""}, profiles={})
        == "mistral"
    )

    class _BrokenConfig:
        def openai_profiles(self, include_cloud=True):
            raise RuntimeError("profiles unavailable")

    monkeypatch.setattr(agent_config, "Config", _BrokenConfig)
    assert rs._profile_backend_lookup() == {}

    def _explode():
        raise RuntimeError("queue down")

    monkeypatch.setattr(
        "agent_server.bench_service.queue_runner.live_run_statuses",
        _explode,
    )
    assert rs._live_run_statuses() == {}


def test_save_list_page_rename_delete_export(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    generated = rs.save_result({"benchmark": "arc", "status": "completed"})
    assert generated.is_file()
    loaded = rs.get_result(generated.stem)
    assert loaded["run_id"] == generated.stem
    assert loaded["created_at"]

    for index, name in enumerate(("one", "two", "three")):
        path = rs.save_result(
            {
                "run_id": name,
                "benchmark": "mmlu",
                "status": "completed",
                "provider": "google",
                "model_id": "g",
                "name": name,
                "questions": ["skip-me", {"question_id": "q", "sessionId": f"s-{name}"}],
                "total": 1,
            }
        )
        os.utime(path, (time.time() + index, time.time() + index))

    page = rs.list_results_page(limit=1)
    assert page["total"] == 4
    assert [row["run_id"] for row in page["data"]] == ["three"]
    assert page["data"][0]["usage_session_ids"] == ["s-three"]
    assert page["next_cursor"]
    nxt = rs.list_results_page(limit=1, cursor=page["next_cursor"])
    assert [row["run_id"] for row in nxt["data"]] == ["two"]
    listed = rs.list_results(limit=10)
    assert {row["run_id"] for row in listed} >= {"one", "two", "three"}

    renamed = rs.rename_result("one", "  hello   world  ")
    assert renamed["name"] == "hello world"
    trimmed = rs.rename_result("two", "n" * 150)
    assert trimmed["name"] == "n" * 120
    blank = rs.rename_result("one", "   ")
    assert "name" not in blank
    assert rs.get_result("one")["benchmark"] == "mmlu"
    assert rs.rename_result("missing", "x") is None

    exported = rs.export_path("two")
    assert exported is not None and exported.is_file()
    assert rs.export_path("missing") is None
    (tmp_path / "corrupt.json").write_text("{", encoding="utf-8")
    assert rs.get_result("corrupt") is None
    assert rs.export_path("corrupt").is_file()

    rs.save_result(
        {
            "run_id": "doomed",
            "project_id": "proj-d",
            "status": "completed",
            "benchmark": "mmlu",
            "questions": [],
            "total": 0,
        }
    )
    _write_json(
        tmp_path / "doomed.checkpoint.json",
        {"run_id": "doomed", "status": "paused"},
    )
    store = _DeleteStore()
    assert rs.delete_result("doomed", store=store) is True
    assert store.sessions == ["sess-del"]
    assert store.projects == ["proj-d"]
    assert not (tmp_path / "doomed.json").exists()
    assert not (tmp_path / "doomed.checkpoint.json").exists()
    assert rs.delete_result("doomed") is False


def test_clear_results_removes_files_and_project_sessions(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    _write_json(tmp_path / "early.checkpoint.json", {"run_id": "early", "status": "paused"})
    _write_json(
        tmp_path / "run-clear.json",
        {"run_id": "run-clear", "project_id": "proj-clear", "status": "completed"},
    )
    (tmp_path / "bad-clear.json").write_text("{", encoding="utf-8")
    _write_json(tmp_path / "plain.json", {"run_id": "plain", "status": "completed"})
    (tmp_path / "array-clear.json").write_text("[]", encoding="utf-8")
    store = _ClearStore(tmp_path)
    assert rs.clear_results(store=store) == (6, 1)
    assert store.sessions == ["sess-1"]
    assert store.projects == ["proj-clear"]
    assert list(tmp_path.glob("*.json")) == []


def test_list_page_filters_lean_rows_and_checkpoints(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)

    def _live():
        return {"inflight": "running"}

    def _profiles():
        return {"omlx": "omlx"}

    monkeypatch.setattr(rs, "_live_run_statuses", _live)
    monkeypatch.setattr(rs, "_profile_backend_lookup", _profiles)
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "array.json").write_text("[]", encoding="utf-8")
    (tmp_path / "folder.json").mkdir()
    (tmp_path / "shape.checkpoint.json").write_text("[]", encoding="utf-8")
    _write_json(
        tmp_path / "only.checkpoint.json",
        {
            "run_id": "only",
            "status": "interrupted",
            "suite_id": "mmlu",
            "provider": "google",
            "remaining_question_ids": ["q"],
        },
    )
    rs.save_result(
        {
            "run_id": "inflight",
            "status": "running",
            "benchmark": "mmlu",
            "provider": "openai",
            "model_id": "gpt",
            "questions": [{"question_id": "q1"}, {"question_id": "q2"}],
            "total": 2,
            "environment": {
                "runtime": {"provider": "openai", "openai_profile_id": "omlx"}
            },
        }
    )
    rs.save_result(
        {
            "run_id": "partial",
            "status": "completed",
            "benchmark": "arc",
            "model_id": "deepseek/flash",
            "questions": [{"question_id": "q1"}],
            "total": 4,
        }
    )
    rs.save_result(
        {
            "run_id": "ckpt-answered",
            "status": "completed",
            "benchmark": "mmlu",
            "model_id": "m",
            "total": 4,
        }
    )
    _write_json(
        tmp_path / "ckpt-answered.checkpoint.json",
        {
            "run_id": "ckpt-answered",
            "status": "paused",
            "completed_question_ids": ["a", "b"],
            "remaining_question_ids": ["c"],
        },
    )

    mapped = rs._checkpoint_map()
    assert "only" in mapped
    assert "shape" not in mapped

    page = rs.list_results_page(lean=False, paginate=False)
    by_id = {row["run_id"]: row for row in page["data"]}
    assert page["next_cursor"] is None
    assert by_id["inflight"]["status"] == "running"
    assert by_id["inflight"]["resumable"] is False
    assert by_id["inflight"]["provider"] == "omlx"
    assert "questions" in by_id["inflight"]
    assert by_id["partial"]["provider"] == "deepseek"
    assert by_id["partial"]["status"] == "interrupted"
    assert by_id["partial"]["resumable"] is True
    assert "only" in by_id

    filtered = rs.list_results_page(suite="arc")
    assert {row["run_id"] for row in filtered["data"]} == {"partial"}
    assert "google" in filtered["providers"]

    lean = {row["run_id"]: row for row in rs.list_results(limit=20)}
    assert lean["ckpt-answered"]["answered"] == 2
    assert lean["ckpt-answered"]["status"] == "paused"


def test_resume_checkpoints_rebuild_and_give_up(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    assert rs.build_resume_checkpoint(" ") is None
    assert rs.build_resume_checkpoint("absent") is None
    assert rs.build_retry_failed_checkpoint("") is None
    assert rs.build_retry_failed_checkpoint("missing-run") is None

    bad_sample = rs.result_from_checkpoint({"run_id": "s", "sample_size": "nope"})
    assert bad_sample["total"] == 0
    good_sample = rs.result_from_checkpoint(
        {"run_id": "s", "sample_size": "6", "thinking": 1, "elapsed_s": 2, "status": "paused"}
    )
    assert good_sample["total"] == 6
    assert good_sample["thinking_used"] is True
    assert good_sample["time_s"] == 2.0

    _write_json(
        tmp_path / "paused-run.checkpoint.json",
        {
            "run_id": "paused-run",
            "status": "paused",
            "remaining_question_ids": ["q9"],
        },
    )
    paused = rs.build_resume_checkpoint("paused-run")
    assert paused["status"] == "paused"
    assert paused["remaining_question_ids"] == ["q9"]
    assert rs._effective_status({"run_id": "paused-run", "status": "running"}) == "paused"
    assert (
        rs._effective_status({"run_id": "", "status": "   "}, live={}, checkpoints={})
        == "completed"
    )

    rs.save_result(
        {
            "run_id": "rebuild",
            "project_id": "proj",
            "status": "completed",
            "benchmark": "mmlu",
            "total": 4,
            "questions": [
                {"question_id": "q1"},
                {
                    "question_id": "q-stall",
                    "eval_mode": "error",
                    "judge": {"error": "Cell stalled"},
                },
            ],
        }
    )
    _write_json(
        tmp_path / "rebuild.checkpoint.json",
        {
            "run_id": "rebuild",
            "status": "running",
            "project_id": "proj",
            "completed_question_ids": ["q1", "q-left"],
            "remaining_question_ids": ["q-old"],
        },
    )
    rebuilt = rs.build_resume_checkpoint(
        "rebuild",
        stores=[_NoLookup(), _BoomLeftover(), _LeftoverStore()],
    )
    assert rebuilt["status"] == "interrupted"
    assert rebuilt["remaining_question_ids"] == ["q-left"]
    assert rebuilt["completed_question_ids"] == ["q1"]

    rs.save_result(
        {
            "run_id": "partial-ex",
            "project_id": "proj",
            "status": "completed",
            "benchmark": "mmlu",
            "name": "Partial",
            "time_s": 3,
            "total": 8,
            "thinking_used": False,
            "questions": [
                {"question_id": "q1"},
                {"question_id": ""},
                "bad",
                {
                    "question_id": "q-stall",
                    "eval_mode": "error",
                    "judge": {"error": "timed out waiting"},
                },
            ],
            "environment": {
                "suite": {
                    "suite_id": "mmlu",
                    "sample_size": "",
                    "pack_id": "pack",
                    "matrix": {"n": 1},
                },
                "model": {
                    "model_id": "m",
                    "provider": "openai",
                    "specialist_id": "spec",
                    "thinking": True,
                },
            },
        }
    )
    exhausted = rs.build_resume_checkpoint(
        "partial-ex",
        stores=[_BoomStore(), _EmptyCounts(), _ExhaustedStore()],
    )
    assert exhausted["suite_id"] == "mmlu"
    assert exhausted["sample_size"] == 8
    assert exhausted["remaining_question_ids"] == []
    assert exhausted["thinking"] is True
    assert "q-extra" in exhausted["completed_question_ids"]
    assert "q1" in exhausted["completed_question_ids"]

    rs.save_result(
        {
            "run_id": "clean",
            "status": "completed",
            "benchmark": "mmlu",
            "total": 1,
            "questions": [{"question_id": "q1", "predicted": "A", "correct": True}],
        }
    )
    assert rs.build_retry_failed_checkpoint("clean") is None
    assert rs.build_retry_failed_checkpoint("clean", question_ids=["missing", " "]) is None
    assert rs.build_resume_checkpoint("clean", stores=[_NoLookup()]) is None


def test_attach_usage_and_resume_edges(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    attached = rs.attach_usage_and_resume(
        [
            {
                "run_id": "live",
                "project_id": "proj-live",
                "status": "running",
                "usage_session_ids": ["s1"],
                "lifetime_tokens": "nope",
                "total": 3,
                "answered": "1",
            },
            {
                "run_id": "nums",
                "status": "interrupted",
                "answered": "4",
                "total": 4,
            },
            {
                "run_id": "bad",
                "status": "completed",
                "answered": "nope",
                "total": {"bad": True},
            },
        ],
        stores=[None, _NoLookup(), _BoomStore(), _UsageStore()],
        run_tokens={"live": 3},
    )
    live, nums, bad = attached
    assert live["status"] == "running"
    assert live["resumable"] is True
    assert live["lifetime_tokens"] == 15
    assert "usage_session_ids" not in live
    assert nums["status"] == "completed"
    assert nums["resumable"] is False
    assert nums["lifetime_tokens"] == 0
    assert bad["lifetime_tokens"] == 0
    assert bad["answered"] == "nope"


def test_match_decode_slice_terminal_and_live_status(tmp_path, monkeypatch):
    assert (
        rs._matches(
            {"status": "running"},
            q=None,
            suite=None,
            status="__none__",
            provider=None,
        )
        is False
    )
    assert (
        rs._matches({"status": "running"}, q=None, suite=None, status=",", provider=None)
        is False
    )
    assert (
        rs._matches(
            {"status": "", "benchmark": "mmlu"},
            q=None,
            suite=None,
            status="completed",
            provider=None,
        )
        is True
    )
    assert (
        rs._matches(
            {"status": "running"},
            q=None,
            suite=None,
            status="completed,paused",
            provider=None,
        )
        is False
    )
    assert rs._decode_offset(base64.urlsafe_b64encode(b"\xff").decode().rstrip("=")) is None
    assert (
        rs._decode_offset(base64.urlsafe_b64encode(b"off:abc").decode().rstrip("=")) is None
    )
    assert rs._decode_offset(base64.urlsafe_b64encode(b"nope").decode().rstrip("=")) is None

    rows = [{"n": 1}, {"n": 2}, {"n": 3}]
    first = rs.slice_page(rows, limit=2)
    assert first["total"] == 3
    assert first["data"] == rows[:2]
    second = rs.slice_page(rows, limit=2, cursor=first["next_cursor"])
    assert second["data"] == [{"n": 3}]
    assert second["next_cursor"] is None
    assert rs.slice_page(rows, cursor="!!!")["total"] == 3

    ids = rs._terminal_question_ids(
        {
            "questions": [
                "nope",
                {"question_id": "  "},
                {
                    "question_id": "stall",
                    "eval_mode": "error",
                    "judge": {"error": "timed out waiting"},
                },
                {"question_id": "other", "eval_mode": "error", "judge": {"error": "format"}},
            ]
        }
    )
    assert ids == {"stall"}

    _isolate(monkeypatch, tmp_path)

    def _running():
        return {"r1": "running"}

    monkeypatch.setattr(rs, "_live_run_statuses", _running)
    same = {
        "run_id": "r1",
        "status": "running",
        "resumable": False,
        "questions": [{"question_id": "q"}],
        "total": 1,
    }
    assert rs.apply_live_status(same) is same

    def _idle():
        return {}

    monkeypatch.setattr(rs, "_live_run_statuses", _idle)
    changed = {
        "run_id": "r2",
        "status": "queued",
        "resumable": False,
        "questions": [{}, {}],
        "total": 2,
    }
    updated = rs.apply_live_status(changed)
    assert updated["status"] == "interrupted"
    assert updated["resumable"] is True
    assert updated is not changed
