"""HTTP result classification for the doctor model-key probe."""

from agent.doctor.model_provider_http import (
    ModelsProbeResult,
    _classify_http_result,
    _error_snippet,
    _is_output_limit_error,
    _probe_token_budget,
    _qwen_model_miss,
    _reply_from_anthropic,
    _reply_from_openai_chat,
    _success_message,
    supports_llm_key_probe,
)


def test_snippets_replies_and_budgets():
    assert _error_snippet("nope") == ""
    assert _error_snippet({"error": {"message": "bad key"}}) == "bad key"
    assert _error_snippet({"error": "plain"}) == "plain"
    assert _error_snippet({"detail": "missing"}) == "missing"
    assert _error_snippet({"message": "later"}) == "later"
    assert _reply_from_openai_chat(None) == ""
    assert _reply_from_openai_chat({"choices": [{"message": {"content": " hi "}}]}) == "hi"
    assert _reply_from_openai_chat({"choices": [{"text": "legacy"}]}) == "legacy"
    assert _reply_from_anthropic({"content": [{"type": "text", "text": "ok"}, {"type": "tool"}]}) == "ok"
    assert _reply_from_anthropic({"content": "no"}) == ""
    assert "replied" in _success_message("OpenAI", "hello")
    assert _success_message("OpenAI", "") == "OpenAI API key works."
    assert _probe_token_budget("gpt-5.6-sol") == 64
    assert _probe_token_budget("deepseek-reasoner") == 64
    assert _probe_token_budget("claude-sonnet") == 1
    assert _is_output_limit_error("output limit was reached")
    assert _is_output_limit_error("max_tokens reached")
    assert supports_llm_key_probe("openai")
    assert not supports_llm_key_probe("local")


def test_classify_http_result():
    ok = _classify_http_result(label="OpenAI", code=200, body_text="", payload=None, success_message="works")
    assert ok.ok and ok.message == "works"
    limited = _classify_http_result(
        label="OpenAI",
        code=400,
        body_text="max_tokens reached",
        payload={"error": "limit"},
        success_message="works",
    )
    assert limited.ok
    invalid = _classify_http_result(
        label="OpenAI",
        code=401,
        body_text="unauthorized",
        payload={"error": {"message": "nope"}},
        success_message="works",
    )
    assert not invalid.ok and "Invalid API key" in invalid.message
    other = _classify_http_result(
        label="OpenAI",
        code=500,
        body_text="boom",
        payload={"message": "down"},
        success_message="works",
    )
    assert "HTTP 500" in other.message
    bare = _classify_http_result(
        label="OpenAI",
        code=502,
        body_text="",
        payload=None,
        success_message="works",
    )
    assert bare.message == "OpenAI returned HTTP 502."


def test_qwen_model_miss():
    assert _qwen_model_miss(ModelsProbeResult(ok=False, message="model not found", status_code=404))
    assert not _qwen_model_miss(ModelsProbeResult(ok=True, message="ok", status_code=200))
