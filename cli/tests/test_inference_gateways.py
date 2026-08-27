"""Cerebras, Groq, and Fireworks — native LangChain + OpenAI-compat registration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.config import API_KEYS, OPENAI_COMPATIBLE_PROVIDERS, VALID_LLM_PROVIDERS
from agent.model_catalog import (
    AVAILABLE_MODELS,
    catalog_provider_for_model,
    model_supports_image_inputs,
)
from cli.setup.providers import _parse_provider_list


def test_inference_gateways_registered():
    expected = {
        "cerebras": (
            "https://api.cerebras.ai/v1",
            "CEREBRAS_API_KEY",
            "llm.cerebras_api_key",
            "gpt-oss-120b",
        ),
        "groq": (
            "https://api.groq.com/openai/v1",
            "GROQ_API_KEY",
            "llm.groq_api_key",
            "llama-3.3-70b-versatile",
        ),
        "fireworks": (
            "https://api.fireworks.ai/inference/v1",
            "FIREWORKS_API_KEY",
            "llm.fireworks_api_key",
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
        ),
    }
    for provider, (base_url, env_var, config_key, default_model) in expected.items():
        assert provider in VALID_LLM_PROVIDERS
        assert provider in OPENAI_COMPATIBLE_PROVIDERS
        meta = OPENAI_COMPATIBLE_PROVIDERS[provider]
        assert meta["base_url"] == base_url
        assert meta["env_var"] == env_var
        assert meta["config_key"] == config_key
        assert meta["default_model"] == default_model
        assert meta.get("discover_models", "").lower() in {"1", "true", "yes"}
        assert config_key in API_KEYS
        assert API_KEYS[config_key]["provider_key"] == provider
        assert API_KEYS[config_key]["env_var"] == env_var


def test_inference_gateways_catalog_and_lookup():
    assert {"gpt-oss-120b", "gemma-4-31b"} <= {
        row[0] for row in AVAILABLE_MODELS["cerebras"]
    }
    assert "llama-3.3-70b-versatile" in {row[0] for row in AVAILABLE_MODELS["groq"]}
    assert "accounts/fireworks/models/llama-v3p3-70b-instruct" in {
        row[0] for row in AVAILABLE_MODELS["fireworks"]
    }
    assert catalog_provider_for_model("gpt-oss-120b") == "cerebras"
    assert catalog_provider_for_model("gemma-4-31b") == "cerebras"
    assert catalog_provider_for_model("llama-3.3-70b-versatile") == "groq"
    assert (
        catalog_provider_for_model("accounts/fireworks/models/llama-v3p3-70b-instruct")
        == "fireworks"
    )
    assert (
        catalog_provider_for_model("meta-llama/llama-4-scout-17b-16e-instruct") == "groq"
    )


def test_groq_scout_is_vision():
    assert (
        model_supports_image_inputs(
            "groq", "meta-llama/llama-4-scout-17b-16e-instruct"
        )
        is True
    )
    assert model_supports_image_inputs("cerebras", "gpt-oss-120b") is False


def test_inference_gateways_setup_aliases():
    assert _parse_provider_list("cerebras,groq,fireworks,fireworks-ai") == [
        "cerebras",
        "groq",
        "fireworks",
    ]


def test_build_chat_model_dispatches_to_native_builders():
    from agent.deepagents_runtime.chat_model import build_chat_model

    cases = (
        ("cerebras", "build_cerebras_chat_model"),
        ("groq", "build_groq_chat_model"),
        ("fireworks", "build_fireworks_chat_model"),
    )
    for provider, builder in cases:
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None, _p=provider: {
            "llm.provider": _p,
            "llm.model": "probe",
            "llm.temperature": 0.1,
        }.get(key, default)
        with patch(
            f"agent.deepagents_runtime.chat_model.{builder}",
            return_value=f"{provider}-model",
        ) as mock_build:
            result = build_chat_model(cfg)
            assert result == f"{provider}-model"
            mock_build.assert_called_once()


def test_llm_client_recognizes_inference_gateways():
    from models.llm import LLMClient

    expected = {
        "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "gpt-oss-120b"),
        "groq": (
            "https://api.groq.com/openai/v1",
            "GROQ_API_KEY",
            "llama-3.3-70b-versatile",
        ),
        "fireworks": (
            "https://api.fireworks.ai/inference/v1",
            "FIREWORKS_API_KEY",
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
        ),
    }
    for provider, (base_url, env_var, default_model) in expected.items():
        assert provider in LLMClient.OPENAI_COMPATIBLE_BASE_URLS
        got_url, got_env = LLMClient.OPENAI_COMPATIBLE_BASE_URLS[provider]
        assert got_url == base_url
        assert got_env == env_var
        client = LLMClient(provider=provider, api_key="sk-test")
        assert client.model == default_model
        with patch("openai.OpenAI") as mock_openai:
            got = client._get_client()
            mock_openai.assert_called_once_with(api_key="sk-test", base_url=base_url)
            assert got is mock_openai.return_value
