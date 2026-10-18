"""Bench queue cancel/pause, result retry rules, and FastFold one-click grant."""

from __future__ import annotations

import json
import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock

from agent_server.bench_service import queue_runner as queue
from agent_server.bench_service import results_store as results
from agent_server.integrations_service import fastfold_one_click as one_click


def test_incomplete_and_retryable_results(tmp_path, monkeypatch):
    assert results._answered_count({"questions": "nope"}) is None
    assert results._answered_count({"questions": [{}, {}]}) == 2
    assert results.is_incomplete_result({"status": "cancelled", "total": 3, "questions": [{}]}) is False
    assert results.is_incomplete_result({"status": "running", "total": 1, "questions": [{}]}) is True
    assert results.is_incomplete_result({"status": "completed", "total": "bad", "questions": []}) is False
    assert results.is_incomplete_result({"status": "completed", "total": 4, "questions": [{}, {}]}) is True
    assert results.is_retryable_failure({"skipped": True}) is True
    assert results.is_retryable_failure({"eval_mode": "error"}) is True
    assert results.is_retryable_failure({"judge": {"error": "boom"}}) is True
    assert results.is_retryable_failure({"predicted": "rate limit"}) is True
    assert results.is_retryable_failure({"predicted": "42", "correct": False}) is False
    ids = results.retryable_failure_ids(
        {"questions": [{"question_id": "a", "skipped": True}, "nope", {"question_id": "a", "skipped": True}, {"question_id": "b", "predicted": "ok"}]}
    )
    assert ids == ["a"]

    monkeypatch.setattr(results, "results_dir", lambda: tmp_path)
    (tmp_path / "bad.checkpoint.json").write_text("not-json")
    (tmp_path / "run-1.checkpoint.json").write_text(json.dumps({"run_id": "run-1", "status": "paused"}))
    (tmp_path / "list.json").write_text("[]")
    found = results._checkpoint_map()
    assert found["run-1"]["status"] == "paused"
    status = results._effective_status(
        {"run_id": "run-1", "status": "running", "total": 2, "questions": [{}]},
        live={"run-1": "paused"},
        checkpoints=found,
    )
    assert status == "paused"
    leftover = results._effective_status(
        {"run_id": "gone", "status": "queued", "total": 0, "questions": []},
        live={},
        checkpoints={},
    )
    assert leftover == "interrupted"


def test_queue_cancel_pause_and_shutdown(monkeypatch):
    queue.reset_state_for_tests()
    assert queue.cancel_run("missing") is None or queue.cancel_run() is None
    queue.reset_state_for_tests()
    job = queue.BenchJob(
        run_id="run-1",
        model_id="gpt",
        provider="openai",
        suites=[{"suite_id": "gpqa"}],
    )
    job.active_run_id = "suite-1"
    with queue._state.lock:
        queue._state.queue.append(job)
        queue._state.paused["paused-1"] = {"run_id": "paused-1"}
    monkeypatch.setattr(queue, "_mark_cancelled", lambda run_id: None)
    monkeypatch.setattr(queue, "_live_inflight_ids", lambda: set())
    assert queue.cancel_run("run-1") == "run-1"
    assert queue.cancel_run("paused-1") == "paused-1"
    live = queue.BenchJob(run_id="live-1", model_id="gpt", provider="openai", suites=[])
    with queue._state.lock:
        queue._state.inflight["live-1"] = live
    assert queue.pause_run("active") == "live-1"
    assert queue.pause_run("missing") is None
    threads = queue.request_bench_shutdown()
    assert threads == []
    assert queue.cancel_current() == "live-1"
    queue.reset_state_for_tests()


def test_fastfold_one_click(monkeypatch):
    label = one_click._device_label()
    assert "sandwalk" in label and "python-v" in label
    monkeypatch.setattr(one_click.platform, "node", lambda: "")
    monkeypatch.setattr(one_click.platform, "system", lambda: "Windows")
    monkeypatch.setattr(one_click.platform, "machine", lambda: "AMD64")
    assert "win32" in one_click._device_label()
    assert "(x64)" in one_click._device_label()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"query": "1.2.3.4", "city": "Austin", "country": "US"}'

    monkeypatch.setattr(one_click.urllib.request, "urlopen", lambda request, timeout=3: _Resp())
    meta = one_click._network_meta()
    assert meta["client_ip"] == "1.2.3.4"
    assert "Austin" in meta["location"]

    def _fail(request, timeout=3):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(one_click.urllib.request, "urlopen", _fail)
    assert one_click._network_meta() == {}

    class _Cloud:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'["nope"]'

    monkeypatch.setattr(one_click.urllib.request, "urlopen", lambda request, timeout=30: _Cloud())
    payload, err = one_click._cloud_json("POST", "https://cloud.example", body={"a": 1}, bearer="tok")
    assert payload == {} and err is None

    def _http(request, timeout=30):
        exc = urllib.error.HTTPError(request.full_url, 409, "wait", hdrs=None, fp=None)
        exc.read = lambda: b'{"message": "later"}'
        raise exc

    monkeypatch.setattr(one_click.urllib.request, "urlopen", _http)
    assert one_click._cloud_json("GET", "https://cloud.example")[1] == "not_ready"

    def _read_boom():
        raise RuntimeError("read")

    def _http400b(request, timeout=30):
        exc = urllib.error.HTTPError(request.full_url, 400, "bad", hdrs=None, fp=None)
        exc.read = _read_boom
        raise exc

    monkeypatch.setattr(one_click.urllib.request, "urlopen", _http400b)
    assert "HTTP 400" in one_click._cloud_json("GET", "https://cloud.example")[1]

    monkeypatch.setattr(one_click, "cloud_base_url", lambda: "http://127.0.0.1:8787")
    localized = one_click._localize_auth_url("https://cloud.fastfold.ai/allow")
    assert localized.startswith("http://localhost:3000")
    monkeypatch.setattr(one_click, "cloud_base_url", lambda: "https://cloud.fastfold.ai")
    assert one_click._localize_auth_url("https://cloud.fastfold.ai/allow").startswith("https://cloud")

    monkeypatch.setattr(one_click, "_network_meta", lambda: {})
    monkeypatch.setattr(one_click, "_cloud_json", lambda *a, **k: (None, "nope"))
    try:
        one_click.start_fastfold_one_click()
        raise AssertionError("expected error")
    except ValueError:
        pass
    monkeypatch.setattr(
        one_click,
        "_cloud_json",
        lambda *a, **k: ({"auth_url": "https://cloud.fastfold.ai/allow", "claim_token": "claim"}, None),
    )
    url = one_click.start_fastfold_one_click(return_to="https://app.example/back")
    assert "allow" in url
    integrations = MagicMock()
    integrations.update.return_value = {"id": "fastfold-cloud"}
    monkeypatch.setattr(one_click, "_cloud_json", lambda *a, **k: (None, "not_ready"))
    assert one_click.import_fastfold_one_click(integrations) == {"ready": False}
    monkeypatch.setattr(one_click, "_cloud_json", lambda *a, **k: ({"api_key": "sk", "team_id": "t"}, None))
    imported = one_click.import_fastfold_one_click(integrations)
    assert imported["ready"] is True
    one_click.clear_fastfold_one_click()
    try:
        one_click.import_fastfold_one_click(integrations)
        raise AssertionError("expected no claim")
    except ValueError:
        pass
