"""DeepSeek / MiniMax / Mistral / Qwen — OpenAI-compatible cloud providers."""

from __future__ import annotations

from unittest.mock import patch

from agent.config import API_KEYS, OPENAI_COMPATIBLE_PROVIDERS, VALID_LLM_PROVIDERS
from agent.model_catalog import (
    AVAILABLE_MODELS,
    catalog_provider_for_model,
    model_supports_image_inputs,
    model_supports_pdf_inputs,
    model_supports_video_inputs,
)
from cli.setup.providers import _parse_provider_list


def test_new_providers_registered():
    for provider in ("deepseek", "minimax", "mistral", "qwen", "together"):
        assert provider in VALID_LLM_PROVIDERS
        assert provider in OPENAI_COMPATIBLE_PROVIDERS
        assert OPENAI_COMPATIBLE_PROVIDERS[provider]["config_key"] in API_KEYS


def test_new_providers_catalog_and_lookup():
    assert {
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    } <= {row[0] for row in AVAILABLE_MODELS["deepseek"]}
    assert {row[0] for row in AVAILABLE_MODELS["minimax"]} == {"MiniMax-M2.5"}
    assert "mistral-large-latest" in {row[0] for row in AVAILABLE_MODELS["mistral"]}
    qwen_ids = {row[0] for row in AVAILABLE_MODELS["qwen"]}
    assert {
        "qwen3.8-max",
        "qwen3.7-plus",
        "qwen3.7-flash",
        "qwen3.6-flash",
        "deepseek-v4-flash-0731",
        "deepseek-v4-pro",
        "glm-5.2",
        "qwen3-max",
    } <= qwen_ids
    assert "zai-org/GLM-5.2" in {row[0] for row in AVAILABLE_MODELS["together"]}
    assert "moonshotai/Kimi-K2.7-Code" in {row[0] for row in AVAILABLE_MODELS["together"]}

    # OpenRouter / Qwen Flash revisions stay dated so 0423 ≠ 0731 in the UI.
    openrouter = {row[0]: row[1] for row in AVAILABLE_MODELS["openrouter"]}
    assert openrouter["deepseek/deepseek-v4-flash"] == "DeepSeek V4 Flash 0423"
    assert openrouter["deepseek/deepseek-v4-flash-0731"] == "DeepSeek V4 Flash 0731"
    qwen_labels = {row[0]: row[1] for row in AVAILABLE_MODELS["qwen"]}
    assert qwen_labels["deepseek-v4-flash-0731"] == "DeepSeek V4 Flash 0731"

    assert catalog_provider_for_model("deepseek-v4-flash") == "deepseek"
    assert catalog_provider_for_model("deepseek-v4-flash-0731") == "qwen"
    assert catalog_provider_for_model("glm-5.2") == "qwen"
    assert catalog_provider_for_model("MiniMax-M2.5") == "minimax"
    assert catalog_provider_for_model("mistral-large-latest") == "mistral"
    assert catalog_provider_for_model("pixtral-large-latest") == "mistral"
    assert catalog_provider_for_model("qwen3-max") == "qwen"
    assert catalog_provider_for_model("zai-org/GLM-5.2") == "together"
    assert catalog_provider_for_model("deepseek-ai/DeepSeek-V4-Pro") == "together"


def test_new_providers_are_text_only_in_curated_matrix():
    cases = (
        ("deepseek", "deepseek-v4-flash"),
        ("deepseek", "deepseek-v4-pro"),
        ("minimax", "MiniMax-M2.5"),
        ("mistral", "mistral-small-latest"),
        ("qwen", "qwen3.7-max"),
        ("qwen", "qwen3-max"),
        ("qwen", "deepseek-v4-flash-0731"),
        ("qwen", "deepseek-v4-pro"),
        ("qwen", "glm-5.2"),
        ("together", "zai-org/GLM-5.2"),
        ("together", "moonshotai/Kimi-K2.7-Code"),
    )
    for provider, model_id in cases:
        assert model_supports_image_inputs(provider, model_id) is False
        assert model_supports_pdf_inputs(provider, model_id) is False
        assert model_supports_video_inputs(provider, model_id) is False
    # Mistral Large accepts image/PDF (OpenRouter + native vision matrix).
    assert model_supports_image_inputs("mistral", "mistral-large-latest") is True


def test_qwen_visual_models_support_image_and_video_inputs():
    assert model_supports_image_inputs("qwen", "qwen3.8-max") is True
    assert model_supports_video_inputs("qwen", "qwen3.8-max") is True
    assert model_supports_image_inputs("qwen", "qwen3.7-plus") is True
    assert model_supports_video_inputs("qwen", "qwen3.7-plus") is False
    assert model_supports_image_inputs("qwen", "qwen3.7-flash") is True
    assert model_supports_video_inputs("qwen", "qwen3.7-flash") is True
    assert model_supports_image_inputs("qwen", "qwen3.6-flash") is True
    assert model_supports_video_inputs("qwen", "qwen3.6-flash") is True
    assert model_supports_pdf_inputs("qwen", "qwen3.8-max") is False


