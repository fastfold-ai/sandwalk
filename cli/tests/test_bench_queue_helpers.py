"""Bench queue helpers: enqueue, cancel, and progress shaping."""

from __future__ import annotations

from types import SimpleNamespace

from agent_server.bench_service import queue_runner as q
from agent_server.models.bench import BenchSpawnRequest, BenchSuiteRef


def test_queue_helpers(monkeypatch):
    q.reset_state_for_tests()
    assert q._clamp_parallel(None) is None
    assert q._clamp_parallel(0) == 1
    assert q._clamp_parallel(99) == q.MAX_PARALLEL_RUNS
    assert q._sample_sizes([{"sample_size": "3"}, {"sample_size": ""}, {"sample_size": "no"}]) == [3, None, None]
    assert q._as_elapsed("1.5") == 1.5
    assert q._as_elapsed("no") == 0.0
    assert q._split_suite("mmlu")[0] == "mmlu"
    assert q._progress_model(None) is None
    assert q._progress_model({"phase": "running", "message": "go"}).phase == "running"
    assert q.remove_queued(0) is False

    monkeypatch.setattr(q.SettingsService, "get", staticmethod(lambda: SimpleNamespace(model="gemma", provider="openai", openai_profile_id=None)))
    monkeypatch.setattr(q, "resolve_bench_provider", lambda provider, profile_id=None: provider)
    monkeypatch.setattr(q, "_pump", lambda deps: None)
    ids = q.enqueue(
        SimpleNamespace(),
        BenchSpawnRequest(
            suites=[BenchSuiteRef(suite_id="mmlu", sample_size=1)],
            model="gemma",
            models=["other"],
            parallel_runs=2,
        ),
    )
    assert len(ids) == 2
    assert q.remove_queued(0) is True
    try:
        q.enqueue(SimpleNamespace(), BenchSpawnRequest(suites=[]))
        raise AssertionError("expected suites")
    except ValueError:
        pass
    job = q.BenchJob(
        run_id="run-1",
        model_id="gemma",
        provider="openai",
        suites=[{"suite_id": "mmlu", "sample_size": 1}, {"suite_id": "pack:grid"}],
    )
    monkeypatch.setattr(q, "run_agent_suite", lambda **kwargs: {"status": "completed"})
    assert q._run_job(SimpleNamespace(), job) == "completed"
    q._state.cancel_ids.add("run-1")
    assert q._run_job(SimpleNamespace(), job) == "cancelled"
    q._state.cancel_ids.clear()
    q._state.pause_ids.add("run-1")
    assert q._run_job(SimpleNamespace(), job) == "paused"
    q._emit({"type": "progress", "phase": "running"}, "run-1")
    assert q._state.phase == "running"
    q.reset_state_for_tests()
