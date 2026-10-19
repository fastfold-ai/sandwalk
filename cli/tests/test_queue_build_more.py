"""Remaining queue-runner and deepagents-build branches, without a live model."""

from __future__ import annotations

import asyncio
import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent.runner import deepagents_build as build_mod
from agent.runner.deepagents_build import DeepAgentsBuildMixin
from agent_server.bench_service import queue_runner as qr
from agent_server.file_access import FILE_ACCESS_ENV


class _Config:
    def __init__(self, values=None, hidden=None):
        self.values = dict(values or {})
        self.hidden = list(hidden or [])

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def hidden_tools(self):
        return list(self.hidden)


class _Host(DeepAgentsBuildMixin):
    def __init__(self):
        self.trajectory = SimpleNamespace(
            session_id="sess",
            turns=[],
            context_for_planner=lambda: "HISTORY",
        )
        self.session = SimpleNamespace(config=_Config())
        self.trace_store = None
        self._headless = True

    def _print_usage(self, *args, **kwargs):
        self.printed = True


class _Tool:
    def __init__(self, name):
        self.name = name


class _Registry:
    def list_tools(self):
        return [_Tool("keep.tool"), _Tool("drop.tool"), _Tool("  ")]


def _job(run_id="run-1", **kwargs):
    payload = {
        "model_id": "m",
        "provider": "openai",
        "suites": [{"suite_id": "mmlu", "sample_size": 1}],
    }
    payload.update(kwargs)
    return qr.BenchJob(run_id=run_id, **payload)


