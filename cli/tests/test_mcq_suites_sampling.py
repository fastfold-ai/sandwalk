"""MCQ fixture lookup, prompts, and seeded sampling."""

from __future__ import annotations

import json

import pytest

from agent_server.bench_service import mcq_suites as mcq


def test_catalog_sizes_and_missing_suite(tmp_path, monkeypatch):
    suite = mcq.MCQ_SUITES["mmlu"]
    assert mcq.count_fixture("nope") == 0
    assert mcq.dataset_available("nope") is False
    assert mcq.full_dataset_available("nope") is False
    assert suite.default_sample_size in mcq.catalog_sample_sizes(suite)
    assert mcq.catalog_sample_sizes(suite, full_available=False)
    monkeypatch.setattr(mcq, "fixtures_dir", lambda: None)
    assert mcq.sample_fixture_size(suite) == 0
    monkeypatch.setattr(mcq, "fixtures_dir", lambda: tmp_path)
    monkeypatch.setattr(mcq, "bench_cache_root", lambda: tmp_path)
    monkeypatch.setattr(mcq, "bench_root", lambda: None)
    assert mcq.resolve_dataset_path(suite, prefer_full=True) is None
    sample = tmp_path / suite.sample_fixture
    sample.write_text('{"question":"Q","choices":["a","b"],"answer":"A"}\n', encoding="utf-8")
    assert mcq.resolve_dataset_path(suite, prefer_full=False) == sample
    assert mcq.sample_fixture_size(suite) == 1
    with pytest.raises(FileNotFoundError):
        mcq.ensure_dataset_path(suite, 30)
    full = tmp_path / ".cache" / "mcq" / suite.full_fixture
    full.parent.mkdir(parents=True)
    rows = [
        {"question": f"Q{i}", "choices": ["a", "b"], "answer": "A", "subject": "math" if i % 2 else "law"}
        for i in range(6)
    ]
    full.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert mcq.full_dataset_available("mmlu") is True
    loaded = mcq.load_mcq_items("mmlu", 4)
    assert len(loaded) == 4
    assert loaded[0]["answer"] == "A"
    pro = mcq.MCQ_SUITES["mmlu-pro"]
    pro_path = tmp_path / ".cache" / "mcq" / pro.full_fixture
    pro_path.write_text(
        "".join(
            json.dumps({"question": f"P{i}", "choices": ["a", "b"], "answer": 0, "subject": "bio"}) + "\n"
            for i in range(4)
        ),
        encoding="utf-8",
    )
    sampled = mcq.load_mcq_items("mmlu-pro", 2)
    assert len(sampled) == 2
    prompt = mcq.format_mcq_prompt(
        "arc-challenge",
        {"subject": "life_science", "question": "Why?", "choices": ["up", "down"], "labels": ["A", "B", "C", "D", "E"]},
    )
    assert "A–E" in prompt and "Why?" in prompt
