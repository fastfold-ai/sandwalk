"""Unit tests for the known cloud context-window mapping."""

from __future__ import annotations

from agent.model_catalog import context_window_for_model


def test_anthropic_modern_models_have_1m():
    # 1M context is GA (default, no beta header) on modern Anthropic models.
    assert context_window_for_model("claude-opus-5") == 1_000_000
    assert context_window_for_model("claude-fable-5") == 1_000_000
    assert context_window_for_model("claude-opus-4-8") == 1_000_000
    assert context_window_for_model("claude-sonnet-5") == 1_000_000
    assert context_window_for_model("claude-sonnet-4-6") == 1_000_000


def test_anthropic_legacy_models_stay_200k():
    assert context_window_for_model("claude-sonnet-4-5-20250929") == 200_000
    assert context_window_for_model("claude-haiku-4-5-20251001") == 200_000


def test_openai_gpt5_family():
    # GPT-5.6 family (Sol/Terra/Luna) has a 1.05M window; older GPT-5.x 400k.
    assert context_window_for_model("gpt-5.6-sol") == 1_050_000
    assert context_window_for_model("gpt-5.6-terra") == 1_050_000
    assert context_window_for_model("gpt-5.5") == 400_000
    assert context_window_for_model("gpt-5.3-codex") == 400_000


def test_gemini_and_xai():
    assert context_window_for_model("gemini-3.1-pro-preview") == 1_048_576
    assert context_window_for_model("grok-4.3") == 1_000_000
    assert context_window_for_model("grok-4.5") == 256_000
    assert context_window_for_model("kimi-k3") == 1_000_000
    assert context_window_for_model("kimi-k2.6") == 256_000
    assert context_window_for_model("kimi-k2.7-code-highspeed") == 256_000


def test_unknown_model_returns_none():
    assert context_window_for_model("mystery-model") is None
    assert context_window_for_model("") is None
