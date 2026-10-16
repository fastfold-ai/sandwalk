"""Backend inference/normalization helpers mixed into ``Config``."""

from typing import Any


class ProfileBackendInferMixin:
    """Static helpers for normalizing and inferring OpenAI-compatible backends."""

    @classmethod
    def _normalize_openai_base_url(cls, value: Any) -> str | None:
        """Normalize OpenAI-compatible base URLs for consistent comparisons."""
        text = cls._normalized_secret(value)
        if not text:
            return None
        return text.rstrip("/")

    @staticmethod
    def _normalize_compatible_backend_name(value: Any) -> str:
        """Normalize backend aliases to canonical compatible backend ids."""
        text = str(value or "").strip().lower()
        aliases = {
            "ollama": "ollama",
            "unsloth": "unsloth",
            "omlx": "omlx",
            "ds4": "ds4",
            "deepseek": "ds4",
            "deepseek-v4": "ds4",
            "deepseek_4": "ds4",
            "llama.cpp": "llama_cpp",
            "llama_cpp": "llama_cpp",
            "llama-cpp": "llama_cpp",
            "llamacpp": "llama_cpp",
            "llama": "llama",
            "llama-app": "llama",
            "llama.app": "llama",
            "lmstudio": "lm_studio",
            "lm_studio": "lm_studio",
            "lm-studio": "lm_studio",
            "lm studio": "lm_studio",
            "custom": "other",
            "generic": "other",
            "other": "other",
            "openai": "openai",
        }
        return aliases.get(text, text)

    @staticmethod
    def infer_openai_compatible_backend(base_url: str | None, api_key: str | None = None) -> str:
        """Infer OpenAI-compatible backend type from endpoint and key hints."""
        endpoint = str(base_url or "").strip().lower()
        secret = str(api_key or "").strip().lower()
        if secret.startswith("sk-unsloth-") or "8888" in endpoint:
            return "unsloth"
        if (
            secret.startswith("dsv4-")
            or secret.startswith("sk-ds4-")
            or "deepseek-v4" in endpoint
            or "deepseek4" in endpoint
            or "ds4" in endpoint
        ):
            return "ds4"
        if ":9931" in endpoint or endpoint.rstrip("/").endswith("9931"):
            return "llama"
        if "1234" in endpoint or "lmstudio" in endpoint or "lm-studio" in endpoint:
            return "lm_studio"
        if (
            "8080" in endpoint
            or "llama.cpp" in endpoint
            or "llama-cpp" in endpoint
            or "llamacpp" in endpoint
        ):
            return "llama_cpp"
        if secret.startswith("sk-omlx-") or "omlx" in endpoint:
            return "omlx"
        if "11434" in endpoint or "ollama" in endpoint:
            return "ollama"
        # Keep legacy 8000-port inference for oMLX profiles without explicit hints.
        if "8000" in endpoint:
            return "omlx"
        return "other"

    @staticmethod
    def _infer_backend_from_model_name(model_id: str | None) -> str | None:
        """Infer backend from model id hints when endpoint is unavailable."""
        model_name = str(model_id or "").strip().lower()
        if not model_name:
            return None
        if (
            "deepseek-v4" in model_name
            or model_name.startswith("deepseek-v4")
            or model_name.startswith("ds4")
        ):
            return "ds4"
        if "omlx" in model_name:
            return "omlx"
        if "unsloth" in model_name:
            return "unsloth"
        if model_name.startswith("llama") or model_name.startswith("qwen") or model_name.startswith("phi"):
            return "ollama"
        return None

    @staticmethod
    def _looks_like_anthropic_model(model_id: str | None) -> bool:
        """Best-effort check for Anthropic model identifiers."""
        value = str(model_id or "").strip().lower()
        return value.startswith("claude-")

    @staticmethod
    def _looks_like_openai_cloud_model(model_id: str | None) -> bool:
        """Best-effort check for OpenAI cloud model identifiers."""
        value = str(model_id or "").strip().lower()
        if not value:
            return False
        if value.startswith("gpt-oss"):
            return False
        return (
            value.startswith("gpt-4")
            or value.startswith("gpt-5")
            or value.startswith("o1")
            or value.startswith("o3")
            or value.startswith("chatgpt")
        )
