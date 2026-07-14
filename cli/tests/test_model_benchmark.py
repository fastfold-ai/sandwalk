"""Unit tests for agent.model_benchmark (matrix expansion; no live LLM calls)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agent.model_benchmark import (
    BenchmarkQuestion,
    BenchmarkTarget,
    cases_to_preview,
    collect_cloud_targets,
    expand_cases,
    invoke_case,
    load_suite,
    run_benchmark,
)


def test_expand_cases_effort_only_for_reasoning_models():
    openai = BenchmarkTarget(
        provider="openai",
        model="gpt-5.6-sol",
        label="Sol",
        supports_reasoning_effort=True,
    )
    anthropic = BenchmarkTarget(
        provider="anthropic",
        model="claude-sonnet-5",
        label="Sonnet 5",
        supports_reasoning_effort=False,
    )
    questions = [
        BenchmarkQuestion(id="hi", prompt="hi"),
        BenchmarkQuestion(id="math", prompt="1+1", expect_contains=["2"]),
    ]
    cases = expand_cases(
        [openai, anthropic],
        questions,
        efforts=["low", "fast"],
    )
    # openai: 2 efforts × 2 questions; anthropic: 1 default × 2 questions
    assert len(cases) == 6
    openai_efforts = {
        c.effort for c in cases if c.target.provider == "openai"
    }
    assert openai_efforts == {"low", "fast"}
    anthropic_efforts = {
        c.effort for c in cases if c.target.provider == "anthropic"
    }
    assert anthropic_efforts == {None}


def test_load_suite_from_config():
    path = (
        Path(__file__).resolve().parents[1]
        / "configs"
        / "model_benchmarks.json"
    )
    name, questions = load_suite(path)
    assert name == "model-catalog-smoke"
    ids = {q.id for q in questions}
    assert {"hi", "math", "kras"} <= ids
    math = next(q for q in questions if q.id == "math")
    assert "323" in math.expect_contains


def test_collect_cloud_targets_filters_by_key_and_provider():
    targets = collect_cloud_targets(
        provider="openai",
        has_key=lambda provider: provider == "openai",
    )
    assert targets
    assert all(t.provider == "openai" for t in targets)
    assert any(t.model == "gpt-5.6-sol" for t in targets)
    assert any(t.supports_reasoning_effort for t in targets)

    empty = collect_cloud_targets(has_key=lambda _p: False)
    assert empty == []


def test_run_benchmark_with_fake_model():
    target = BenchmarkTarget(
        provider="openai",
        model="gpt-5.6-sol",
        label="Sol",
        supports_reasoning_effort=True,
    )
    question = BenchmarkQuestion(
        id="math",
        prompt="17*19",
        expect_contains=["323"],
    )
    cases = expand_cases([target], [question], efforts=["medium"])

    class FakeMsg:
        content = "323"
        usage_metadata = {"input_tokens": 10, "output_tokens": 2}

    class FakeChat:
        def bind_tools(self, _tools):
            return self

        def invoke(self, _messages):
            return FakeMsg()

    cfg_data = {
        "llm.provider": "openai",
        "llm.model": "gpt-5.6-sol",
        "llm.reasoning_effort": "medium",
        "llm.reasoning_fast": False,
        "llm.openai_active_profile": "openai_cloud",
    }

    def cfg_get(key, default=None):
        return cfg_data.get(key, default)

    def cfg_set(key, value):
        cfg_data[key] = value

    config = SimpleNamespace(
        get=cfg_get,
        set=cfg_set,
        set_openai_active_profile=lambda _pid: None,
    )

    run = run_benchmark(
        cases,
        suite_name="unit",
        with_tools=True,
        build_model=lambda _cfg, streaming=False: FakeChat(),
        config=config,
    )
    assert run.summary()["passed"] == 1
    assert run.summary()["failed"] == 0
    assert run.results[0].preview == "323"
    assert run.results[0].effort == "medium"
    assert run.to_dict()["results"][0]["latencyMs"] >= 0


def test_invoke_case_expectation_failure():
    target = BenchmarkTarget(
        provider="openai",
        model="gpt-5.6-sol",
        label="Sol",
        supports_reasoning_effort=False,
    )
    question = BenchmarkQuestion(
        id="math",
        prompt="17*19",
        expect_contains=["323"],
    )
    case = expand_cases([target], [question], efforts=["medium"])[0]

    class FakeMsg:
        content = "I refuse"
        usage_metadata = {}

    class FakeChat:
        def bind_tools(self, _tools):
            return self

        def invoke(self, _messages):
            return FakeMsg()

    cfg_data: dict = {
        "llm.provider": "openai",
        "llm.model": "gpt-5.6-sol",
        "llm.reasoning_effort": "medium",
        "llm.reasoning_fast": False,
    }
    config = SimpleNamespace(
        get=lambda key, default=None: cfg_data.get(key, default),
        set=lambda key, value: cfg_data.__setitem__(key, value),
        set_openai_active_profile=lambda _pid: None,
    )
    result = invoke_case(
        case,
        with_tools=False,
        build_model=lambda *_a, **_k: FakeChat(),
        config=config,
    )
    assert result.ok is False
    assert result.expect_ok is False


def test_cases_to_preview_shape():
    target = BenchmarkTarget(
        provider="google",
        model="gemini-3.5-flash",
        label="Flash",
        supports_reasoning_effort=False,
    )
    cases = expand_cases(
        [target],
        [BenchmarkQuestion(id="hi", prompt="hi")],
        efforts=["high"],
    )
    preview = cases_to_preview(cases)
    assert preview == [
        {
            "provider": "google",
            "model": "gemini-3.5-flash",
            "label": "Flash",
            "effort": None,
            "questionId": "hi",
            "supportsReasoningEffort": False,
        }
    ]
