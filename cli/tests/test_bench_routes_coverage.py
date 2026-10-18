"""Hit /v1/bench routes with the service functions stubbed."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_server.bench_service.dataset_install import BenchInstallError
from agent_server.models.bench import (
    BenchActiveStatus,
    BenchInstallResponse,
    BenchProgress,
    BenchUninstallResponse,
)
from agent_server.routes import bench as bench_routes


def _row(**extra):
    base = {
        "run_id": "run-1",
        "model_id": "openai/gpt-test",
        "benchmark": "gpqa",
        "accuracy": 0.5,
        "correct": 1,
        "answered": 2,
        "total": 2,
        "time_s": 1.5,
        "thinking_used": False,
        "project_id": None,
        "created_at": "2026-01-01T00:00:00Z",
        "status": "completed",
        "reasoning_effort": "low",
        "reasoning_fast": False,
        "name": "nightly",
        "provider": "openai",
        "lifetime_tokens": 12,
        "resumable": False,
        "failed_count": 0,
    }
    base.update(extra)
    return base


def _client(monkeypatch, store):
    monkeypatch.setattr(bench_routes, "bootstrap_resumable", lambda: None)
    app = FastAPI()
    deps = SimpleNamespace(store=store, worker_store=lambda: store)
    bench_routes.register_bench_routes(app, deps)
    return TestClient(app)


def test_bench_routes_happy_and_error_paths(tmp_path, monkeypatch):
    cards = []
    monkeypatch.setattr(bench_routes, "list_suite_cards", lambda store: cards)
    monkeypatch.setattr(bench_routes, "total_cache_bytes", lambda: 4)
    monkeypatch.setattr(bench_routes, "cache_root", lambda: tmp_path)

    def _install(suite_id):
        if suite_id == "missing":
            raise BenchInstallError("need token", needs_hf_token=True)
        return BenchInstallResponse(ok=True, suite_id=suite_id, summary="started")

    def _uninstall(suite_id):
        if suite_id == "missing":
            raise BenchInstallError("no cache", status_code=404)
        return BenchUninstallResponse(ok=True, suite_id=suite_id, summary="gone")

    monkeypatch.setattr(bench_routes, "start_install", _install)
    monkeypatch.setattr(bench_routes, "uninstall_suite", _uninstall)

    def _enqueue(deps, payload):
        if payload.project_name == "bad":
            raise ValueError("bad project")
        if payload.project_name == "boom":
            raise RuntimeError("queue down")
        return ["run-1"]

    monkeypatch.setattr(bench_routes, "enqueue", _enqueue)
    monkeypatch.setattr(
        "agent_server.settings_service.SettingsService.get",
        staticmethod(lambda: SimpleNamespace(model="settings-model")),
    )
    monkeypatch.setattr(
        bench_routes,
        "get_active_status",
        lambda: BenchActiveStatus(
            running=False,
            phase="idle",
            last_progress=BenchProgress(message="done"),
        ),
    )
    page = {
        "data": [_row(), _row(run_id="run-2", lifetime_tokens=None, answered="", reasoning_effort="")],
        "next_cursor": None,
        "total": 2,
        "providers": ["openai"],
    }
    monkeypatch.setattr(bench_routes, "list_results_page", lambda **kwargs: page)
    monkeypatch.setattr(
        bench_routes,
        "attach_usage_and_resume",
        lambda rows, **kwargs: [{**row, "lifetime_tokens": row.get("lifetime_tokens") or 9} for row in rows],
    )

    store = SimpleNamespace(lifetime_tokens_by_run=lambda ids: dict.fromkeys(ids, 9))
    client = _client(monkeypatch, store)

    packs = client.get("/v1/bench/packs")
    assert packs.status_code == 200
    assert packs.json()["cacheBytes"] == 4

    assert client.post("/v1/bench/packs/gpqa/install").status_code == 200
    denied = client.post("/v1/bench/packs/missing/install")
    assert denied.status_code == 400
    assert denied.json()["detail"]["needsHfToken"] is True
    assert client.delete("/v1/bench/packs/gpqa/install").status_code == 200
    assert client.delete("/v1/bench/packs/missing/install").status_code == 404

    dry = client.post(
        "/v1/bench/spawn",
        json={"suites": [{"suite_id": "gpqa"}], "dry_run": True},
    )
    assert dry.status_code == 200
    assert dry.json()["runIds"] == ["dry-run"]
    dry_models = client.post(
        "/v1/bench/spawn",
        json={"suites": [{"suite_id": "gpqa"}], "dry_run": True, "model": "a", "models": ["b"]},
    )
    assert dry_models.json()["queued"] == 2
    spawned = client.post("/v1/bench/spawn", json={"suites": [{"suite_id": "gpqa"}]})
    assert spawned.json()["runIds"] == ["run-1"]
    assert client.post(
        "/v1/bench/spawn",
        json={"suites": [{"suite_id": "gpqa"}], "project_name": "bad"},
    ).status_code == 400
    assert client.post(
        "/v1/bench/spawn",
        json={"suites": [{"suite_id": "gpqa"}], "project_name": "boom"},
    ).status_code == 500

    assert client.get("/v1/bench/runs/active").status_code == 200
    listed = client.get("/v1/bench/runs")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 2
    by_usage = client.get("/v1/bench/runs?sort=usage_desc")
    assert by_usage.status_code == 200
    assert client.get("/v1/bench/runs?sort=usage_asc").status_code == 200
    assert client.get("/v1/bench/runs?sort=date_asc").status_code == 200

    monkeypatch.setattr(bench_routes, "resolve_result_run_id", lambda run_id: run_id)
    monkeypatch.setattr(bench_routes, "get_result", lambda run_id: _row() if run_id == "run-1" else None)
    monkeypatch.setattr(bench_routes, "load_checkpoint", lambda run_id: {"run_id": run_id} if run_id == "ckpt" else None)
    monkeypatch.setattr(
        bench_routes,
        "result_from_checkpoint",
        lambda ckpt: _row(run_id=ckpt["run_id"], lifetime_tokens=None, provider=""),
    )
    monkeypatch.setattr(bench_routes, "apply_live_status", lambda row: row)
    detail = client.get("/v1/bench/runs/run-1")
    assert detail.status_code == 200
    assert "run-1" in detail.text
    missing = client.get("/v1/bench/runs/missing")
    assert missing.status_code == 404
    from_ckpt = client.get("/v1/bench/runs/ckpt")
    assert from_ckpt.status_code == 200

    monkeypatch.setattr(bench_routes, "rename_result", lambda run_id, name: {"name": name} if run_id == "run-1" else None)
    assert client.patch("/v1/bench/runs/run-1", json={}).status_code == 400
    assert client.patch("/v1/bench/runs/missing", json={"name": "x"}).status_code == 404
    renamed = client.patch("/v1/bench/runs/run-1", json={"name": "x"})
    assert renamed.status_code == 200

    export = tmp_path / "export.json"
    export.write_text("{}")
    monkeypatch.setattr(bench_routes, "export_path", lambda run_id: export if run_id == "run-1" else None)
    assert client.get("/v1/bench/runs/missing/export").status_code == 404
    downloaded = client.get("/v1/bench/runs/run-1/export")
    assert downloaded.status_code == 200
    assert "gpt-test_gpqa.json" in downloaded.headers["content-disposition"]

    monkeypatch.setattr(bench_routes, "cancel_run", lambda run_id: run_id)
    assert client.post("/v1/bench/runs/run-1/cancel").status_code == 200
    monkeypatch.setattr(bench_routes, "pause_run", lambda run_id: None if run_id == "idle" else run_id)
    assert client.post("/v1/bench/runs/idle/pause").status_code == 409
    assert client.post("/v1/bench/runs/run-1/pause").status_code == 200

    def _resume(deps, run_id, **kwargs):
        if run_id == "bad":
            raise ValueError("cannot resume")
        return run_id or "active-run"

    monkeypatch.setattr(bench_routes, "resume_run", _resume)
    assert client.post("/v1/bench/runs/run-1/resume").status_code == 200
    assert client.post("/v1/bench/runs/active/resume").json()["runId"] == "active-run"
    assert client.post("/v1/bench/runs/bad/resume").status_code == 400
    retried = client.post("/v1/bench/runs/run-1/retry-failed", json={"question_ids": ["q1"]})
    assert retried.status_code == 200
    assert client.post("/v1/bench/runs/bad/retry-failed").status_code == 400

    monkeypatch.setattr(bench_routes, "delete_result", lambda run_id, **kwargs: run_id == "run-1")
    assert client.delete("/v1/bench/runs/missing").status_code == 404
    assert client.delete("/v1/bench/runs/run-1").json()["ok"] is True
    monkeypatch.setattr(bench_routes, "remove_queued", lambda index: index == 0)
    assert client.delete("/v1/bench/queue/3").status_code == 404
    assert client.delete("/v1/bench/queue/0").json()["ok"] is True
    monkeypatch.setattr(bench_routes, "clear_results", lambda **kwargs: (2, 1))
    reset = client.post("/v1/bench/results/reset")
    assert reset.json()["cleared"] == 2

    monkeypatch.setattr(bench_routes, "get_result", lambda run_id: _row() if run_id == "run-1" else None)
    assert client.post("/v1/bench/grade", json={"run_id": "missing"}).status_code == 404
    graded = client.post("/v1/bench/grade", json={"run_id": "run-1"})
    assert graded.json()["ok"] is True
    assert client.post("/v1/bench/grade", json={}).json()["ok"] is False

    with client.stream("GET", "/v1/bench/runs/run-1/stream") as response:
        body = response.read().decode()
    assert "data:" in body
    assert "done" in body
    assert Path(export).is_file()
