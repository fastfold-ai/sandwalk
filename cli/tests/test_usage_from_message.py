"""Unit tests for LangChain message usage extraction."""

from __future__ import annotations

from types import SimpleNamespace

from agent.deepagents_runtime.event_text import _usage_from_message


def test_reads_langchain_usage_metadata():
    message = SimpleNamespace(
        usage_metadata={
            "input_tokens": 12,
            "output_tokens": 4,
            "input_token_details": {"cache_read": 3},
        },
        response_metadata={},
        content="hi",
    )
    assert _usage_from_message(message) == {
        "input_tokens": 12,
        "output_tokens": 4,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 3,
    }


def test_reads_openai_compatible_token_usage_and_omlx_timings():
    message = SimpleNamespace(
        usage_metadata=None,
        response_metadata={
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "generation_tokens_per_second": 161.2,
                "prompt_eval_duration": 0.039,
                "generation_duration": 1.1,
            }
        },
        content="hello",
    )
    usage = _usage_from_message(message)
    assert usage is not None
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 20
    assert usage["tokens_per_second"] == 161.2
    assert usage["prompt_eval_seconds"] == 0.039
    assert usage["generation_seconds"] == 1.1


def test_estimates_output_when_provider_omits_usage():
    message = SimpleNamespace(
        usage_metadata=None,
        response_metadata={},
        content="abcd",  # 4 chars → 1 token estimate
    )
    usage = _usage_from_message(message)
    assert usage == {
        "input_tokens": 0,
        "output_tokens": 1,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "estimated": True,
    }
