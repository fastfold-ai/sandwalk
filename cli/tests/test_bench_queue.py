"""Queue stacking, cancel-one-run, and parallel job pickup."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent_server.bench_service import queue_runner as qr
from agent_server.models.bench import BenchSpawnRequest, BenchSuiteRef


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
    yield
    with qr._state.lock:
        qr._state.cancel_ids.update(qr._state.inflight)
        qr._state.cancel_ids.update(job.run_id for job in qr._state.queue)
    for thread in list(qr._state.job_threads.values()):
        thread.join(timeout=3)
    qr.reset_state_for_tests()


def _req(**kwargs) -> BenchSpawnRequest:
    suites = kwargs.pop("suites", [BenchSuiteRef(suite_id="mbpp", sample_size=5)])
    model = kwargs.pop("model", "m1")
    return BenchSpawnRequest(suites=suites, model=model, **kwargs)


def _block_until_stop(started: threading.Event, release: threading.Event):
    def fake_run(_deps, job):
        started.set()
        while not release.is_set():
            reason = qr._stop_reason(job.run_id)
            if reason == "cancel":
                return "cancelled"
            if reason == "pause":
                return "paused"
            time.sleep(0.01)
        return "completed"

    return fake_run


def _join_jobs(timeout: float = 3) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        threads = list(qr._state.job_threads.values())
        if not threads:
            return
        for thread in threads:
            thread.join(timeout=0.05)


def test_enqueue_while_running_keeps_a_separate_stack(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    deps = MagicMock()
    first = qr.enqueue(deps, _req(model="m1"))
    assert started.wait(2)
    second = qr.enqueue(
        deps,
        _req(
            model="m2",
            suites=[BenchSuiteRef(suite_id="mmlu", sample_size=10)],
        ),
    )
    status = qr.get_active_status()
    assert status.running
    assert len(status.inflight) == 1
    assert status.inflight[0].run_id == first[0]
    assert len(status.queue) == 1
    assert status.queue[0].run_id == second[0]
    assert status.queue[0].model_id == "m2"
    assert status.queue[0].suites == ["mmlu"]
    assert status.queue[0].sample_sizes == [10]
    release.set()
    _join_jobs()


def test_cancel_inflight_does_not_wipe_queue(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    deps = MagicMock()
    first = qr.enqueue(deps, _req(model="m1"))[0]
    assert started.wait(2)
    second = qr.enqueue(deps, _req(model="m2"))[0]
    qr.cancel_run(first)
    deadline = time.time() + 2
    live = set()
    while time.time() < deadline:
        status = qr.get_active_status()
        live = {row.run_id for row in [*status.inflight, *status.queue]}
        if first not in live and second in live:
            break
        time.sleep(0.02)
    assert first not in live
    assert second in live
    release.set()
    _join_jobs()


def test_parallel_runs_start_two_stacks(queue_env, monkeypatch):
    ready = threading.Event()
    release = threading.Event()
    count = {"n": 0}
    lock = threading.Lock()

    def fake_run(_deps, job):
        with lock:
            count["n"] += 1
            if count["n"] >= 2:
                ready.set()
        while not release.is_set():
            reason = qr._stop_reason(job.run_id)
            if reason == "cancel":
                return "cancelled"
            if reason == "pause":
                return "paused"
            time.sleep(0.01)
        return "completed"

    qr._job_hook = fake_run
    deps = MagicMock()
    ids = qr.enqueue(deps, _req(model="m1", models=["m2"], parallel_runs=2))
    assert len(ids) == 2
    assert ready.wait(2)
    status = qr.get_active_status()
    assert {row.run_id for row in status.inflight} == set(ids)
    assert status.queue == []
    assert status.parallel_runs == 2
    release.set()
    _join_jobs()


def test_resume_allowed_while_another_run_is_active(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    deps = MagicMock()
    qr.enqueue(deps, _req(model="m1"))
    assert started.wait(2)
    ckpt = {
        "run_id": "paused-1",
        "model_id": "m2",
        "suite_id": "mbpp",
        "concurrency": 1,
    }
    with qr._state.lock:
        qr._state.paused["paused-1"] = ckpt
    rid = qr.resume_run(deps, "paused-1")
    assert rid == "paused-1"
    status = qr.get_active_status()
    inflight = {row.run_id for row in status.inflight}
    assert "paused-1" in inflight
    assert status.queue == []
    assert status.parallel_runs >= 2
    assert "paused-1" not in {row.run_id for row in status.paused}
    release.set()
    _join_jobs()


def test_resume_rebuilds_checkpoint_from_partial_result(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    monkeypatch.setattr(
        qr,
        "build_resume_checkpoint",
        lambda rid, **_kw: {
            "run_id": rid,
            "status": "interrupted",
            "suite_id": "mmlu",
            "model_id": "m1",
            "completed_question_ids": ["q1"],
        }
        if rid == "partial-1"
        else None,
    )
    rid = qr.resume_run(MagicMock(), "partial-1")
    assert rid == "partial-1"
    assert started.wait(2)
    live = {row.run_id for row in qr.get_active_status().inflight}
    assert "partial-1" in live
    release.set()
    _join_jobs()


def test_pause_inflight_stays_resumable_without_checkpoint(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    deps = MagicMock()
    rid = qr.enqueue(deps, _req(model="m1"))[0]
    assert started.wait(2)
    assert qr.pause_run(rid) == rid
    deadline = time.time() + 2
    paused_ids: set[str] = set()
    while time.time() < deadline:
        status = qr.get_active_status()
        paused_ids = {row.run_id for row in status.paused}
        if rid in paused_ids and not status.inflight:
            break
        time.sleep(0.02)
    assert rid in paused_ids
    assert qr.get_active_status().resumable_run_id == rid
    resumed = qr.resume_run(deps, rid)
    assert resumed == rid
    status = qr.get_active_status()
    live = {row.run_id for row in [*status.inflight, *status.queue]}
    assert rid in live
    assert rid not in {row.run_id for row in status.paused}
    release.set()
    _join_jobs()


def test_active_status_lists_disk_paused_when_memory_empty(queue_env, monkeypatch):
    monkeypatch.setattr(
        qr,
        "list_checkpoints",
        lambda: [
            {
                "run_id": "disk-paused",
                "status": "paused",
                "model_id": "m9",
                "suite_id": "arc-challenge",
            }
        ],
    )
    status = qr.get_active_status()
    assert status.phase == "paused"
    assert status.resumable_run_id == "disk-paused"
    assert [row.run_id for row in status.paused] == ["disk-paused"]
    assert status.paused[0].model_id == "m9"


def test_inflight_status_stamps_stable_started_at(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    qr.enqueue(MagicMock(), _req(model="m1"))
    assert started.wait(2)
    first = qr.get_active_status().inflight[0]
    assert first.started_at
    assert first.elapsed_s == 0
    time.sleep(1.1)
    second = qr.get_active_status().inflight[0]
    assert second.started_at == first.started_at
    release.set()
    _join_jobs()


def test_retry_while_inflight_queues_more_questions(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    monkeypatch.setattr(
        qr,
        "build_retry_failed_checkpoint",
        lambda rid, **kw: {
            "run_id": rid,
            "status": "interrupted",
            "suite_id": "mmlu",
            "model_id": "m1",
            "force_retry": True,
            "remaining_question_ids": list(kw.get("question_ids") or ["q1"]),
        },
    )
    assert qr.resume_run(MagicMock(), "live-1", retry_failed=True, question_ids=["q1"])
    assert started.wait(2)
    assert qr.resume_run(MagicMock(), "live-1", retry_failed=True, question_ids=["q2"]) == "live-1"
    from agent_server.bench_service.retry_extra import take_extra_retry

    assert take_extra_retry("live-1") == ["q2"]
    release.set()
    _join_jobs()


def test_retry_failed_enqueues(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    monkeypatch.setattr(
        qr,
        "build_retry_failed_checkpoint",
        lambda rid, **_kw: {
            "run_id": rid,
            "status": "interrupted",
            "suite_id": "bixbench-verified-50",
            "model_id": "m1",
            "force_retry": True,
            "remaining_question_ids": ["bix-24-q2"],
            "completed_question_ids": ["q1"],
        },
    )
    rid = qr.resume_run(MagicMock(), "retry-1", retry_failed=True)
    assert rid == "retry-1"
    assert started.wait(2)
    live = {row.run_id for row in qr.get_active_status().inflight}
    assert "retry-1" in live
    release.set()
    _join_jobs()


def test_resume_finished_run_retries_failed(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    monkeypatch.setattr(
        qr,
        "build_retry_failed_checkpoint",
        lambda rid, **_kw: {
            "run_id": rid,
            "status": "interrupted",
            "suite_id": "mmlu",
            "model_id": "m1",
            "force_retry": True,
            "remaining_question_ids": ["q-fail"],
        },
    )
    monkeypatch.setattr(
        qr, "get_result", lambda rid: {"run_id": rid, "status": "completed"}
    )
    assert qr.resume_run(MagicMock(), "done-1") == "done-1"
    assert started.wait(2)
    release.set()
    _join_jobs()


def test_resume_finished_run_is_noop(queue_env, monkeypatch):
    monkeypatch.setattr(
        qr, "get_result", lambda rid: {"run_id": rid, "status": "completed"}
    )
    monkeypatch.setattr(qr, "build_retry_failed_checkpoint", lambda _rid, **_kw: None)
    assert qr.resume_run(MagicMock(), "done-1") == "done-1"
    assert qr.get_active_status().inflight == []


def test_resume_inflight_uses_checkpoint_elapsed(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    monkeypatch.setattr(
        qr,
        "find_resumable_checkpoint",
        lambda: {
            "run_id": "resume-1",
            "status": "paused",
            "model_id": "m1",
            "suite_id": "mmlu",
            "elapsed_s": 95.4,
        },
    )
    qr.resume_run(MagicMock(), "resume-1")
    assert started.wait(2)
    item = qr.get_active_status().inflight[0]
    assert item.run_id == "resume-1"
    assert item.started_at
    assert item.elapsed_s == 95.4
    release.set()
    _join_jobs()


def test_multi_suite_inflight_exposes_active_suite_id(queue_env, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    deps = MagicMock()
    stack_id = qr.enqueue(
        deps,
        _req(
            model="m1",
            suites=[
                BenchSuiteRef(suite_id="mmlu", sample_size=10),
                BenchSuiteRef(suite_id="mmlu-pro", sample_size=10),
            ],
        ),
    )[0]
    assert started.wait(2)
    suite_id = "suite-mmlu-pro"
    with qr._state.lock:
        job = qr._state.inflight[stack_id]
        job.active_run_id = suite_id
    status = qr.get_active_status()
    assert status.current_run_id == suite_id
    assert {row.run_id for row in status.inflight} == {suite_id}
    assert qr.live_run_statuses() == {suite_id: "running"}
    assert qr.pause_run(suite_id) == stack_id
    release.set()
    _join_jobs()


def test_resolve_result_run_id_maps_stack_to_suite_file(queue_env, monkeypatch, tmp_path):
    started = threading.Event()
    release = threading.Event()
    qr._job_hook = _block_until_stop(started, release)
    monkeypatch.setattr(qr, "get_result", lambda rid: {"run_id": rid} if rid == "suite-file" else None)
    stack_id = qr.enqueue(MagicMock(), _req(model="m1"))[0]
    assert started.wait(2)
    with qr._state.lock:
        qr._state.inflight[stack_id].active_run_id = "suite-file"
    assert qr.resolve_result_run_id(stack_id) == "suite-file"
    assert qr.resolve_result_run_id("suite-file") == "suite-file"
    release.set()
    _join_jobs()


def test_paused_status_exposes_frozen_elapsed(queue_env, monkeypatch):
    monkeypatch.setattr(
        qr,
        "list_checkpoints",
        lambda: [
            {
                "run_id": "paused-elapsed",
                "status": "paused",
                "model_id": "m1",
                "suite_id": "mmlu",
                "elapsed_s": 42,
            }
        ],
    )
    status = qr.get_active_status()
    assert status.paused[0].elapsed_s == 42
    assert status.paused[0].started_at is None
