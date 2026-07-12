"""Tests for models/llm.py helpers, dataclasses, and client init paths."""

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from models.llm import (  # type: ignore[import-untyped]
    LLMClient,
    LLMResponse,
    MODEL_PRICING,
    UsageTracker,
    _openai_temperature_kwargs,
    _openai_token_limit_kwargs,
)


class TestOpenAIKwargs:
    @pytest.mark.parametrize(
        "model,expected_key",
        [
            ("gpt-5.5", "max_completion_tokens"),
            ("GPT-5-mini", "max_completion_tokens"),
            ("gpt-4o", "max_tokens"),
            ("", "max_tokens"),
        ],
    )
    def test_token_limit_kwargs(self, model, expected_key):
        result = _openai_token_limit_kwargs(model, 2048)
        assert expected_key in result
        assert list(result.values())[0] == 2048

    def test_temperature_suppressed_for_gpt5(self):
        assert _openai_temperature_kwargs("gpt-5.4", 0.7) == {}

    def test_temperature_passed_for_legacy_models(self):
        assert _openai_temperature_kwargs("gpt-4o-mini", 0.3) == {"temperature": 0.3}


class TestLLMResponse:
    def test_defaults(self):
        resp = LLMResponse(content="hello", model="gpt-4o")
        assert resp.content == "hello"
        assert resp.model == "gpt-4o"
        assert resp.usage is None
        assert resp.raw is None
        assert resp.content_blocks is None

    def test_with_usage_and_blocks(self):
        resp = LLMResponse(
            content="tool call",
            model="claude-sonnet-4-5-20250929",
            usage={"input": 10, "output": 5},
            raw={"id": "msg_1"},
            content_blocks=[{"type": "text"}],
        )
        assert resp.usage["input"] == 10
        assert resp.content_blocks[0]["type"] == "text"


class TestModelPricing:
    def test_all_entries_have_input_output(self):
        for model, pricing in MODEL_PRICING.items():
            assert "input" in pricing, model
            assert "output" in pricing, model
            assert pricing["input"] > 0
            assert pricing["output"] > 0

    def test_opus_more_expensive_than_haiku(self):
        opus = MODEL_PRICING["claude-opus-4-6"]
        haiku = MODEL_PRICING["claude-haiku-4-5-20251001"]
        assert opus["input"] > haiku["input"]
        assert opus["output"] > haiku["output"]


class TestUsageTrackerExtended:
    def test_summary_when_empty(self):
        assert UsageTracker().summary() == "No LLM calls made."

    def test_record_empty_usage_dict_skipped(self):
        tracker = UsageTracker()
        tracker.record("gpt-4o", {})
        assert tracker.total_tokens == 0
        assert len(tracker.calls) == 0

    def test_cost_for_gpt4o(self):
        tracker = UsageTracker()
        tracker.record("gpt-4o", {"input": 1_000_000, "output": 500_000})
        # $2.50/M in + $10/M out
        assert tracker.total_cost == pytest.approx(7.5)

    def test_multiple_models_in_summary(self):
        tracker = UsageTracker()
        tracker.record("gpt-4o", {"input": 100, "output": 50})
        tracker.record("claude-haiku-4-5-20251001", {"input": 200, "output": 80})
        summary = tracker.summary()
        assert "2 LLM calls" in summary
        assert "gpt-4o" in summary
        assert "claude-haiku" in summary


