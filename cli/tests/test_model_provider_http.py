"""Unit tests for live LLM API-key probes (1-token chat/messages)."""

from __future__ import annotations

from types import SimpleNamespace

from agent.doctor.model_provider_http import (
    probe_chat_completions,
    probe_llm_api_key,
    probe_models_endpoint,
    supports_llm_key_probe,
)


def test_supports_llm_key_probe_known_providers():
    assert supports_llm_key_probe("anthropic")
    assert supports_llm_key_probe("openai")
    assert supports_llm_key_probe("nvidia")
    assert supports_llm_key_probe("google")
    assert supports_llm_key_probe("opencode")
    assert not supports_llm_key_probe("slack")


def test_probe_chat_completions_invalid_key(monkeypatch):
    class _Resp:
        status_code = 403
        text = '{"status":403,"detail":"Authorization failed"}'

        def json(self):
            return {"status": 403, "detail": "Authorization failed"}

    monkeypatch.setitem(
        __import__("sys").modules,
        "httpx",
        SimpleNamespace(post=lambda *_a, **_k: _Resp()),
    )
    result = probe_chat_completions(
        "https://opencode.ai/zen/v1/chat/completions",
        {"Authorization": "Bearer bad"},
        label="OpenCode Zen",
        model="gpt-5-nano",
    )
    assert result.ok is False
    assert result.message.startswith("Invalid API key.")


def test_probe_llm_api_key_opencode_uses_chat(monkeypatch):
    seen: dict = {}

    def _fake(url, headers, *, label, model, timeout=30.0):
        seen["url"] = url
        seen["headers"] = headers
        seen["model"] = model
        from agent.doctor.model_provider_http import ModelsProbeResult

        return ModelsProbeResult(
            ok=False,
            message="Invalid API key.",
            status_code=403,
        )

    monkeypatch.setattr(
        "agent.doctor.model_provider_http.probe_chat_completions", _fake
    )
    result = probe_llm_api_key("opencode", "sk-bogus", label="OpenCode Zen")
    assert result.ok is False
    assert seen["url"] == "https://opencode.ai/zen/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer sk-bogus"


def test_probe_llm_api_key_nvidia_uses_chat(monkeypatch):
    seen: dict = {}

    def _fake(url, headers, *, label, model, timeout=30.0):
        seen["url"] = url
        seen["model"] = model
        from agent.doctor.model_provider_http import ModelsProbeResult

        return ModelsProbeResult(ok=True, message=f"{label} API key works.", status_code=200)

    monkeypatch.setattr(
        "agent.doctor.model_provider_http.probe_chat_completions", _fake
    )
    result = probe_llm_api_key("nvidia", "nvapi-test", label="NVIDIA")
    assert result.ok is True
    assert seen["url"].endswith("/chat/completions")
    assert seen["model"] == "meta/llama-3.1-8b-instruct"


def test_probe_llm_api_key_anthropic_uses_messages(monkeypatch):
    seen: dict = {}

    def _fake(api_key, *, label="Anthropic", model="", timeout=30.0):
        seen["api_key"] = api_key
        seen["model"] = model
        from agent.doctor.model_provider_http import ModelsProbeResult

        return ModelsProbeResult(ok=True, message=f"{label} API key works.", status_code=200)

    monkeypatch.setattr(
        "agent.doctor.model_provider_http.probe_anthropic_messages", _fake
    )
    result = probe_llm_api_key("anthropic", "sk-ant-test", label="Anthropic")
    assert result.ok is True
    assert seen["api_key"] == "sk-ant-test"
    assert "haiku" in seen["model"]


def test_probe_llm_api_key_google_uses_openai_compat_chat(monkeypatch):
    seen: dict = {}

    def _fake(url, headers, *, label, model, timeout=30.0):
        seen["url"] = url
        seen["model"] = model
        from agent.doctor.model_provider_http import ModelsProbeResult

        return ModelsProbeResult(ok=True, message=f"{label} API key works.", status_code=200)

    monkeypatch.setattr(
        "agent.doctor.model_provider_http.probe_chat_completions", _fake
    )
    result = probe_llm_api_key("google", "AIza-test", label="Google Gemini")
    assert result.ok is True
    assert "openai" in seen["url"]
    assert seen["url"].endswith("/chat/completions")


def test_probe_llm_api_key_qwen_subscription_discovers_token_plan(monkeypatch):
    seen: list[str] = []

    def _fake(url, headers, *, label, model, timeout=30.0):
        seen.append(url)
        from agent.doctor.model_provider_http import ModelsProbeResult

        if "token-plan" in url and model == "qwen3.7-plus":
            return ModelsProbeResult(
                ok=True, message=f"{label} API key works.", status_code=200
            )
        return ModelsProbeResult(
            ok=False,
            message="Invalid API key. (invalid access token or token expired)",
            status_code=401,
        )

    monkeypatch.setattr(
        "agent.doctor.model_provider_http.probe_chat_completions", _fake
    )
    result = probe_llm_api_key("qwen", "sk-sp-token-test", label="Qwen Cloud")
    assert result.ok is True
    assert result.base_url == (
        "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    )
    assert seen[0].startswith(
        "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/"
    )


def test_probe_llm_api_key_qwen_paygo_uses_compatible_mode(monkeypatch):
    seen: dict = {}

    def _fake(url, headers, *, label, model, timeout=30.0):
        seen["url"] = url
        seen["model"] = model
        from agent.doctor.model_provider_http import ModelsProbeResult

        return ModelsProbeResult(ok=True, message=f"{label} API key works.", status_code=200)

    monkeypatch.setattr(
        "agent.doctor.model_provider_http.probe_chat_completions", _fake
    )
    result = probe_llm_api_key("qwen", "sk-ws-paygo-test", label="Qwen Cloud")
    assert result.ok is True
    assert seen["url"] == (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
    )
    assert seen["model"] == "qwen3.7-plus"
    assert result.base_url == (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )


def test_probe_models_endpoint_still_works(monkeypatch):
    class _Resp:
        status_code = 200
        text = '{"data":[{"id":"a"}]}'

        def json(self):
            return {"data": [{"id": "a"}]}

    monkeypatch.setitem(
        __import__("sys").modules,
        "httpx",
        SimpleNamespace(get=lambda *_a, **_k: _Resp()),
    )
    result = probe_models_endpoint(
        "https://example.com/v1/models",
        {"Authorization": "Bearer x"},
        label="Example",
    )
    assert result.ok is True
    assert result.model_count == 1
