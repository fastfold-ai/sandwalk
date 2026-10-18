"""Bench result status, filters, and file summaries."""

from __future__ import annotations

from agent_server.bench_service import results_store as rs


def test_incomplete_retryable_and_status():
    assert rs._answered_count({}) is None
    assert rs._answered_count({"questions": [{}, {}]}) == 2
    assert rs.is_incomplete_result({"status": "cancelled", "questions": [{}], "total": 3}) is False
    assert rs.is_incomplete_result({"status": "paused", "questions": [], "total": 0}) is True
    assert rs.is_incomplete_result({"status": "completed", "questions": [{}], "total": 3}) is True
    assert rs.is_incomplete_result({"status": "completed", "total": "nope"}) is False

    assert rs.is_retryable_failure({"skipped": True}) is True
    assert rs.is_retryable_failure({"eval_mode": "error"}) is True
    assert rs.is_retryable_failure({"judge": {"error": "boom"}}) is True
    assert rs.is_retryable_failure({"raw_response": "HTTP 429 rate limit"}) is True
    assert rs.is_retryable_failure({"predicted": "the answer is A"}) is False
    assert rs.retryable_failure_ids(
        {"questions": [{"question_id": "q1", "skipped": True}, {"question_id": "q1", "skipped": True}, "bad"]}
    ) == ["q1"]

    row = {"run_id": "r1", "status": "running", "questions": [{}], "total": 2}
    assert rs._effective_status(row, live={"r1": "running"}) == "running"
    assert rs._effective_status({"run_id": "r2", "status": "running", "questions": [{}, {}], "total": 2}, live={}, checkpoints={}) == "interrupted"
    assert rs._as_token("4") == 4
    assert rs._as_token("no") == 0
    assert rs.new_run_id()


def test_summarize_match_and_files(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "results_dir", lambda: tmp_path)
    saved = rs.save_result({"benchmark": "mmlu", "status": "completed", "name": "Nightly", "questions": [{"session_id": "s1", "skipped": True, "question_id": "q1"}], "total": 1, "reasoning_effort": "high", "reasoning_fast": False, "provider": "openai"})
    assert saved.is_file()
    assert rs._is_result_file(saved) is True
    summary = rs._summarize(
        json_row(saved),
        run_id=json_row(saved)["run_id"],
        live={},
        profiles={},
        checkpoints={},
    )
    assert summary["name"] == "Nightly"
    assert summary["failed_count"] == 1
    assert rs._matches(summary, q="night", suite="mmlu", status="completed,paused", provider="openai,llama") is True
    assert rs._matches(summary, q=None, suite="arc", status=None, provider=None) is False
    token = rs._encode_offset(3)
    assert rs._decode_offset(token) == 3
    assert rs._decode_offset("@@@") is None
    loaded = rs.get_result(json_row(saved)["run_id"])
    assert loaded is not None
    renamed = rs.rename_result(loaded["run_id"], "Morning")
    assert renamed["name"] == "Morning"
    assert rs.delete_result(loaded["run_id"], delete_sessions=False) is True
    assert rs.get_result(loaded["run_id"]) is None


def json_row(path):
    import json
    return json.loads(path.read_text(encoding="utf-8"))
