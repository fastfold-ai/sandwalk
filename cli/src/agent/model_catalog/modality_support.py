"""Per-model multimodal input capability checks (image / PDF / audio / video).

LangChain exposes a beta ``ModelProfile`` with keys like ``image_inputs`` and
``pdf_inputs`` (from models.dev tables). Coverage is incomplete for new catalog
ids and all local/OpenAI-compatible profiles, so we combine:

1. Live ``chat_model.profile`` when available
2. Provider/model allowlist heuristics (default False for unknown local models)
"""

from __future__ import annotations

from typing import Any, Literal

ModalityKind = Literal["image", "file", "audio", "video"]

# Deep Agents multimodal extension table → content-block type.
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".heif"})
FILE_EXTENSIONS = frozenset({".pdf", ".ppt", ".pptx"})
AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".aiff", ".aac", ".ogg", ".flac"})
VIDEO_EXTENSIONS = frozenset(
    {".mp4", ".mpeg", ".mov", ".avi", ".flv", ".mpg", ".webm", ".wmv", ".3gpp"}
)

_PROFILE_KEY: dict[ModalityKind, str] = {
    "image": "image_inputs",
    "file": "pdf_inputs",
    "audio": "audio_inputs",
    "video": "video_inputs",
}

# Local / Ollama / MLX vision families (name markers).
# DeepSeek-V4-Flash is intentionally omitted: oMLX serves it via mlx-lm (text LLM).
_LOCAL_IMAGE_MARKERS = (
    "diffusiongemma",
    "diffusion-gemma",
    "gemma4",
    "gemma-4",
    "nemotron3",
    # Prefer specific local tags — bare ``nemotron-3`` also matches text-only
    # OpenRouter ``nvidia/nemotron-3-ultra-…`` rows.
    "nemotron-3-nano",
    "nemotron-3-super",
    "llava",
    "bakllava",
    "moondream",
    "minicpm-v",
    "minicpmv",
    "qwen2-vl",
    "qwen2.5-vl",
    "qwen2-5-vl",
    "qwen3-vl",
    "qwen-vl",
    "llama3.2-vision",
    "llama-3.2-vision",
    "pixtral",
)

# Qwen3.5 / 3.6 are unified multimodal (text + image + video) per HF / mlx-vlm.
_LOCAL_IMAGE_VIDEO_MARKERS = (
    "qwen3.5",
    "qwen3-5",
    "qwen3_5",
    "qwen3.6",
    "qwen3-6",
    "qwen3_6",
)


def modality_for_extension(suffix: str) -> ModalityKind | None:
    """Return the multimodal block kind for a file suffix, or None if not multimodal."""
    ext = str(suffix or "").strip().lower()
    if not ext.startswith("."):
        ext = f".{ext}" if ext else ""
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in FILE_EXTENSIONS:
        return "file"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def profile_supports_modality(profile: Any, kind: ModalityKind) -> bool | None:
    """Return True/False from a LangChain ModelProfile, or None if unknown."""
    if profile is None:
        return None
    key = _PROFILE_KEY[kind]
    try:
        if hasattr(profile, "get"):
            value = profile.get(key)
        else:
            value = getattr(profile, key, None)
    except Exception:  # noqa: BLE001
        return None
    if value is None:
        return None
    return bool(value)


def _is_local_or_compatible(provider: str | None) -> bool:
    provider_norm = str(provider or "").strip().lower()
    return provider_norm in {"local", "compatible", "openai-compatible", ""}


def _openai_cloud_multimodal(model_id: str) -> set[ModalityKind]:
    value = model_id.lower()
    kinds: set[ModalityKind] = set()
    # GPT-4o / 4.1 / 5 families and o-series generally accept images; many also PDF.
    if (
        value.startswith("gpt-4o")
        or value.startswith("gpt-4.1")
        or value.startswith("gpt-5")
        or value.startswith("o1")
        or value.startswith("o3")
        or value.startswith("o4")
    ):
        kinds.update({"image", "file"})
    return kinds


def _anthropic_multimodal(model_id: str) -> set[ModalityKind]:
    value = model_id.lower()
    if value.startswith("claude-"):
        # Modern Claude models accept images + PDFs as document/file blocks.
        return {"image", "file"}
    return set()


def _google_multimodal(model_id: str) -> set[ModalityKind]:
    value = model_id.lower()
    if not value.startswith("gemini-"):
        return set()
    # Gemini multimodal family — image/PDF widely; audio/video on many flash/pro.
    kinds: set[ModalityKind] = {"image", "file", "audio", "video"}
    return kinds


