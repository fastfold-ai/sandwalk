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


def test_claude_and_gpt_image_pdf():
    assert model_supports_image_inputs("anthropic", "claude-sonnet-4-5") is True
    assert model_supports_pdf_inputs("anthropic", "claude-sonnet-4-5") is True
    assert model_supports_image_inputs("openai", "gpt-4o") is True
    assert model_supports_pdf_inputs("openai", "gpt-5.6-sol") is True
    assert model_supports_audio_inputs("openai", "gpt-4o") is False


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
