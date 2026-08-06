"""Unit tests for multimodal modality allowlists and extension mapping."""

from agent.model_catalog.modality_support import (
    allowlist_modalities,
    modality_for_extension,
    model_supports_audio_inputs,
    model_supports_image_inputs,
    model_supports_modality,
    model_supports_pdf_inputs,
    model_supports_video_inputs,
    profile_supports_modality,
)


def test_modality_for_extension_deep_agents_table():
    assert modality_for_extension(".png") == "image"
    assert modality_for_extension("PDF") == "file"
    assert modality_for_extension(".wav") == "audio"
    assert modality_for_extension(".mp4") == "video"
    assert modality_for_extension(".csv") is None


def test_local_models_default_false():
    assert model_supports_image_inputs("local", "llama3.2") is False
    assert model_supports_pdf_inputs("local", "llama3.2") is False
    assert allowlist_modalities("local", "anything") == set()


def test_local_gemma4_and_nemotron3_image():
    assert model_supports_image_inputs("local", "gemma4:31b-mlx") is True
    assert model_supports_image_inputs("local", "gemma4:e2b") is True
    assert model_supports_image_inputs("local", "nemotron3:33b") is True
    assert model_supports_image_inputs("local", "nvidia/nemotron-3-nano") is True
    assert model_supports_pdf_inputs("local", "gemma4:31b-mlx") is False
    assert allowlist_modalities("local", "gemma4:31b-mlx") == {"image"}


def test_local_diffusion_gemma_image():
    # oMLX Chat serves diffusion_gemma via mlx-vlm; sandwalk must allow images.
    assert (
        model_supports_image_inputs(
            "local", "diffusiongemma-26B-A4B-it-4bit"
        )
        is True
    )
    assert (
        model_supports_image_inputs(
            "compatible", "mlx-community/diffusiongemma-26B-A4B-it-4bit"
        )
        is True
    )
    assert model_supports_image_inputs("local", "diffusion-gemma-4b") is True


def test_openai_runtime_provider_keeps_local_vlm_image():
    # Catalog labels oMLX models as local, but AgentComposerSlot remaps the
    # runtime provider to openai for the wire protocol. Injection must still
    # treat Diffusion Gemma / Qwen3.5 as vision-capable.
    assert (
        model_supports_image_inputs(
            "openai", "diffusiongemma-26B-A4B-it-4bit"
        )
        is True
    )
    assert model_supports_image_inputs("openai", "Qwen3.5-4B-MLX-4bit") is True
    assert model_supports_video_inputs("openai", "Qwen3.5-4B-MLX-4bit") is True
    # Plain local text models stay false even under openai runtime.
    assert model_supports_image_inputs("openai", "llama3.2") is False


def test_local_qwen35_and_qwen36_image_and_video():
    # Qwen3.5 / 3.6 are unified multimodal families (image + video).
    assert model_supports_image_inputs("local", "Qwen3.5-4B-MLX-4bit") is True
    assert model_supports_video_inputs("local", "Qwen3.5-4B-MLX-4bit") is True
    assert (
        model_supports_image_inputs(
            "compatible", "mlx-community/Qwen3.5-4B-MLX-4bit"
        )
        is True
    )
    assert (
        model_supports_image_inputs("local", "Unsloth Qwen3.6 35B A3B UD")
        is True
    )
    assert model_supports_video_inputs("local", "Qwen3.6-35B-A3B") is True
    assert allowlist_modalities("local", "Qwen3.6-35B-A3B") == {
        "image",
        "video",
    }
    # Plain Qwen3 (not 3.5/3.6) stays text-only unless it has a -vl marker.
    assert model_supports_image_inputs("local", "qwen3:8b") is False
    # DeepSeek-V4-Flash is an LLM in oMLX (mlx-lm), not a VLM.
    assert model_supports_image_inputs("local", "DeepSeek-V4-Flash") is False
    assert model_supports_image_inputs("local", "Deepseek V4 Flash") is False
    # Gemma / Diffusion Gemma remain image-only (no video column).
    assert allowlist_modalities("local", "gemma4:31b-mlx") == {"image"}
    assert allowlist_modalities(
        "local", "diffusiongemma-26B-A4B-it-4bit"
    ) == {"image"}