def test_together_inkling_and_maverick_multimodal():
    from agent.model_catalog import model_supports_audio_inputs

    assert model_supports_image_inputs("together", "thinkingmachines/Inkling") is True
    assert model_supports_audio_inputs("together", "thinkingmachines/Inkling") is True
    # Model card: text / image / audio — not native PDF or video.
    assert model_supports_pdf_inputs("together", "thinkingmachines/Inkling") is False
    assert model_supports_video_inputs("together", "thinkingmachines/Inkling") is False

    assert (
        model_supports_image_inputs(
            "together", "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP4"
        )
        is True
    )
    assert (
        model_supports_pdf_inputs(
            "together", "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP4"
        )
        is False
    )


def test_new_providers_setup_aliases_and_env():
    assert _parse_provider_list(
        "deepseek,minimax,mistral,qwen,dashscope,together"
    ) == [
        "deepseek",
        "minimax",
        "mistral",
        "qwen",
        "together",
    ]
    assert API_KEYS["llm.deepseek_api_key"]["env_var"] == "DEEPSEEK_API_KEY"
    assert API_KEYS["llm.minimax_api_key"]["env_var"] == "MINIMAX_API_KEY"
    assert API_KEYS["llm.mistral_api_key"]["env_var"] == "MISTRAL_API_KEY"
    assert API_KEYS["llm.qwen_api_key"]["env_var"] == "QWEN_API_KEY"
    assert API_KEYS["llm.qwen_api_key"]["env_var_aliases"] == "DASHSCOPE_API_KEY"
    assert API_KEYS["llm.together_api_key"]["env_var"] == "TOGETHER_API_KEY"


def test_llm_client_recognizes_new_providers():
    from models.llm import LLMClient

    expected = {
        "deepseek": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY", "deepseek-v4-flash"),
        "minimax": ("https://api.minimax.io/v1", "MINIMAX_API_KEY", "MiniMax-M2.5"),
        "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY", "mistral-large-latest"),
        "qwen": (
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            "QWEN_API_KEY",
            "qwen3.7-plus",
        ),
        "together": ("https://api.together.xyz/v1", "TOGETHER_API_KEY", "zai-org/GLM-5.2"),
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


def test_normalize_qwen_base_url_appends_compatible_mode():
    from agent.config import (
        QWEN_CODING_BASE_URL,
        QWEN_PAYGO_BASE_URL,
        QWEN_TOKEN_PLAN_BASE_URL,
        normalize_qwen_base_url,
    )

    assert (
        normalize_qwen_base_url(
            "https://token-plan.ap-southeast-1.maas.aliyuncs.com"
        )
        == QWEN_TOKEN_PLAN_BASE_URL
    )
    assert (
        normalize_qwen_base_url(
            "https://dashscope-intl.aliyuncs.com"
        )
        == QWEN_PAYGO_BASE_URL
    )
    assert (
        normalize_qwen_base_url("https://coding-intl.dashscope.aliyuncs.com")
        == QWEN_CODING_BASE_URL
    )
    assert normalize_qwen_base_url(QWEN_TOKEN_PLAN_BASE_URL) == QWEN_TOKEN_PLAN_BASE_URL


def test_qwen_subscription_key_prefers_token_plan_then_persisted_override():
    from agent.config import (
        QWEN_CODING_BASE_URL,
        QWEN_PAYGO_BASE_URL,
        QWEN_TOKEN_PLAN_BASE_URL,
        Config,
        qwen_base_url_candidates,
        resolve_qwen_base_url,
    )
    from models.llm import LLMClient

    assert resolve_qwen_base_url("sk-ws-paygo") == QWEN_PAYGO_BASE_URL
    assert resolve_qwen_base_url("sk-sp-sub") == QWEN_TOKEN_PLAN_BASE_URL
    assert qwen_base_url_candidates("sk-sp-sub") == [
        QWEN_TOKEN_PLAN_BASE_URL,
        QWEN_CODING_BASE_URL,
        QWEN_PAYGO_BASE_URL,
    ]

    cfg = Config(
        data={
            "llm.qwen_api_key": "sk-sp-sub-key",
            "llm.qwen_base_url": QWEN_TOKEN_PLAN_BASE_URL,
        }
    )
    assert cfg.llm_provider_base_url("qwen") == QWEN_TOKEN_PLAN_BASE_URL

    client = LLMClient(provider="qwen", api_key="sk-sp-sub-key")
    with patch("openai.OpenAI") as mock_openai:
        client._get_client()
        mock_openai.assert_called_once_with(
            api_key="sk-sp-sub-key",
            base_url=QWEN_TOKEN_PLAN_BASE_URL,
        )