def _settle(timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        threads = list(qr._state.job_threads.values())
        if not threads:
            return
        for thread in threads:
            thread.join(timeout=0.05)
    leftover = [thread.name for thread in qr._state.job_threads.values() if thread.is_alive()]
    raise AssertionError(f"bench threads still running: {leftover}")


@pytest.fixture
def queue_env(monkeypatch):
    qr.reset_state_for_tests()
    monkeypatch.setattr(
        qr.SettingsService,
        "get",
        staticmethod(lambda: SimpleNamespace(model="default", provider="openai")),
    )
    monkeypatch.setattr(qr, "load_checkpoint", lambda _rid: None)
    monkeypatch.setattr(qr, "save_checkpoint", lambda payload: payload)
    monkeypatch.setattr(qr, "delete_checkpoint", lambda _rid: True)
    monkeypatch.setattr(qr, "list_checkpoints", lambda: [])
    monkeypatch.setattr(qr, "get_result", lambda _rid: None)
    monkeypatch.setattr(qr, "save_result", lambda _row: None)
    monkeypatch.setattr(qr, "build_resume_checkpoint", lambda _rid, **_kw: None)
    monkeypatch.setattr(qr, "build_retry_failed_checkpoint", lambda _rid, **_kw: None)
    monkeypatch.setattr(qr, "find_resumable_checkpoint", lambda: None)

    def _finish(_deps, _job):
        return "completed"

    qr._job_hook = _finish
    yield
    with qr._state.lock:
        qr._state.cancel_ids.update(qr._state.inflight)
        qr._state.cancel_ids.update(job.run_id for job in qr._state.queue)
    _settle()
    qr.reset_state_for_tests()


def test_reset_state_swallows_cleanup_errors(queue_env, monkeypatch):
    def _extra():
        raise RuntimeError("extra")

    class _BadStop:
        def clear(self):
            raise RuntimeError("stop")

    monkeypatch.setattr("agent_server.bench_service.retry_extra.clear_extra_retry", _extra)
    monkeypatch.setattr("agent_server.bench_service.runtime._stopping", _BadStop())
    qr._state.phase = "running"
    qr.reset_state_for_tests()
    assert qr._state.phase == "idle"
    assert qr._job_hook is None


def test_bootstrap_resumable_edges(queue_env, monkeypatch):
    rows = {"v": [{"run_id": "early", "status": "paused", "model_id": "m", "suite_id": "mmlu"}]}
    saved = []

    def _save(ckpt):
        saved.append(dict(ckpt))
        if ckpt.get("run_id") == "bad":
            raise OSError("disk")

    monkeypatch.setattr(qr, "list_checkpoints", lambda: rows["v"])
    monkeypatch.setattr(qr, "save_checkpoint", _save)
    qr._state.inflight["live"] = _job("live")
    qr.bootstrap_resumable()
    assert qr._state.paused == {}
    assert saved == []

    qr._state.inflight.clear()
    rows["v"] = [{"run_id": "done", "status": "completed"}]
    qr.bootstrap_resumable()
    assert qr._state.phase == "idle"
    assert qr._state.paused == {}

    rows["v"] = [
        {"run_id": "bad", "status": "running", "model_id": "m1", "suite_id": "mmlu"},
        {
            "run_id": "ok",
            "status": "paused",
            "model_id": "m2",
            "suite_id": "mbpp",
            "completed_question_ids": ["a"],
            "remaining_question_ids": ["b"],
        },
        {"status": "paused", "model_id": "skip"},
        {"run_id": "finished", "status": "completed"},
    ]
    qr.bootstrap_resumable()
    assert set(qr._state.paused) == {"bad", "ok"}
    assert qr._state.paused["bad"]["status"] == "interrupted"
    assert qr._state.phase == "paused"
    progress = qr._state.last_progress
    assert progress["phase"] == "paused"
    assert progress["message"] == "Paused — resume to continue"
    assert saved and saved[0]["status"] == "interrupted"


def test_disk_paused_skips_finished_rows(queue_env, monkeypatch):
    monkeypatch.setattr(
        qr,
        "list_checkpoints",
        lambda: [
            {"run_id": "done", "status": "completed"},
            {"run_id": "gone", "status": "cancelled"},
            {"status": "paused"},
            {"run_id": "skip", "status": "paused", "model_id": "m"},
            {"run_id": "keep", "status": "interrupted", "model_id": "m2", "suite_id": "mbpp"},
        ],
    )
    found = qr._disk_paused(exclude={"skip"})
    assert list(found) == ["keep"]


def test_active_status_loading_project_and_bad_sample(queue_env, monkeypatch):
    qr._state.queue.append(_job("queued", suites=[{"suite_id": "mmlu", "sample_size": "no"}]))
    loading = qr.get_active_status()
    assert loading.phase == "loading"
    assert loading.running is False
    assert loading.queue[0].run_id == "queued"
    assert loading.queue[0].sample_sizes == [None]

    qr._state.queue.clear()
    qr._state.inflight["r"] = _job("r")
    qr._state.phase = "scoring"
    qr._state.progress_by_run["r"] = {
        "type": "progress",
        "phase": "scoring",
        "project_id": "proj-live",
        "message": "go",
    }
    live = qr.get_active_status()
    assert live.phase == "scoring"
    assert live.project_id == "proj-live"
    assert live.current_run_id == "r"
    assert live.current_model == "m"

    qr._state.inflight.clear()
    qr._state.progress_by_run.clear()
    monkeypatch.setattr(
        qr,
        "list_checkpoints",
        lambda: [
            {
                "run_id": "disk",
                "status": "paused",
                "model_id": "md",
                "benchmark": "arc-challenge",
                "project_id": "proj-disk",
                "sample_size": {"bad": True},
                "provider": "",
            }
        ],
    )
    paused = qr.get_active_status()
    assert paused.phase == "paused"
    assert paused.project_id == "proj-disk"
    assert paused.resumable_run_id == "disk"
    assert paused.paused[0].sample_sizes == [None]
    assert paused.paused[0].suites == ["arc-challenge"]
    assert paused.paused[0].provider is None

    monkeypatch.setattr(qr, "list_checkpoints", lambda: [])
    qr._state.inflight["r2"] = _job("r2")
    qr._state.progress_by_run["r2"] = {"type": "progress", "phase": "running", "message": "x"}
    monkeypatch.setattr(
        qr,
        "load_checkpoint",
        lambda rid: {"run_id": rid, "project_id": "from-ckpt"} if rid == "r2" else None,
    )
    from_disk = qr.get_active_status()
    assert from_disk.project_id == "from-ckpt"
    assert from_disk.running is True


def test_cancel_pause_and_suite_mark(queue_env, monkeypatch):
    marked = []
    monkeypatch.setattr(qr, "_mark_cancelled", lambda rid: marked.append(rid))
    qr._state.paused["mem"] = {
        "run_id": "mem",
        "status": "paused",
        "suite_id": "mmlu",
        "model_id": "m",
    }
    assert qr.cancel_current() == "mem"
    assert marked == ["mem"]
    assert "mem" not in qr._state.paused

    qr._state.queue.append(_job("q1"))
    assert qr.cancel_run(None) == "q1"
    assert qr._state.queue == []

    monkeypatch.setattr(
        qr,
        "find_resumable_checkpoint",
        lambda: {"run_id": "disk-9", "status": "paused"},
    )
    assert qr.cancel_run("active") == "disk-9"
    assert marked[-1] == "disk-9"

    qr._state.inflight["stack"] = _job("stack", active_run_id="suite")
    qr._state.paused["suite"] = {"run_id": "suite", "status": "paused", "suite_id": "mmlu"}
    marked.clear()
    assert qr.cancel_run("suite") == "stack"
    assert marked == ["stack", "suite"]
    assert qr.pause_current() == "stack"
    assert "stack" in qr._state.pause_ids

    qr._state.inflight.clear()
    assert qr.pause_run(None) is None
    assert qr.pause_current() is None


def test_live_statuses_and_result_resolution(queue_env, monkeypatch):
    qr._state.inflight["stack"] = _job("stack", active_run_id="suite-x")
    qr._state.queue.append(_job("queued"))
    qr._state.paused["held"] = {"run_id": "held", "status": "paused"}
    qr._state.paused["suite-x"] = {"run_id": "suite-x", "status": "paused"}
    assert qr.live_run_statuses() == {
        "suite-x": "running",
        "queued": "queued",
        "held": "paused",
    }

    def _result(rid):
        if rid == "file":
            return {"run_id": rid}
        return None

    monkeypatch.setattr(qr, "get_result", _result)
    assert qr.resolve_result_run_id("suite-x") == "suite-x"
    monkeypatch.setattr(
        qr,
        "load_checkpoint",
        lambda rid: {"run_id": "file"} if rid == "missing" else None,
    )
    assert qr.resolve_result_run_id("missing") == "file"
    assert qr.resolve_result_run_id("unknown") == "unknown"


def test_mark_cancelled_survives_store_errors(queue_env, monkeypatch):
    flags = {"delete": True, "save": True}
    saved = []
    row = {"run_id": "r", "status": "completed"}

    def _delete(_rid):
        if flags["delete"]:
            raise OSError("delete")

    def _save(payload):
        if flags["save"]:
            raise OSError("save")
        saved.append(dict(payload))

    monkeypatch.setattr(qr, "delete_checkpoint", _delete)
    monkeypatch.setattr(qr, "get_result", lambda rid: row if rid == "r" else None)
    monkeypatch.setattr(qr, "save_result", _save)
    qr._mark_cancelled("r")
    assert row["status"] == "cancelled"
    assert saved == []
    flags["delete"] = False
    flags["save"] = False
    qr._mark_cancelled("r")
    assert saved[-1]["status"] == "cancelled"
    qr._mark_cancelled("missing")


def test_ensure_paused_updates_existing_and_logs_save_failure(queue_env, monkeypatch):
    job = _job(
        "p",
        suites=[{"suite_id": "mmlu", "sample_size": 2, "pack_id": "mbpp", "matrix": "grid"}],
        project_name="proj",
        specialist_id="spec",
        thinking=True,
        client_surface="cli",
        concurrency=2,
        cleanup_sessions=True,
    )
    saved = {}
    monkeypatch.setattr(
        qr,
        "load_checkpoint",
        lambda _rid: {"run_id": "p", "status": "running", "suite_id": "old"},
    )
    monkeypatch.setattr(qr, "save_checkpoint", lambda ckpt: saved.update(ckpt))
    monkeypatch.setattr(qr, "get_result", lambda _rid: {"run_id": "p"})
    updated = qr._ensure_paused_checkpoint(job)
    assert updated["status"] == "paused"
    assert saved["suite_id"] == "old"
    assert saved["status"] == "paused"

    def _fail(_ckpt):
        raise OSError("disk")

    monkeypatch.setattr(qr, "load_checkpoint", lambda _rid: None)
    monkeypatch.setattr(qr, "save_checkpoint", _fail)
    monkeypatch.setattr(qr, "get_result", lambda _rid: None)
    job.suites = []
    created = qr._ensure_paused_checkpoint(job)
    assert created["status"] == "paused"
    assert created["suite_id"] == ""
    assert created["run_id"] == "p"


def test_emit_inflight_phases_and_trim(queue_env):
    qr._state.inflight["a"] = _job("a")
    qr._state.inflight["b"] = _job("b")
    qr._emit({"type": "progress", "phase": "paused"}, "a")
    assert qr._state.phase == "running"
    qr._emit({"type": "progress", "phase": "scoring"}, "a")
    assert qr._state.phase == "scoring"
    qr._state.inflight.pop("b")
    qr._emit({"type": "progress", "phase": "idle"}, "a")
    assert qr._state.phase == "running"
    qr._state.inflight.clear()
    qr._state.events = [{"n": index} for index in range(500)]
    qr._emit({"type": "progress", "phase": "done"})
    assert len(qr._state.events) == 250
    assert qr._state.phase == "done"


def test_stop_reason_shutdown_and_import_error(queue_env, monkeypatch):
    monkeypatch.setattr(
        "agent_server.bench_service.runtime.is_bench_stopping",
        lambda: True,
    )
    assert qr._stop_reason("x") == "pause"

    def _boom():
        raise RuntimeError("runtime")

    monkeypatch.setattr("agent_server.bench_service.runtime.is_bench_stopping", _boom)
    qr._state.cancel_ids.add("x")
    assert qr._stop_reason("x") == "cancel"


def test_execute_and_run_job_edges(queue_env, monkeypatch):
    qr._job_hook = None
    calls = []

    def _suite(**kwargs):
        calls.append(kwargs)
        kwargs["on_progress"]({"type": "progress", "phase": "running", "message": "cell"})
        if len(calls) == 1:
            return {"status": "completed"}
        return {"status": "paused"}

    monkeypatch.setattr(qr, "run_agent_suite", _suite)
    job = _job(
        "stack",
        suites=[
            {"suite_id": "pack:grid", "sample_size": 4},
            {"suite_id": "mbpp", "sample_size": 0, "pack_id": "mbpp", "matrix": None},
        ],
        resume_checkpoint={"run_id": "pinned-suite", "suite_id": "pack:grid"},
    )
    assert qr._execute_job(SimpleNamespace(), job) == "paused"
    assert calls[0]["run_id"] == "pinned-suite"
    assert calls[0]["pack_id"] == "pack"
    assert calls[0]["matrix"] == "grid"
    assert calls[0]["sample_size"] == 4
    assert calls[1]["run_id"] != "stack"
    assert calls[1]["sample_size"] is None
    assert calls[1]["pack_id"] == "mbpp"
    assert qr._split_suite("pack:grid") == ("pack", "grid")
    assert qr._split_suite("custom-suite") == ("custom-suite", None)

    monkeypatch.setattr(qr, "run_agent_suite", lambda **_kwargs: {"status": "cancelled"})
    assert qr._execute_job(SimpleNamespace(), _job("cancel-me")) == "cancelled"

    def _hook(_deps, _run):
        return "hooked"

    qr._job_hook = _hook
    assert qr._execute_job(SimpleNamespace(), _job("hooked")) == "hooked"


def test_job_thread_records_hook_error(queue_env):
    def _boom(_deps, _run):
        raise RuntimeError("boom")

    qr._job_hook = _boom
    job = _job("err", suites=[])
    qr._state.inflight[job.run_id] = job
    qr._job_thread(SimpleNamespace(), job)
    assert "err" not in qr._state.inflight
    assert qr._state.events[-1]["phase"] == "error"
    assert "boom" in qr._state.events[-1]["message"]
    assert qr._state.phase == "idle"
    _settle()


def test_resume_run_rejects_and_short_circuits(queue_env):
    deps = MagicMock()
    with pytest.raises(ValueError, match="Pick a run to retry failed questions"):
        qr.resume_run(deps, None, retry_failed=True)
    with pytest.raises(ValueError, match="Pick a run to retry failed questions"):
        qr.resume_run(deps, "active", retry_failed=True)
    with pytest.raises(ValueError, match="That question is not on this run"):
        qr.resume_run(deps, "r", retry_failed=True, question_ids=["q"])
    with pytest.raises(ValueError, match="No failed questions to retry"):
        qr.resume_run(deps, "r", retry_failed=True)
    with pytest.raises(ValueError, match="That bench run has nothing left to resume"):
        qr.resume_run(deps, "ghost")
    with pytest.raises(ValueError, match="No resumable bench checkpoint found"):
        qr.resume_run(deps)

    qr._state.inflight["busy"] = _job("busy")
    qr._state.paused["busy"] = {
        "run_id": "busy",
        "suite_id": "mmlu",
        "model_id": "m",
        "status": "paused",
    }
    with pytest.raises(ValueError, match="That bench run is already in progress"):
        qr.resume_run(deps, "busy")

    qr._state.inflight.clear()
    qr._state.queue.append(_job("queued-already"))
    qr._state.paused["queued-already"] = {
        "run_id": "queued-already",
        "suite_id": "mbpp",
        "model_id": "m",
        "status": "paused",
    }
    assert qr.resume_run(deps, "queued-already") == "queued-already"
    assert [job.run_id for job in qr._state.queue] == ["queued-already"]
    assert "queued-already" in qr._state.paused


def test_resume_run_sources(queue_env, monkeypatch):
    seen = {}

    def _build(rid, stores=None, **_kw):
        seen["stores"] = list(stores or [])
        seen["rid"] = rid
        return {
            "run_id": rid,
            "suite_id": "mmlu",
            "model_id": "m",
            "status": "paused",
            "concurrency": 1,
        }

    monkeypatch.setattr(qr, "build_resume_checkpoint", _build)
    deps = MagicMock()
    deps.worker_store.side_effect = RuntimeError("no worker")
    marker = object()
    deps.store = marker
    assert qr.resume_run(deps, "from-result") == "from-result"
    assert seen["stores"] == [marker]
    _settle()

    monkeypatch.setattr(qr, "build_resume_checkpoint", lambda _rid, **_kw: None)
    monkeypatch.setattr(
        qr,
        "load_checkpoint",
        lambda rid: {
            "run_id": rid,
            "status": "paused",
            "suite_id": "mbpp",
            "model_id": "m",
        },
    )
    assert qr.resume_run(MagicMock(), "from-disk") == "from-disk"
    _settle()

    monkeypatch.setattr(
        qr,
        "load_checkpoint",
        lambda rid: {"run_id": rid, "status": "completed"},
    )
    monkeypatch.setattr(
        qr,
        "find_resumable_checkpoint",
        lambda: {
            "run_id": "from-find",
            "status": "interrupted",
            "suite_id": "mmlu",
            "model_id": "m",
        },
    )
    assert qr.resume_run(MagicMock(), "from-find") == "from-find"
    _settle()

    monkeypatch.setattr(qr, "load_checkpoint", lambda _rid: None)
    monkeypatch.setattr(qr, "find_resumable_checkpoint", lambda: None)
    qr._state.paused["mem"] = {
        "run_id": "mem",
        "suite_id": "arc-challenge",
        "model_id": "m",
        "status": "paused",
    }
    assert qr.resume_run(MagicMock(), "active") == "mem"
    _settle()

    monkeypatch.setattr(
        qr,
        "find_resumable_checkpoint",
        lambda: {
            "run_id": "found",
            "status": "paused",
            "suite_id": "mmlu",
            "model_id": "m",
        },
    )
    assert qr.resume_run(MagicMock()) == "found"
    _settle()

    monkeypatch.setattr(qr, "find_resumable_checkpoint", lambda: {"status": "paused"})
    with pytest.raises(ValueError, match="Checkpoint missing run_id"):
        qr.resume_run(MagicMock())


async def _inline(fn, *args, **kwargs):
    return fn(*args, **kwargs)


def test_build_deepagents_tools(monkeypatch):
    monkeypatch.setattr(build_mod, "run_cpu_bound", _inline)
    monkeypatch.setattr("tools.ensure_loaded", lambda: None)
    monkeypatch.setattr("tools.registry", _Registry())
    box = {"mcp": "fill", "sand": "ok"}

    def _create_ct(_session, **kwargs):
        box.setdefault("ct_calls", []).append(kwargs)
        box["ct"] = kwargs
        if not kwargs["include_run_python"]:
            return (
                [_Tool("capy.one"), _Tool("capy_raw"), _Tool("other")],
                "sandbox",
                ["trace"],
                {"capy.one": "capy.one", "capy_raw": "plain", "other": "other"},
            )
        return (
            [_Tool("keep.tool"), _Tool("dup"), _Tool("run_python")],
            "sandbox",
            ["trace"],
            {"keep.tool": "Keep", "dup": "Dup", "run_python": "py"},
        )

    async def _external(_servers, out_tools_by_server=None):
        if box["mcp"] == "raise":
            raise RuntimeError("mcp down")
        if box["mcp"] == "empty":
            return []
        out_tools_by_server["srv"] = ["ext"]
        return [_Tool("ext"), _Tool("dup"), _Tool("drop-me")]

    def _sandbox(session_id):
        box.setdefault("sessions", []).append(session_id)
        if box["sand"] == "raise":
            raise RuntimeError("sandbox down")
        return [_Tool("sandbox_status"), _Tool(""), _Tool("sandbox_status"), _Tool("drop-me")]

    def _finalize(tools, provider):
        box["provider"] = provider
        return [tool for tool in tools if tool.name != "drop-me"]

    monkeypatch.setattr(
        "agent.sandbox_control_tools.create_sandbox_control_tools",
        _sandbox,
    )
    host = _Host()
    host.session.config = _Config(
        {"agent.enable_experimental_tools": False, "agent.tool_mode": "  Script "},
        hidden=["secret"],
    )

    async def _run():
        native_ctx = {"session_id": "sid", "allowed_tool_names": ["keep.tool", "  "]}
        native = await host._build_deepagents_tools(
            host.session.config,
            native_ctx,
            "openai",
            _create_ct,
            _external,
            _finalize,
        )
        box["mcp"] = "empty"
        host.session.config.values["agent.enable_experimental_tools"] = True
        empty_ctx = {"allowed_tool_names": None}
        empty_extra = await host._build_deepagents_tools(
            host.session.config,
            empty_ctx,
            "openai",
            _create_ct,
            _external,
            _finalize,
        )
        box["native_ctx"] = native_ctx
        box["empty_ctx"] = empty_ctx
        box["mcp"] = "raise"
        box["sand"] = "raise"
        host.trajectory.session_id = ""
        broken = await host._build_deepagents_tools(
            host.session.config,
            {},
            "anthropic",
            _create_ct,
            _external,
            _finalize,
        )
        host.trajectory.session_id = "sid"
        await host._build_deepagents_tools(
            host.session.config,
            {"session_id": "sid"},
            "anthropic",
            _create_ct,
            _external,
            _finalize,
        )
        host.session.config.values["agent.tool_mode"] = "native"
        capy = await host._build_deepagents_tools(
            host.session.config,
            {"capy_mode": True, "session_id": "sid"},
            "openai",
            _create_ct,
            _external,
            _finalize,
        )
        return native, empty_extra, broken, capy

    native, empty_extra, broken, capy = asyncio.run(_run())
    tools, sandbox, traces, names, tool_mode, exclude_cats, excluded = native
    assert [tool.name for tool in tools] == ["keep.tool", "dup", "run_python", "ext", "sandbox_status"]
    assert sandbox == "sandbox"
    assert traces == ["trace"]
    assert names["sandbox_status"] == "sandbox_status"
    assert "drop-me" not in names
    assert tool_mode == "script"
    assert "compute" in exclude_cats
    assert {"secret", "drop.tool"} <= excluded
    assert box["ct_calls"][0]["tool_mode"] == "script"
    assert box["ct_calls"][0]["session_id"] == "sid"
    assert box["ct_calls"][0]["include_run_python"] is True
    assert box["ct_calls"][-1]["tool_mode"] == "native"
    assert box["ct_calls"][-1]["include_run_python"] is False
    assert box["provider"] == "openai"
    assert box["sessions"][0] == "sid"
    assert box["ct_calls"][2]["session_id"] is None
    assert empty_extra[5] == set()
    assert box["native_ctx"]["mcp_tools_by_server"] == {"srv": ["ext"]}
    assert "mcp_tools_by_server" not in box["empty_ctx"]
    assert [tool.name for tool in broken[0]] == ["keep.tool", "dup", "run_python"]
    assert broken[1] == "sandbox"
    capy_tools, capy_sandbox, capy_trace, capy_names, capy_mode, _cats, _ex = capy
    assert [tool.name for tool in capy_tools] == ["capy.one", "capy_raw"]
    assert capy_names == {"capy.one": "capy.one", "capy_raw": "capy_raw"}
    assert capy_sandbox is None
    assert capy_trace == []
    assert capy_mode == "native"


def test_build_deepagents_system_prompt():
    host = _Host()
    host.trajectory.turns = [object()]
    seen = []

    def _build(_session, **kwargs):
        seen.append(kwargs)
        return "SYS"

    cfg = _Config()
    tools = [SimpleNamespace(name="read"), SimpleNamespace(name="")]
    text = host._build_deepagents_system_prompt(
        cfg,
        {
            "data_dir": "/data",
            "sandbox_backend": "Modal",
            "project_context": "pc",
            "specialist_instructions": "be brief",
            "workspace_path": "/ws",
        },
        tools,
        "native",
        {"compute"},
        {"secret"},
        _build,
    )
    assert text == "SYS"
    assert cfg.values["sandbox.extra_read_dirs"] == "/data"
    assert seen[-1]["data_context"] == "Data directory: /data\n"
    assert seen[-1]["history"] == "HISTORY"
    assert seen[-1]["sandbox_backend"] == "modal"
    assert seen[-1]["tool_names"] == ["read", ""]
    assert seen[-1]["include_skills"] is False
    assert seen[-1]["runtime"] == "deepagents"
    assert seen[-1]["project_context"] == "pc"
    assert seen[-1]["exclude_tools"] == {"secret"}

    capy = host._build_deepagents_system_prompt(
        cfg,
        {"capy_mode": True, "specialist_instructions": "Do the thing"},
        [SimpleNamespace(name="capy.one"), SimpleNamespace(name="")],
        "native",
        set(),
        set(),
        _build,
    )
    assert capy.startswith("Do the thing")
    assert "capy.one" in capy
    assert "function calls" in capy

    bare = host._build_deepagents_system_prompt(
        cfg,
        {"capy_mode": True, "specialist_instructions": "  "},
        [SimpleNamespace(name="")],
        "native",
        set(),
        set(),
        _build,
    )
    assert bare == ""

    host.trajectory = None
    host._build_deepagents_system_prompt(
        cfg,
        {"sandbox_backend": "docker"},
        [],
        "script",
        set(),
        set(),
        _build,
    )
    assert seen[-1]["history"] is None
    assert seen[-1]["sandbox_backend"] is None
    assert seen[-1]["data_context"] is None

    host._build_deepagents_system_prompt(
        cfg,
        {"sandbox_backend": "builtin"},
        [],
        "script",
        set(),
        set(),
        _build,
    )
    assert seen[-1]["sandbox_backend"] == "builtin"


def test_build_deepagents_agent(monkeypatch, caplog):
    monkeypatch.setattr(build_mod, "run_cpu_bound", _inline)
    monkeypatch.setattr(asyncio, "to_thread", _inline)
    skill_args = []
    backend_calls = []
    config_calls = {"n": 0}
    wait_box = {"ok": False, "calls": 0}
    modal = SimpleNamespace(kind="modal", seeded=False, backend="modal-be", skills_sources=["/skills"])
    builtin = SimpleNamespace(kind="builtin", seeded=True, backend="local-be", skills_sources=[])
    seeded = SimpleNamespace(kind="modal", seeded=True, backend="modal-be", skills_sources=["/skills"])
    handles = [modal, modal, builtin, seeded]

    def _skills(names):
        skill_args.append(names)
        if names is None:
            return ["/skills"]
        return []

    def _resolve(_config, **kwargs):
        backend_calls.append(kwargs)
        return handles.pop(0)

    def _from_config(_config):
        config_calls["n"] += 1
        return "builtin"

    def _wait(_handle, timeout=0.0):
        wait_box["calls"] += 1
        assert timeout == 120.0
        return wait_box["ok"]

    def _create(**kwargs):
        return {"kwargs": kwargs}

    monkeypatch.setattr("agent.sandbox_backend.resolve_deepagents_backend", _resolve)
    monkeypatch.setattr("agent.sandbox_backend.sandbox_backend_from_config", _from_config)
    monkeypatch.setattr("agent.sandbox_backend.wait_until_seeded", _wait)
    monkeypatch.setattr(
        "agent.deepagents_runtime.subagents.build_domain_subagents",
        lambda: [{"name": "bio"}],
    )
    monkeypatch.setattr("agent.hitl.build_interrupt_on", lambda: {"gate": True})
    monkeypatch.setattr(
        "agent.hitl.get_session_checkpointer",
        lambda session_id: f"ckpt:{session_id}",
    )

    host = _Host()
    model = SimpleNamespace(profile={"modalities": ["text"]})

    async def _run():
        capy_agent, capy_handle = await host._build_deepagents_agent(
            _Config(
                {
                    "llm.provider": "openai",
                    "llm.model": "gpt",
                    "agent.knowledge_level": "high",
                }
            ),
            {
                "capy_mode": True,
                "workspace_path": "/ws",
                "session_id": "sid",
                "sandbox_backend": "modal",
                "allowed_skill_names": ["skill-a"],
            },
            model,
            [_Tool("capy.one")],
            "prompt",
            _create,
            _skills,
        )
        wait_box["ok"] = True
        await host._build_deepagents_agent(
            _Config({"llm.provider": "openai", "llm.model": "gpt"}),
            {
                "capy_mode": True,
                "workspace_path": "/ws",
                "session_id": "sid",
                "sandbox_backend": "modal",
                "allowed_skill_names": [],
            },
            model,
            [],
            "prompt",
            _create,
            _skills,
        )
        host.trajectory.session_id = ""
        medium_agent, _medium_handle = await host._build_deepagents_agent(
            _Config(
                {
                    "llm.provider": "deepseek",
                    "llm.model": "chat",
                    "agent.knowledge_level": "medium",
                }
            ),
            {"sandbox_backend": "weird"},
            model,
            [],
            "prompt",
            _create,
            _skills,
        )
        host.trajectory.session_id = "traj"
        high_agent, high_handle = await host._build_deepagents_agent(
            _Config(
                {
                    "llm.provider": "anthropic",
                    "llm.model": "sonnet",
                    "agent.knowledge_level": "high",
                }
            ),
            {"sandbox_backend": "builtin", "allowed_skill_names": None},
            model,
            [_Tool("read")],
            "prompt",
            _create,
            _skills,
        )
        return capy_agent, capy_handle, medium_agent, high_agent, high_handle

    with caplog.at_level("WARNING", logger="runner"):
        capy_agent, capy_handle, medium_agent, high_agent, high_handle = asyncio.run(_run())
    assert capy_handle is modal
    assert high_handle.kind == "modal"
    assert skill_args == [["skill-a"], [], None, None]
    assert capy_agent["kwargs"]["skills"] is None
    assert "subagents" not in capy_agent["kwargs"]
    assert capy_agent["kwargs"]["checkpointer"] == "ckpt:sid"
    assert capy_agent["kwargs"]["interrupt_on"] == {"gate": True}
    assert capy_agent["kwargs"]["backend"] == "modal-be"
    assert len(capy_agent["kwargs"]["middleware"]) == 2
    assert backend_calls[0]["background_sync"] is True
    assert backend_calls[0]["workspace_root"] == "/ws"
    assert backend_calls[0]["session_id"] == "sid"
    assert wait_box["calls"] == 2
    assert config_calls["n"] == 1
    assert backend_calls[2]["background_sync"] is False
    assert backend_calls[2]["backend_override"] is None
    assert "Proceeding with Modal" in caplog.text
    assert medium_agent["kwargs"]["skills"] is None
    assert "subagents" not in medium_agent["kwargs"]
    assert medium_agent["kwargs"]["checkpointer"] == "ckpt:None"
    assert len(medium_agent["kwargs"]["middleware"]) == 2
    assert "write_todos" in medium_agent["kwargs"]["middleware"][1]._excluded
    assert high_agent["kwargs"]["skills"] == ["/skills"]
    assert high_agent["kwargs"]["subagents"] == [{"name": "bio"}]
    assert high_agent["kwargs"]["checkpointer"] == "ckpt:traj"
    assert len(high_agent["kwargs"]["middleware"]) == 1
    assert high_agent["kwargs"]["backend"] == "modal-be"
    assert handles == []


def test_user_prompt_workspace_and_mention_edges(tmp_path, monkeypatch):
    from agent_server.file_access import normalize_file_access

    host = _Host()
    host.trajectory.session_id = "sess-9"
    host.session.config = _Config({"agent.plan_preview": False, "agent.file_access": "workspace"})
    workspace = tmp_path / "from-store"
    mode = {
        "resolve": "ok",
        "skill": "ok",
        "mcp": "text",
        "sync": "raise",
        "plans": "raise",
        "norm": "raise",
    }

    def _resolve(session_id, store=None, persist=True):
        assert session_id == "sess-9"
        assert store == "store-obj"
        assert persist is True
        if mode["resolve"] == "raise":
            raise RuntimeError("ws")
        return str(workspace)

    def _skill(*_args, **_kwargs):
        if mode["skill"] == "raise":
            raise RuntimeError("skill")
        return "skill ctx"

    def _mcp(*_args, **_kwargs):
        if mode["mcp"] == "raise":
            raise RuntimeError("mcp")
        return "mcp ctx"

    def _sync(_config):
        if mode["sync"] == "raise":
            raise RuntimeError("sync")

    def _plans(_path):
        if mode["plans"] == "raise":
            raise RuntimeError("plans")
        return ["plan.md"]

    def _norm(value, default="project"):
        if mode["norm"] == "raise":
            raise RuntimeError("norm")
        return normalize_file_access(value, default=default)

    monkeypatch.setattr("agent_server.store.AgentStore", lambda: "store-obj")
    monkeypatch.setattr("agent_server.service.resolve_session_workspace", _resolve)
    monkeypatch.setattr("agent.skills.mentions.build_skill_mention_context", _skill)
    monkeypatch.setattr("agent.mcp_manage.mentions.build_mcp_mention_context", _mcp)
    monkeypatch.setattr("agent.config.sync_process_env_from_config", _sync)
    monkeypatch.setattr("agent.system_prompt.mode_section.list_recent_plan_files", _plans)
    monkeypatch.setattr("agent_server.file_access.normalize_file_access", _norm)

    prev_access = os.environ.get(FILE_ACCESS_ENV)
    prev_ws = os.environ.get("SANDWALK_SESSION_WORKSPACE")
    try:
        prompt, updated = host._build_deepagents_user_prompt(
            "design",
            {
                "compound_smiles": "CCO",
                "target": "EGFR",
                "indication": "cancer",
                "mention_context": "from chat",
                "allowed_skill_names": [],
                "mcp_servers": [],
            },
        )
        assert updated["workspace_path"] == str(workspace)
        assert (workspace / "plans").is_dir()
        assert "EGFR" in prompt
        assert "skill ctx" in prompt
        assert "mcp ctx" in prompt
        assert "Pending plan" not in prompt

        mode["resolve"] = "raise"
        mode["skill"] = "raise"
        mode["mcp"] = "raise"
        mode["norm"] = "ok"
        missed, missed_ctx = host._build_deepagents_user_prompt("again", {})
        assert "workspace_path" not in missed_ctx
        assert missed == "again"
    finally:
        if prev_access is None:
            os.environ.pop(FILE_ACCESS_ENV, None)
        else:
            os.environ[FILE_ACCESS_ENV] = prev_access
        if prev_ws is None:
            os.environ.pop("SANDWALK_SESSION_WORKSPACE", None)
        else:
            os.environ["SANDWALK_SESSION_WORKSPACE"] = prev_ws


def test_exec_result_swallows_artifact_helper_errors(monkeypatch):
    monkeypatch.setattr(
        "agent.runner.deepagents_build._looks_like_unverified_execution_claim",
        lambda _summary, _calls: False,
    )

    def _paths(_calls):
        raise RuntimeError("paths")

    monkeypatch.setattr("agent.local_artifact_paths.collect_paths_from_tool_calls", _paths)
    host = _Host()
    done = host._build_deepagents_exec_result(
        "fetch",
        {
            "full_text": ["saved"],
            "tool_calls": [{"name": "write", "input": {}}],
            "token_usage": {},
            "model_call_count": 1,
        },
        0.0,
        "gpt",
        None,
        [],
        {},
    )
    assert done.summary == "saved"
    assert done.metadata["guardrail_unverified_execution"] is False
