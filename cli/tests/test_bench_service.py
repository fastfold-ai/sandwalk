"""Unit tests for agent_server.bench_service grade + catalog."""

from __future__ import annotations

from agent_server.bench_service.catalog import list_suite_cards
from agent_server.bench_service.mcq_suites import full_dataset_available
from agent_server.bench_service.grade import (
    build_result,
    extract_answer,
    grade_mc_letter,
    grade_range,
    grade_row,
    grade_str,
)


def test_extract_answer_patterns():
    assert extract_answer("thinking...\nAnswer: 42\n") == "42"
    assert extract_answer("FINAL_ANSWER: yes") == "yes"
    assert extract_answer(r"The result is \boxed{3.14}") == "3.14"
    assert extract_answer("the final answer is B") == "B"
    assert extract_answer("only trailing\nline") == "line"
    assert extract_answer("") == ""


def test_grade_str_and_mc():
    assert grade_str("Yes", "yes")
    assert grade_str("foo", "prefix foo suffix")
    assert not grade_str("yes", "no")
    assert grade_mc_letter("B", "I think B is correct")
    assert grade_mc_letter("D", "D")
    assert not grade_mc_letter("A", "C")


def test_grade_range():
    assert grade_range("(1.0, 2.0)", "1.5")
    assert grade_range("(1e-3, 1e-1)", "0.01")
    assert not grade_range("(1.0, 2.0)", "3.0")
    assert not grade_range("not-a-range", "1.0")


def test_grade_row_modes():
    assert grade_row(eval_mode="str_verifier", ideal="42", predicted="Answer: 42")
    assert grade_row(eval_mode="range_verifier", ideal="(0, 10)", predicted="5")
    assert grade_row(eval_mode="mcq", ideal="A", predicted="I think A is right")
    assert grade_row(eval_mode="llm_verifier", ideal="x", predicted="y", judge_ok=True)
    assert not grade_row(eval_mode="llm_verifier", ideal="x", predicted="y", judge_ok=False)
    assert grade_row(eval_mode="checklist", ideal=None, predicted="ok", judge_ok=True)


def test_build_result_shape():
    questions = [
        {
            "id": "1",
            "correct": True,
            "category": "anatomy",
            "expected": "A",
            "predicted": "A",
        },
        {
            "id": "2",
            "correct": False,
            "category": "anatomy",
            "expected": "B",
            "predicted": "C",
        },
        {
            "id": "3",
            "correct": True,
            "category": "biology",
            "expected": "yes",
            "predicted": "yes",
        },
    ]
    result = build_result(
        run_id="run-1",
        model_id="test-model",
        benchmark="mmlu",
        questions=questions,
        time_s=12.34,
        thinking_used=True,
        project_id="proj-1",
        environment={"sandwalk_version": "0.0.1", "python_version": "3.12.0"},
    )
    assert result["run_id"] == "run-1"
    assert result["model_id"] == "test-model"
    assert result["benchmark"] == "mmlu"
    assert result["correct"] == 2
    assert result["total"] == 3
    assert result["accuracy"] == 2 / 3
    assert result["time_s"] == 12.3
    assert result["thinking_used"] is True
    assert result["project_id"] == "proj-1"
    assert result["category_scores"]["anatomy"] == 0.5
    assert result["category_scores"]["biology"] == 1.0
    assert len(result["questions"]) == 3
    assert result["environment"]["sandwalk_version"] == "0.0.1"


def test_capture_bench_environment_shape():
    from agent_server.bench_service.environment import capture_bench_environment

    env = capture_bench_environment(
        None,
        model_id="openrouter/deepseek/deepseek-v4-flash-0731",
        provider="openrouter",
        thinking=True,
        suite_id="arc-challenge",
        sample_size=10,
        pack_id="arc-challenge",
    )
    assert env["model"]["model_id"] == "openrouter/deepseek/deepseek-v4-flash-0731"
    assert env["model"]["provider"] == "openrouter"
    assert env["model"]["thinking"] is True
    assert env["suite"]["suite_id"] == "arc-challenge"
    assert env["suite"]["sample_size"] == 10
    assert isinstance(env["sandwalk_version"], str) and env["sandwalk_version"]
    assert isinstance(env["python_version"], str) and env["python_version"]
    assert isinstance(env["packages"], dict)
    assert isinstance(env["skills"], list)
    assert env["mcp_servers"] == []
    assert "started_at" in env
    assert "captured_at" in env


