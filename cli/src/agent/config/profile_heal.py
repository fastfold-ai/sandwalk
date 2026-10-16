"""Profile repairs after resolution — trust stored provider, never invent one."""

from typing import Any

from .providers import OPENAI_PROFILE_DEFAULTS

_LOCAL_COMPATIBLE_BACKENDS = {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "llama", "lm_studio"}


class ProfileHealMixin:
    """Third phase of ``_ensure_openai_profiles_data``.

    ``llm.provider`` and the active OpenAI profile are written by the picker /
    config APIs and are the source of truth. This phase must not rewrite
    provider from model-id prefixes (``qwen*`` → Qwen Cloud, ``gemini-*`` →
    Google, …) — that collides with local weights and multi-host catalog ids.

    The only repair left is a local-backend impossibility: an OpenAI *cloud*
    model id cannot run on Ollama/oMLX/etc., so fall back to the profile
    default model.
    """

    @classmethod
    def _heal_profile_mismatches(
        cls,
        data: dict[str, Any],
        profiles: dict[str, dict[str, Any]],
        provider_raw: str,
        configured_model: str,
        active_profile: str,
    ) -> tuple[str, str]:
        """Trust stored provider; only repair cloud-model + local-backend mismatch."""
        active_profile_data = (
            profiles.get(active_profile) if isinstance(profiles, dict) else None
        )
        active_backend = str(
            (active_profile_data or {}).get("backend") or ""
        ).strip().lower()

        if (
            provider_raw == "openai"
            and active_backend in _LOCAL_COMPATIBLE_BACKENDS
            and cls._looks_like_openai_cloud_model(configured_model)
        ):
            fallback_model = (
                str((active_profile_data or {}).get("default_model") or "").strip()
                or str(
                    OPENAI_PROFILE_DEFAULTS.get(
                        active_backend, OPENAI_PROFILE_DEFAULTS["other"]
                    ).get("default_model")
                    or "llama3.1"
                ).strip()
            )
            if fallback_model and fallback_model != configured_model:
                data["llm.model"] = fallback_model

        return provider_raw, active_profile
