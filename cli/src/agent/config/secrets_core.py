"""Secret normalization and provider API-key resolution."""

import os
import re
from typing import Any

from .constants import ANTHROPIC_API_KEY_PATTERN, OPENAI_API_KEY_PATTERN
from .providers import OPENAI_COMPATIBLE_PROVIDERS


class SecretsCoreMixin:
    """Secret normalization/validation and ``llm_api_key`` resolution."""

    @staticmethod
    def _normalized_secret(value: Any) -> str | None:
        """Normalize secret-like values; blank/whitespace becomes None."""
        if value is None:
            return None
        text = str(value)
        # Strip ANSI escape sequences that can leak from terminal control input.
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        # Remove non-printable control characters (e.g. ^C bytes).
        text = "".join(ch for ch in text if ch.isprintable())
        text = text.strip()
        return text or None

    @classmethod
    def validate_llm_api_key(
        cls,
        config_key: str,
        value: Any,
        *,
        openai_base_url: str | None = None,
    ) -> str | None:
        """Validate provider API keys; return issue message, else None."""
        normalized = cls._normalized_secret(value)
        if normalized is None:
            return None

        if config_key == "llm.openai_api_key":
            if not cls._is_openai_managed_base_url(openai_base_url):
                return None
            if normalized.startswith("sk-ant-"):
                return (
                    "Invalid OpenAI API key format: looks like an Anthropic key ('sk-ant-...'). "
                    "Use an OpenAI key starting with 'sk-' (typically 'sk-proj-...')."
                )
            if not OPENAI_API_KEY_PATTERN.match(normalized):
                return (
                    "Invalid OpenAI API key format. Expected prefix 'sk-' "
                    "(typically 'sk-proj-...')."
                )
            return None

        if config_key == "llm.openai_compatible_api_key":
            # Compatibility endpoints frequently use placeholder or custom keys.
            return None

        if config_key in {"llm.anthropic_api_key", "llm.api_key"}:
            if not ANTHROPIC_API_KEY_PATTERN.match(normalized):
                return (
                    "Invalid Anthropic API key format. Expected prefix 'sk-ant-'."
                )

        return None

    @classmethod
    def _secret_preview(cls, value: Any) -> str:
        """Return a masked preview for secret-like values."""
        normalized = cls._normalized_secret(value)
        if not normalized:
            return "—"
        if len(normalized) <= 8:
            return "***"
        if len(normalized) <= 14:
            return f"{normalized[:4]}...{normalized[-2:]}"
        return f"{normalized[:8]}...{normalized[-4:]}"

    def llm_api_key(self, provider: str | None = None) -> str | None:
        """Get the best API key for the selected provider."""
        provider = (provider or self.get("llm.provider", "anthropic")).lower()
        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            meta = OPENAI_COMPATIBLE_PROVIDERS[provider]
            env_key = self._normalized_secret(os.environ.get(meta["env_var"]))
            if env_key:
                return env_key
            return self._normalized_secret(self.get(meta["config_key"]))
        if provider == "openai":
            profile = self.get_openai_profile()
            backend = str((profile or {}).get("backend") or "").strip().lower()
            profile_key = self._normalized_secret((profile or {}).get("api_key"))
            if backend and backend != "openai":
                # Each Local LLM profile owns its key. Do not read
                # OPENAI_COMPATIBLE_API_KEY or the retired global config slot.
                return profile_key
            env_openai_key = self._normalized_secret(os.environ.get("OPENAI_API_KEY"))
            if env_openai_key:
                return env_openai_key
            return self._normalized_secret(self.get("llm.openai_api_key"))
        # Backward compatibility: legacy llm.api_key is Anthropic-only fallback.
        return self._normalized_secret(
            self.get("llm.anthropic_api_key") or self.get("llm.api_key")
        )

    def llm_provider_base_url(self, provider: str | None = None) -> str | None:
        """Fixed base URL for first-party OpenAI-compatible providers (xai/google)."""
        provider = (provider or self.get("llm.provider", "anthropic")).lower()
        meta = OPENAI_COMPATIBLE_PROVIDERS.get(provider)
        return meta["base_url"] if meta else None

    def llm_openai_base_url(self) -> str | None:
        """Return normalized OpenAI-compatible base URL, if configured."""
        profile = self.get_openai_profile()
        backend = str((profile or {}).get("backend") or "").strip().lower()
        if backend and backend != "openai":
            profile_base_url = self._normalize_openai_base_url((profile or {}).get("base_url"))
            if profile_base_url:
                return profile_base_url

        env_override = self._normalize_openai_base_url(os.environ.get("OPENAI_BASE_URL"))
        if env_override:
            if self._is_openai_managed_base_url(env_override):
                return None
            return env_override

        value = self._normalize_openai_base_url(self.get("llm.openai_base_url"))
        if not value or self._is_openai_managed_base_url(value):
            return None
        return value