def _xai_multimodal(model_id: str) -> set[ModalityKind]:
    value = model_id.lower()
    if value.startswith("grok-"):
        return {"image"}
    return set()


def _moonshot_multimodal(model_id: str) -> set[ModalityKind]:
    value = model_id.lower()
    # K3 / K2.x support vision (OpenRouter lists image on K2.7 Code too).
    # K2.5 / K3 also take video per LangChain / Moonshot docs.
    if value.startswith("kimi-k3") or value.startswith("kimi-k2."):
        kinds: set[ModalityKind] = {"image"}
        if value.startswith("kimi-k2.5") or value.startswith("kimi-k3"):
            kinds.add("video")
        return kinds
    return set()


def _together_multimodal(model_id: str) -> set[ModalityKind]:
    """Per-model modalities for Together reseller ids (org/name).

    Inkling: native text + image + audio (Thinking Machines model card /
    Together docs). No native PDF/file or video input.
    Llama 4 Maverick: native text + image.
    Other curated Together rows stay text-only until probed.
    """
    value = model_id.lower()
    if "inkling" in value or value.endswith("/inkling"):
        return {"image", "audio"}
    if "llama-4-maverick" in value or "llama4-maverick" in value:
        return {"image"}
    return set()


def _mistral_multimodal(model_id: str) -> set[ModalityKind]:
    """Mistral vision families (Pixtral + Large image/PDF on OpenRouter)."""
    value = model_id.lower()
    if "pixtral" in value or "mistral-large" in value:
        return {"image", "file"}
    return set()


def _meta_multimodal(model_id: str) -> set[ModalityKind]:
    """Meta Muse Spark (OpenRouter: text+image+file+audio+video)."""
    value = model_id.lower()
    if "muse-spark" in value:
        return {"image", "file", "audio", "video"}
    return set()


def _xiaomi_multimodal(model_id: str) -> set[ModalityKind]:
    """Xiaomi MiMo V2.x multimodal (OpenRouter input modalities)."""
    value = model_id.lower()
    if "mimo-v2" in value or value.startswith("mimo-"):
        return {"image", "audio", "video"}
    return set()


def _qwen_multimodal(model_id: str) -> set[ModalityKind]:
    """Qwen Cloud marketplace Visual models (qwencloud.com/models)."""
    value = model_id.lower()
    # Native vision-language Qwen ids. Third-party resale models on the same
    # endpoint (DeepSeek / GLM) stay text-only — DeepSeek V4 is text→text on
    # OpenRouter and api-docs.deepseek.com (image blocks unsupported).
    # Flash / 3.8: image+video. Plus: image (OpenRouter; video optional).
    if (
        value.startswith("qwen3.8")
        or value.startswith("qwen3.7-flash")
        or value.startswith("qwen3.6-flash")
    ):
        return {"image", "video"}
    if value.startswith("qwen3.7-plus") or value.startswith("qwen3.6-plus"):
        return {"image"}
    return set()


def _normalize_local_model_name(model_id: str) -> str:
    """Strip org prefix and normalize separators for local tag matching."""
    value = (
        str(model_id or "")
        .strip()
        .lower()
        .replace("_", "-")
        .replace(" ", "-")
    )
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    return value


def _name_matches_marker(name: str, base: str, marker: str) -> bool:
    return (
        marker in name
        or name.startswith(marker)
        or base.startswith(marker)
    )


def _local_multimodal(model_id: str) -> set[ModalityKind]:
    """Heuristics for Ollama / MLX / OpenAI-compatible local vision models."""
    name = _normalize_local_model_name(model_id)
    if not name:
        return set()
    base = name.split(":", 1)[0]

    if any(
        _name_matches_marker(name, base, marker)
        for marker in _LOCAL_IMAGE_VIDEO_MARKERS
    ):
        return {"image", "video"}

    if any(
        _name_matches_marker(name, base, marker)
        for marker in _LOCAL_IMAGE_MARKERS
    ):
        return {"image"}

    # Generic markers used by many local VL checkpoints.
    if "vision" in name or "-vl" in name or base.endswith("-vl") or base.endswith("vl"):
        return {"image"}
    return set()


