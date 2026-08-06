"""OpenRouter provider registration, attribution, and chat-model dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.config import API_KEYS, OPENAI_COMPATIBLE_PROVIDERS, VALID_LLM_PROVIDERS
from agent.deepagents_runtime.openrouter_attribution import (
    OPENROUTER_APP_CATEGORIES,
    OPENROUTER_APP_TITLE,
    OPENROUTER_APP_URL,
    openrouter_attribution_headers,
)
from agent.model_catalog import AVAILABLE_MODELS, catalog_provider_for_model
from cli.setup.providers import _parse_provider_list


def test_openrouter_registered():
    assert "openrouter" in VALID_LLM_PROVIDERS
    assert "openrouter" in OPENAI_COMPATIBLE_PROVIDERS
    meta = OPENAI_COMPATIBLE_PROVIDERS["openrouter"]
    assert meta["base_url"] == "https://openrouter.ai/api/v1"
    assert meta["env_var"] == "OPENROUTER_API_KEY"
    assert meta["config_key"] == "llm.openrouter_api_key"
    assert meta.get("discover_models", "").lower() in {"1", "true", "yes"}
    assert API_KEYS["llm.openrouter_api_key"]["provider_key"] == "openrouter"
    assert API_KEYS["llm.openrouter_api_key"]["env_var"] == "OPENROUTER_API_KEY"
    assert _parse_provider_list("openrouter,or") == ["openrouter"]


def test_openrouter_catalog_and_lookup():
    from agent.model_catalog import DEFAULT_DISABLED_MODELS

    ids = {row[0] for row in AVAILABLE_MODELS["openrouter"]}
    assert {
        "anthropic/claude-sonnet-5",
        "anthropic/claude-opus-5",
        "openai/gpt-5.6-terra",
        "openai/gpt-5.6-luna",
        "openai/gpt-5.6-luna-pro",
        "google/gemini-3.5-flash",
        "x-ai/grok-4.5",
        "deepseek/deepseek-v4-pro",
        "thinkingmachines/inkling",
        "qwen/qwen3.7-flash",
        "moonshotai/kimi-k3",
        "moonshotai/kimi-k2.6",
        "mistralai/mistral-large-2512",
        "meta/muse-spark-1.1",
        "thinkingmachines/inkling-small",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "z-ai/glm-5.2",
        "xiaomi/mimo-v2.5",
    } <= ids
    assert "z-ai/glm-5.2" not in DEFAULT_DISABLED_MODELS
    assert "xiaomi/mimo-v2.5" not in DEFAULT_DISABLED_MODELS
    assert "moonshotai/kimi-k3" not in DEFAULT_DISABLED_MODELS
    # Curated highlights stay small; full catalog comes from discovery.
    assert len(ids) <= 40
    assert "moonshotai/kimi-k2.5" not in ids
    assert catalog_provider_for_model("anthropic/claude-sonnet-5") == "openrouter"
    # Terra / Luna enabled by default; optional extras stay hidden.
    assert "openai/gpt-5.6-terra" not in DEFAULT_DISABLED_MODELS
    assert "openai/gpt-5.6-luna" not in DEFAULT_DISABLED_MODELS
    assert "openai/gpt-5.6-luna-pro" not in DEFAULT_DISABLED_MODELS
    assert "meta/muse-spark-1.1" in DEFAULT_DISABLED_MODELS
    assert "thinkingmachines/inkling-small" in DEFAULT_DISABLED_MODELS
    assert "nvidia/nemotron-3-ultra-550b-a55b:free" in DEFAULT_DISABLED_MODELS


def test_openrouter_attribution_headers():
    headers = openrouter_attribution_headers()
    assert headers["HTTP-Referer"] == OPENROUTER_APP_URL == "https://sandwalk.sh"
    assert headers["X-OpenRouter-Title"] == OPENROUTER_APP_TITLE == "Sandwalk"
    assert headers["X-Title"] == "Sandwalk"
    assert headers["X-OpenRouter-Categories"] == ",".join(OPENROUTER_APP_CATEGORIES)
    assert "cli-agent" in headers["X-OpenRouter-Categories"]
    assert "personal-agent" in headers["X-OpenRouter-Categories"]


def test_build_chat_model_dispatches_to_openrouter():
    from agent.deepagents_runtime.chat_model import build_chat_model

    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: {
        "llm.provider": "openrouter",
        "llm.model": "anthropic/claude-sonnet-5",
        "llm.temperature": 0.1,
    }.get(key, default)

    with patch(
        "agent.deepagents_runtime.chat_model.build_openrouter_chat_model",
        return_value="openrouter-model",
    ) as mock_build:
        result = build_chat_model(cfg)
        assert result == "openrouter-model"
        mock_build.assert_called_once()


def test_build_openrouter_chat_model_sets_attribution():
    from agent.deepagents_runtime.chat_model_openrouter import build_openrouter_chat_model

    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: {
        "llm.model": "anthropic/claude-sonnet-5",
        "llm.reasoning_effort": "high",
        "llm.reasoning_fast": False,
        "llm.model_reasoning": None,
    }.get(key, default)
    cfg.llm_api_key.return_value = "sk-or-test"

    with patch(
        "langchain_openrouter.ChatOpenRouter",
        return_value=MagicMock(name="chat"),
    ) as mock_cls:
        build_openrouter_chat_model(cfg, temperature=0.2)
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["model"] == "anthropic/claude-sonnet-5"
        assert kwargs["api_key"] == "sk-or-test"
        assert kwargs["temperature"] == 0.2
        assert kwargs["app_url"] == "https://sandwalk.sh"
        assert kwargs["app_title"] == "Sandwalk"
        assert kwargs["app_categories"] == ["cli-agent", "personal-agent"]
        assert kwargs["openrouter_provider"] == {"require_parameters": True}
        assert kwargs["reasoning"] == {"effort": "high"}


def test_build_openrouter_chat_model_fast_and_gpt5_omit_temperature():
    from agent.deepagents_runtime.chat_model_openrouter import build_openrouter_chat_model

    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: {
        "llm.model": "openai/gpt-5.6-terra",
        "llm.reasoning_effort": "high",
        "llm.reasoning_fast": True,
        "llm.model_reasoning": None,
    }.get(key, default)
    cfg.llm_api_key.return_value = "sk-or-test"

    with patch(
        "langchain_openrouter.ChatOpenRouter",
        return_value=MagicMock(name="chat"),
    ) as mock_cls:
        build_openrouter_chat_model(cfg, temperature=0.2)
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["model"] == "openai/gpt-5.6-terra"
        assert "temperature" not in kwargs
        assert kwargs["reasoning"] == {"effort": "none"}


def test_build_openrouter_skips_reasoning_for_non_reasoning_models():
    from agent.deepagents_runtime.chat_model_openrouter import build_openrouter_chat_model

    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: {
        "llm.model": "openai/gpt-4o-mini",
        "llm.reasoning_effort": "high",
        "llm.reasoning_fast": False,
        "llm.model_reasoning": None,
    }.get(key, default)
    cfg.llm_api_key.return_value = "sk-or-test"

    with patch(
        "langchain_openrouter.ChatOpenRouter",
        return_value=MagicMock(name="chat"),
    ) as mock_cls:
        build_openrouter_chat_model(cfg, temperature=0.2)
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["temperature"] == 0.2
        assert "reasoning" not in kwargs


def test_openrouter_discovery_filters_models_without_tools():
    from agent import model_discovery

    payload = {
        "data": [
            {
                "id": "google/gemma-2-9b-it",
                "supported_parameters": ["temperature", "max_tokens"],
                "context_length": 8192,
            },
            {
                "id": "anthropic/claude-sonnet-4.5",
                "supported_parameters": ["tools", "tool_choice", "temperature"],
                "context_length": 200000,
            },
            {"id": "mystery/no-params"},
        ]
    }
    with patch.object(
        model_discovery, "_request_json", return_value=(payload, None)
    ):
        names, windows, err = model_discovery.fetch_openai_models_with_context(
            "https://openrouter.ai/api/v1"
        )
    assert err is None
    assert names == ["anthropic/claude-sonnet-4.5"]
    assert windows == {"anthropic/claude-sonnet-4.5": 200000}
    assert model_discovery.openrouter_model_supports_tools(
        {"supported_parameters": ["tools"]}
    )
    assert not model_discovery.openrouter_model_supports_tools(
        {"supported_parameters": ["temperature"]}
    )


def test_llm_client_recognizes_openrouter_provider():
    from models.llm import LLMClient

    assert "openrouter" in LLMClient.OPENAI_COMPATIBLE_BASE_URLS
    base_url, env_var = LLMClient.OPENAI_COMPATIBLE_BASE_URLS["openrouter"]
    assert base_url == "https://openrouter.ai/api/v1"
    assert env_var == "OPENROUTER_API_KEY"
    client = LLMClient(provider="openrouter", api_key="sk-test")
    assert client.model == "anthropic/claude-sonnet-5"
    with patch("openai.OpenAI") as mock_openai:
        got = client._get_client()
        kwargs = mock_openai.call_args.kwargs
        assert kwargs["api_key"] == "sk-test"
        assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert kwargs["default_headers"]["HTTP-Referer"] == "https://sandwalk.sh"
        assert kwargs["default_headers"]["X-OpenRouter-Title"] == "Sandwalk"
        assert "cli-agent" in kwargs["default_headers"]["X-OpenRouter-Categories"]
        assert got is mock_openai.return_value


def test_doctor_probe_includes_openrouter_attribution_headers():
    from agent.doctor.model_provider_http import probe_llm_api_key

    with patch(
        "agent.doctor.model_provider_http.probe_chat_completions",
        return_value=MagicMock(ok=True, message="ok"),
    ) as mock_probe:
        probe_llm_api_key("openrouter", "sk-or-test", label="OpenRouter")
        url, headers = mock_probe.call_args.args[:2]
        assert url.endswith("/chat/completions")
        assert "openrouter.ai" in url
        assert headers["Authorization"] == "Bearer sk-or-test"
        assert headers["HTTP-Referer"] == "https://sandwalk.sh"
        assert headers["X-OpenRouter-Title"] == "Sandwalk"
        assert "cli-agent" in headers["X-OpenRouter-Categories"]


def test_openrouter_discovered_models_start_disabled():
    from agent.config import Config
    from agent_server.models_service.catalog_discovery import (
        _seed_openrouter_discovered_hidden,
    )

    cfg = Config.load()
    cfg.set("llm.catalog_defaults_version", 99)
    cfg.set("llm.hidden_models", [])
    cfg.set("llm.openrouter_seen_models", [])
    cfg.save()

    known = {"anthropic/claude-sonnet-5"}
    discovered = [
        "anthropic/claude-sonnet-5",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "vendor/brand-new-model",
    ]
    hidden = _seed_openrouter_discovered_hidden(cfg, discovered, known)
    # Curated/known ids are not auto-hidden here; brand-new discoveries are.
    assert "vendor/brand-new-model" in hidden
    assert "nvidia/nemotron-3-ultra-550b-a55b:free" in hidden
    assert "anthropic/claude-sonnet-5" not in hidden

    reloaded = Config.load()
    assert "vendor/brand-new-model" in set(reloaded.hidden_models())
    assert "vendor/brand-new-model" in set(
        reloaded.get("llm.openrouter_seen_models") or []
    )

    # Re-enable sticks: second seed must not re-hide.
    reloaded.set_model_hidden("vendor/brand-new-model", False)
    reloaded.save()
    hidden2 = _seed_openrouter_discovered_hidden(
        Config.load(), discovered, known
    )
    assert "vendor/brand-new-model" not in hidden2
