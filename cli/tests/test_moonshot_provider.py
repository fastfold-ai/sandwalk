"""Moonshot / Kimi catalog, thinking resolve, and chat-model dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.config import API_KEYS, OPENAI_COMPATIBLE_PROVIDERS, VALID_LLM_PROVIDERS
from agent.model_catalog import (
    AVAILABLE_MODELS,
    DEFAULT_DISABLED_MODELS,
    catalog_provider_for_model,
    context_window_for_model,
    effective_moonshot_thinking,
    effective_unsloth_enable_thinking,
    model_supports_image_inputs,
    model_supports_reasoning_effort,
    moonshot_model_supports_thinking_toggle,
    upsert_model_reasoning,
)
from cli.setup.providers import _parse_provider_list


def test_moonshot_in_catalog_and_defaults():
    rows = AVAILABLE_MODELS.get("moonshot") or []
    ids = {row[0] for row in rows}
    assert {
        "kimi-k3",
        "kimi-k2.6",
        "kimi-k2.7-code",
        "kimi-k2.7-code-highspeed",
        "kimi-k2.5",
    } <= ids
    assert "kimi-k2.5" in DEFAULT_DISABLED_MODELS
    assert "kimi-k3" not in DEFAULT_DISABLED_MODELS


def test_moonshot_context_windows_and_lookup():
    assert context_window_for_model("kimi-k3") == 1_000_000
    assert context_window_for_model("kimi-k2.6") == 256_000
    assert context_window_for_model("kimi-k2.7-code") == 256_000
    assert catalog_provider_for_model("kimi-k3") == "moonshot"
    assert catalog_provider_for_model("moonshot-v1-32k") == "moonshot"


def test_moonshot_modality_and_thinking_support():
    assert model_supports_image_inputs("moonshot", "kimi-k3") is True
    assert model_supports_image_inputs("moonshot", "kimi-k2.6") is True
    # K2.7 Code is vision-capable too (OpenRouter lists image on it).
    assert model_supports_image_inputs("moonshot", "kimi-k2.7-code") is True
    assert model_supports_image_inputs("moonshot", "moonshot-v1-32k") is False
    assert moonshot_model_supports_thinking_toggle("kimi-k2.6") is True
    assert moonshot_model_supports_thinking_toggle("kimi-k2.5") is True
    assert moonshot_model_supports_thinking_toggle("kimi-k3") is False
    assert moonshot_model_supports_thinking_toggle("kimi-k2.7-code") is False
    assert model_supports_reasoning_effort("moonshot", "kimi-k2.6") is True
    assert model_supports_reasoning_effort("moonshot", "kimi-k3") is False


def test_unsloth_thinking_via_compatible_backend():
    assert (
        model_supports_reasoning_effort(
            "local", "gemma-4-E2B-it-GGUF", compatible_backend="unsloth"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort(
            "local", "gemma-4-E2B-it-GGUF", compatible_backend="ollama"
        )
        is False
    )
    assert effective_unsloth_enable_thinking(effort="medium", fast=False) is True
    assert effective_unsloth_enable_thinking(effort="high", fast=True) is False
    assert effective_moonshot_thinking(effort="medium", fast=False) is True
    assert effective_moonshot_thinking(effort="low", fast=True) is False


def test_moonshot_api_key_and_provider_metadata():
    assert "moonshot" in VALID_LLM_PROVIDERS
    assert "moonshot" in OPENAI_COMPATIBLE_PROVIDERS
    assert API_KEYS["llm.moonshot_api_key"]["env_var"] == "MOONSHOT_API_KEY"
    assert API_KEYS["llm.moonshot_api_key"]["provider_key"] == "moonshot"
    assert _parse_provider_list("moonshot,kimi") == ["moonshot"]


def test_llm_client_recognizes_moonshot_provider():
    from models.llm import LLMClient

    assert "moonshot" in LLMClient.OPENAI_COMPATIBLE_BASE_URLS
    base_url, env_var = LLMClient.OPENAI_COMPATIBLE_BASE_URLS["moonshot"]
    assert base_url == "https://api.moonshot.ai/v1"
    assert env_var == "MOONSHOT_API_KEY"
    client = LLMClient(provider="moonshot", api_key="sk-test")
    assert client.model == "kimi-k2.6"
    with patch("openai.OpenAI") as mock_openai:
        got = client._get_client()
        mock_openai.assert_called_once_with(
            api_key="sk-test",
            base_url="https://api.moonshot.ai/v1",
        )
        assert got is mock_openai.return_value


def test_upsert_model_reasoning_for_moonshot():
    store = upsert_model_reasoning(
        {},
        "moonshot",
        "kimi-k2.6",
        effort="high",
        fast=False,
    )
    assert store["moonshot:kimi-k2.6"] == {"effort": "high", "fast": False}


def test_build_chat_model_dispatches_to_moonshot():
    from agent.deepagents_runtime.chat_model import build_chat_model

    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: {
        "llm.provider": "moonshot",
        "llm.model": "kimi-k2.6",
        "llm.temperature": 0.1,
        "llm.model_reasoning": {},
        "llm.reasoning_effort": "medium",
        "llm.reasoning_fast": False,
    }.get(key, default)
    cfg.llm_api_key.return_value = "sk-test"

    with patch(
        "agent.deepagents_runtime.chat_model_moonshot.ChatMoonshot",
        create=True,
    ):
        with patch(
            "agent.deepagents_runtime.chat_model.build_moonshot_chat_model",
            return_value="moonshot-model",
        ) as mock_build:
            result = build_chat_model(cfg)
            assert result == "moonshot-model"
            mock_build.assert_called_once()


def test_build_moonshot_chat_model_sets_thinking():
    from agent.deepagents_runtime.chat_model_moonshot import build_moonshot_chat_model

    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: {
        "llm.model": "kimi-k2.6",
        "llm.model_reasoning": {
            "moonshot:kimi-k2.6": {"effort": "medium", "fast": False}
        },
        "llm.reasoning_effort": "medium",
        "llm.reasoning_fast": False,
    }.get(key, default)
    cfg.llm_api_key.return_value = "sk-test"

    with patch(
        "langchain_moonshot.ChatMoonshot",
        return_value=MagicMock(name="chat"),
    ) as mock_cls:
        build_moonshot_chat_model(cfg, temperature=0.1)
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["model"] == "kimi-k2.6"
        assert kwargs["thinking"] is True
        assert kwargs["temperature"] == 1.0
        assert kwargs["api_key"] == "sk-test"


def test_build_openai_chat_model_unsloth_extra_body():
    from agent.deepagents_runtime.chat_model_openai import build_openai_chat_model

    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: {
        "llm.model": "gemma-4-E2B-it-GGUF",
        "llm.temperature": 0.1,
        "llm.model_reasoning": {
            "local:gemma-4-E2B-it-GGUF": {"effort": "medium", "fast": True}
        },
        "llm.reasoning_effort": "medium",
        "llm.reasoning_fast": False,
    }.get(key, default)
    cfg.llm_api_key.return_value = "sk-unsloth-test"
    cfg.llm_openai_base_url.return_value = "http://localhost:8888/v1"
    cfg.get_openai_profile.return_value = {
        "id": "unsloth_local",
        "backend": "unsloth",
        "base_url": "http://localhost:8888/v1",
    }

    with patch(
        "agent.config.Config._is_openai_managed_base_url",
        return_value=False,
    ), patch(
        "langchain.chat_models.init_chat_model",
        return_value=MagicMock(),
    ) as mock_init:
        build_openai_chat_model(cfg, temperature=0.1)
        kwargs = mock_init.call_args.kwargs
        assert kwargs.get("extra_body") == {"enable_thinking": False}