def _gateway_multimodal(model_id: str) -> set[ModalityKind]:
    """Modalities for discovery gateways that host many first-party families.

    Same bare id can be served by Moonshot and OpenCode Zen (e.g. ``kimi-k3``);
    capabilities follow the model family, not the gateway label. OpenRouter-style
    ``org/name`` ids are matched on the bare name as well.
    """
    value = str(model_id or "").strip()
    candidates = [value]
    if "/" in value:
        candidates.append(value.rsplit("/", 1)[-1])
    kinds: set[ModalityKind] = set()
    for candidate in candidates:
        kinds |= _openai_cloud_multimodal(candidate)
        kinds |= _anthropic_multimodal(candidate)
        kinds |= _google_multimodal(candidate)
        kinds |= _xai_multimodal(candidate)
        kinds |= _moonshot_multimodal(candidate)
        kinds |= _together_multimodal(candidate)
        kinds |= _mistral_multimodal(candidate)
        kinds |= _meta_multimodal(candidate)
        kinds |= _xiaomi_multimodal(candidate)
        kinds |= _qwen_multimodal(candidate)
        kinds |= _local_multimodal(candidate)
    return kinds


def allowlist_modalities(
    provider: str | None,
    model_id: str | None,
) -> set[ModalityKind]:
    """Static allowlist of modalities for a provider/model pair."""
    provider_norm = str(provider or "").strip().lower()
    value = str(model_id or "").strip()
    if not value:
        return set()
    # Local / compatible: inject only for known vision families (or LC profile).
    if provider_norm in {"local", "compatible", "openai-compatible"}:
        return _local_multimodal(value)

    # OpenCode Zen / OpenRouter discover many vendor families under one provider.
    if provider_norm in {"opencode", "openrouter"}:
        return _gateway_multimodal(value)

    if provider_norm in {"openai", "nvidia"}:
        kinds = _openai_cloud_multimodal(value)
        # Local VLMs (oMLX / Ollama / MLX) are catalogued as provider=local but
        # remapped to openai at runtime for the OpenAI-compatible wire protocol.
        # Keep vision injection working for those model ids.
        kinds |= _local_multimodal(value)
        return kinds
    if provider_norm == "anthropic":
        return _anthropic_multimodal(value)
    if provider_norm == "google":
        return _google_multimodal(value)
    if provider_norm == "xai":
        return _xai_multimodal(value)
    if provider_norm == "moonshot":
        return _moonshot_multimodal(value)
    if provider_norm == "together":
        return _together_multimodal(value)
    if provider_norm == "mistral":
        return _mistral_multimodal(value)
    if provider_norm == "qwen":
        return _qwen_multimodal(value)
    # DeepSeek / MiniMax curated text flagships — no native image injection.
    # DeepSeek V4 (Pro/Flash) is text-only on api.deepseek.com and OpenRouter
    # (``input_modalities: ["text"]``; Anthropic-compat marks image unsupported).
    if provider_norm in {"deepseek", "minimax"}:
        return set()
    return set()


def model_supports_modality(
    provider: str | None,
    model_id: str | None,
    kind: ModalityKind,
    *,
    profile: Any = None,
) -> bool:
    """Return True when user-turn content blocks of ``kind`` may be injected."""
    from_profile = profile_supports_modality(profile, kind)
    if from_profile is True:
        return True
    if from_profile is False and not _is_local_or_compatible(provider):
        # Explicit profile denial for a known cloud model.
        # Still allow allowlist to override missing/stale profiles for new ids.
        pass
    return kind in allowlist_modalities(provider, model_id)


def model_supports_image_inputs(
    provider: str | None, model_id: str | None, *, profile: Any = None
) -> bool:
    return model_supports_modality(provider, model_id, "image", profile=profile)


def model_supports_pdf_inputs(
    provider: str | None, model_id: str | None, *, profile: Any = None
) -> bool:
    return model_supports_modality(provider, model_id, "file", profile=profile)


def model_supports_audio_inputs(
    provider: str | None, model_id: str | None, *, profile: Any = None
) -> bool:
    return model_supports_modality(provider, model_id, "audio", profile=profile)


def model_supports_video_inputs(
    provider: str | None, model_id: str | None, *, profile: Any = None
) -> bool:
    return model_supports_modality(provider, model_id, "video", profile=profile)


def modality_capability_fields(
    provider: str | None,
    model_id: str | None,
    *,
    profile: Any = None,
) -> dict[str, bool]:
    """API/catalog snake_case fields for multimodal capabilities."""
    return {
        "supports_image_inputs": model_supports_image_inputs(
            provider, model_id, profile=profile
        ),
        "supports_pdf_inputs": model_supports_pdf_inputs(
            provider, model_id, profile=profile
        ),
        "supports_audio_inputs": model_supports_audio_inputs(
            provider, model_id, profile=profile
        ),
        "supports_video_inputs": model_supports_video_inputs(
            provider, model_id, profile=profile
        ),
    }