class TestLLMClientInit:
    def test_default_model_per_provider(self):
        anthropic = LLMClient(provider="anthropic")
        assert anthropic.model == LLMClient.DEFAULT_MODELS["anthropic"]

        openai = LLMClient(provider="openai")
        assert openai.model == "gpt-4o"

    def test_base_url_stripped(self):
        client = LLMClient(provider="openai", base_url="http://localhost:11434/v1/")
        assert client.base_url == "http://localhost:11434/v1"

    def test_unknown_provider_raises_on_chat(self):
        client = LLMClient(provider="bogus", model="x")
        with pytest.raises(ValueError, match="Unknown provider"):
            client.chat("sys", [{"role": "user", "content": "hi"}])

    @patch("models.llm.LLMClient._get_client")
    def test_chat_openai_records_usage(self, mock_get_client):
        client = LLMClient(provider="openai", model="gpt-4o", api_key="sk-test")
        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="answer"))]
        mock_response.usage.prompt_tokens = 120
        mock_response.usage.completion_tokens = 40
        mock_openai.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_openai

        resp = client.chat("system", [{"role": "user", "content": "question"}])

        assert resp.content == "answer"
        assert client.usage.total_input_tokens == 120
        assert client.usage.total_output_tokens == 40
        create_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert "max_tokens" in create_kwargs
        assert "temperature" in create_kwargs

    @patch("models.llm.LLMClient._get_client")
    def test_chat_anthropic_empty_content(self, mock_get_client):
        client = LLMClient(provider="anthropic", model="claude-sonnet-4-5-20250929")
        mock_anthropic = MagicMock()
        mock_response = MagicMock()
        mock_response.content = []
        mock_response.usage.input_tokens = 5
        mock_response.usage.output_tokens = 0
        mock_anthropic.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_anthropic

        resp = client.chat("sys", [{"role": "user", "content": "hi"}])
        assert resp.content == ""
        assert resp.content_blocks == []

    @patch("models.llm.LLMClient._get_client")
    def test_stream_non_streaming_provider_yields_full_response(self, mock_get_client):
        client = LLMClient(provider="local", model="local-model")
        mock_get_client.return_value = MagicMock()

        with patch.object(client, "chat", return_value=LLMResponse(content="full", model="local-model")):
            chunks = list(client.stream("sys", [{"role": "user", "content": "hi"}]))
        assert chunks == ["full"]

    def test_retry_raises_on_non_transient_error(self):
        client = LLMClient(provider="anthropic", model="claude-sonnet-4-5-20250929")

        def _fail():
            raise ValueError("invalid request payload")

        with pytest.raises(ValueError, match="invalid request"):
            client._retry(_fail, max_retries=2)

    def test_retry_succeeds_after_transient_error(self):
        client = LLMClient(provider="anthropic", model="claude-sonnet-4-5-20250929")
        calls = {"n": 0}

        def _flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("rate_limit exceeded")
            return "ok"

        with patch("models.llm.time.sleep"):
            assert client._retry(_flaky, max_retries=3) == "ok"
        assert calls["n"] == 2

    def test_get_client_uses_anthropic_foundry_when_env_present(self, monkeypatch):
        fake_anthropic = types.SimpleNamespace(
            AnthropicFoundry=MagicMock(return_value="foundry-client"),
            Anthropic=MagicMock(return_value="cloud-client"),
        )
        monkeypatch.setenv("ANTHROPIC_FOUNDRY_API_KEY", "foundry-key")
        with patch.dict(sys.modules, {"anthropic": fake_anthropic}):
            client = LLMClient(provider="anthropic", model="claude-sonnet-4-5-20250929")
            resolved = client._get_client()
        assert resolved == "foundry-client"
        fake_anthropic.AnthropicFoundry.assert_called_once()
        fake_anthropic.Anthropic.assert_not_called()

    def test_stream_openai_records_usage_from_usage_chunk(self):
        client = LLMClient(provider="openai", model="gpt-4o", api_key="sk-test")
        chunk1 = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))],
            usage=None,
        )
        chunk2 = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=None))],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=5),
        )
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.return_value = [chunk1, chunk2]
        client._client = mock_openai

        chunks = list(client.stream("system", [{"role": "user", "content": "hi"}], max_tokens=64))
        assert chunks == ["hello"]
        assert client.usage.total_input_tokens == 12
        assert client.usage.total_output_tokens == 5

    def test_stream_anthropic_records_usage_on_stream_finalize(self):
        client = LLMClient(provider="anthropic", model="claude-sonnet-4-5-20250929")

        class _FakeStream:
            def __init__(self):
                self.text_stream = ["A", "B"]

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def get_final_message(self):
                return SimpleNamespace(
                    usage=SimpleNamespace(input_tokens=7, output_tokens=4),
                )

        mock_anthropic = MagicMock()
        mock_anthropic.messages.stream.return_value = _FakeStream()
        client._client = mock_anthropic

        out = list(client.stream("sys", [{"role": "user", "content": "q"}]))
        assert out == ["A", "B"]
        assert client.usage.total_input_tokens == 7
        assert client.usage.total_output_tokens == 4

    def test_stream_anthropic_finalize_failure_is_tolerated(self):
        client = LLMClient(provider="anthropic", model="claude-sonnet-4-5-20250929")

        class _FakeStream:
            def __init__(self):
                self.text_stream = ["chunk"]

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def get_final_message(self):
                raise RuntimeError("final message unavailable")

        mock_anthropic = MagicMock()
        mock_anthropic.messages.stream.return_value = _FakeStream()
        client._client = mock_anthropic

        assert list(client.stream("sys", [{"role": "user", "content": "q"}])) == ["chunk"]
        assert client.usage.total_tokens == 0