def test_claude_and_gpt_image_pdf():
    assert model_supports_image_inputs("anthropic", "claude-sonnet-4-5") is True
    assert model_supports_pdf_inputs("anthropic", "claude-sonnet-4-5") is True
    assert model_supports_image_inputs("openai", "gpt-4o") is True
    assert model_supports_pdf_inputs("openai", "gpt-5.6-sol") is True
    assert model_supports_audio_inputs("openai", "gpt-4o") is False


def test_gateway_providers_use_model_family_modalities():
    # OpenCode / OpenRouter host vendor families under one provider label.
    assert model_supports_image_inputs("opencode", "kimi-k3") is True
    assert model_supports_video_inputs("opencode", "kimi-k3") is True
    assert model_supports_image_inputs("opencode", "kimi-k2.7-code") is True
    assert model_supports_image_inputs("opencode", "claude-sonnet-4-5") is True
    assert model_supports_pdf_inputs("opencode", "claude-sonnet-4-5") is True
    assert model_supports_image_inputs("opencode", "gpt-5.4") is True
    assert model_supports_image_inputs("openrouter", "kimi-k3") is True
    assert model_supports_image_inputs(
        "openrouter", "anthropic/claude-sonnet-5"
    ) is True
    assert model_supports_pdf_inputs(
        "openrouter", "anthropic/claude-sonnet-5"
    ) is True


def test_deepseek_v4_is_text_only():
    # OpenRouter architecture + DeepSeek API docs: text→text, no image blocks.
    for mid in (
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        "deepseek-v4-flash-0731",
        "deepseek/deepseek-v4-pro",
        "deepseek/deepseek-v4-flash-0731",
    ):
        assert model_supports_image_inputs("deepseek", mid) is False
        assert model_supports_image_inputs("openrouter", mid) is False
        assert model_supports_image_inputs("qwen", mid) is False


def test_openrouter_vision_catalog_rows():
    assert model_supports_image_inputs(
        "openrouter", "qwen/qwen3.7-flash"
    ) is True
    assert model_supports_video_inputs(
        "openrouter", "qwen/qwen3.7-flash"
    ) is True
    assert model_supports_image_inputs(
        "openrouter", "qwen/qwen3.7-max"
    ) is False
    assert model_supports_image_inputs(
        "openrouter", "qwen/qwen3.7-plus"
    ) is True
    assert model_supports_video_inputs(
        "openrouter", "qwen/qwen3.7-plus"
    ) is False
    assert model_supports_image_inputs(
        "openrouter", "mistralai/mistral-large-2512"
    ) is True
    assert model_supports_image_inputs(
        "openrouter", "meta/muse-spark-1.1"
    ) is True
    assert model_supports_image_inputs(
        "openrouter", "xiaomi/mimo-v2.5"
    ) is True
    # Text-only Nemotron Ultra free tier must not inherit local VL heuristics.
    assert model_supports_image_inputs(
        "openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"
    ) is False


def test_gemini_full_multimodal():
    assert model_supports_image_inputs("google", "gemini-2.5-flash") is True
    assert model_supports_pdf_inputs("google", "gemini-2.5-flash") is True
    assert model_supports_audio_inputs("google", "gemini-2.5-flash") is True
    assert model_supports_video_inputs("google", "gemini-2.5-flash") is True


def test_profile_overrides_true():
    assert (
        model_supports_modality(
            "local",
            "custom-model",
            "image",
            profile={"image_inputs": True},
        )
        is True
    )


def test_profile_supports_modality_none_when_missing():
    assert profile_supports_modality({}, "image") is None
    assert profile_supports_modality({"image_inputs": False}, "image") is False
