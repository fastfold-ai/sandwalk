"""Secret normalization and provider API-key resolution."""

import os
import re
from typing import Any

from .providers import OPENAI_COMPATIBLE_PROVIDERS, resolve_qwen_base_url


def _provider_env_names(meta: dict[str, str]) -> list[str]:
    """Primary env var first, then any comma/space-separated aliases."""
    names: list[str] = []
    primary = str(meta.get("env_var") or "").strip()
    if primary:
        names.append(primary)
    aliases = str(meta.get("env_var_aliases") or "").strip()
    if aliases:
        for part in aliases.replace(",", " ").split():
            token = part.strip()
            if token and token not in names:
                names.append(token)
    return names


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
        """Normalize-only check for provider API keys.

        Prefix / format heuristics are intentionally not enforced — providers
        rotate key shapes (e.g. Qwen Cloud ``sk-sp-`` Coding Plan keys). Live
        probe validation is the source of truth for auth.
        """
        _ = (config_key, openai_base_url)
        cls._normalized_secret(value)
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
            for env_name in _provider_env_names(meta):
                env_key = self._normalized_secret(os.environ.get(env_name))
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
        if not meta:
            return None
        if provider == "qwen":
            configured = self._normalized_secret(self.get("llm.qwen_base_url"))
            return resolve_qwen_base_url(
                self.llm_api_key("qwen"),
                configured=configured,
            )
        return meta["base_url"]

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