def test_list_suite_cards_includes_mmlu_and_packs():
    cards = list_suite_cards()
    ids = {c.id for c in cards}
    assert "mmlu" in ids
    assert "mmlu-pro" in ids
    assert "arc-challenge" in ids
    assert "mbpp" in ids
    assert "livecodebench" in ids
    assert "bixbench-verified-50" in ids
    assert "bixbench-adapted-5" not in ids
    mmlu = next(c for c in cards if c.id == "mmlu")
    assert mmlu.runner == "agent"
    assert mmlu.available is True
    assert mmlu.question_count == 14042
    assert mmlu.default_sample_size == 30
    assert 30 in mmlu.sample_sizes
    # Offered sizes depend on what is cached locally: the full corpus unlocks the
    # large picks, while the bundled sample fixture must not advertise sizes it
    # cannot serve (picking one used to fail mid-run).
    if full_dataset_available("mmlu"):
        assert 2000 in mmlu.sample_sizes
        assert mmlu.sample_sizes[-1] == 14042  # Full
    else:
        assert max(mmlu.sample_sizes) <= 30
        assert mmlu.installable is True
    pro = next(c for c in cards if c.id == "mmlu-pro")
    assert pro.available is True
    assert pro.question_count == 12032
    assert pro.default_sample_size == 30
    if full_dataset_available("mmlu-pro"):
        assert pro.sample_sizes[-1] == 12032
    else:
        assert max(pro.sample_sizes) <= 30
    assert pro.author == "TIGER-Lab"
    arc = next(c for c in cards if c.id == "arc-challenge")
    assert arc.available is True
    assert arc.title == "ARC-C"
    assert arc.question_count == 1172
    assert arc.default_sample_size == 30
    if full_dataset_available("arc-challenge"):
        assert arc.sample_sizes == [30, 50, 100, 200, 300, 1172]
    else:
        assert max(arc.sample_sizes) <= 30
        assert 30 in arc.sample_sizes
    mbpp = next(c for c in cards if c.id == "mbpp")
    assert mbpp.code_exec is True
    assert mbpp.question_count == 500
    assert mbpp.default_sample_size == 30
    assert mbpp.sample_sizes[-1] == 500
    assert mbpp.installable is True
    lcb = next(c for c in cards if c.id == "livecodebench")
    assert lcb.code_exec is True
    assert lcb.question_count == 1055
    assert lcb.default_sample_size == 30
    assert lcb.sample_sizes[-1] == 1055
    assert lcb.installable is True
    # One card per YAML pack (not one per matrix) — UI owns model selection.
    pack_cards = [c for c in cards if c.pack_id and c.id != "bixbench-verified-50"]
    assert pack_cards, "expected at least one YAML pack suite card"
    pack_ids = [c.pack_id for c in pack_cards]
    assert len(pack_ids) == len(set(pack_ids))
    skills = next((c for c in pack_cards if c.pack_id == "bio-capybara-full"), None)
    if skills is not None:
        assert skills.id == "bio-capybara-full"
        assert skills.title == "Bio-Capybara-full"
        assert skills.author == "Sandwalk"
        assert skills.question_count == 12
        assert skills.matrix == "full-coverage-same-model"
        assert "fold" in skills.required_skills
        assert "pymol" in skills.required_mcps
        # Without a store, MCP readiness is empty → soft skip warning, still runnable.
        if skills.missing_skills or skills.missing_mcps:
            assert skills.available is True
            assert skills.unavailable_reason
            assert "skipped" in skills.unavailable_reason.lower()
    mmlu_card = next(c for c in cards if c.id == "mmlu")
    assert mmlu_card.author == "Hendrycks et al."
    bix = next(c for c in cards if c.id == "bixbench-verified-50")
    assert bix.author == "Phylo"
    assert bix.installable is True
    assert bix.requires_hf_token is True
    # Not-installed is conveyed by installed/available + Install button, not copy.
    if not bix.available:
        assert bix.installed is False
    # Bio-Capybara-full ships with the CLI (bundled packs).
    assert any(c.pack_id == "bio-capybara-full" for c in cards)


def test_grade_mc_supports_mmlu_pro_letters():
    assert grade_mc_letter("I", "Answer: I")
    assert grade_mc_letter("J", "the final answer is J")
    assert not grade_mc_letter("A", "I")


def test_code_exec_mbpp_grader():
    from agent_server.bench_service.code_exec import grade_code_exec

    src = {
        "suite": "mbpp",
        "test_list": ["assert add(1, 2) == 3", "assert add(0, 0) == 0"],
        "test_setup_code": "",
    }
    ok = grade_code_exec(
        suite_id="mbpp",
        source=src,
        predicted="```python\ndef add(a, b):\n    return a + b\n```",
    )
    assert ok
    bad = grade_code_exec(
        suite_id="mbpp",
        source=src,
        predicted="```python\ndef add(a, b):\n    return a - b\n```",
    )
    assert not bad


def test_mcq_sampling_is_seed_stable():
    import pytest

    from agent_server.bench_service.mcq_suites import (
        MCQ_SUITES,
        load_mcq_items,
        resolve_dataset_path,
    )

    if resolve_dataset_path(MCQ_SUITES["arc-challenge"], prefer_full=True) is None:
        pytest.skip("full ARC/MMLU datasets not cached under apps/benchmarking/.cache/mcq/")

    a = load_mcq_items("arc-challenge", 30)
    b = load_mcq_items("arc-challenge", 30)
    assert len(a) == 30
    assert [x["id"] for x in a] == [x["id"] for x in b]
    full = load_mcq_items("arc-challenge", 0)
    assert len(full) == 1172
    pro = load_mcq_items("mmlu-pro", 30)
    assert len(pro) == 30
    subjects = {x["subject"] for x in pro}
    assert len(subjects) >= 5
