"""Heal provider/model/backend mismatches after profile resolution."""

from typing import Any

from .providers import OPENAI_PROFILE_DEFAULTS

_LOCAL_COMPATIBLE_BACKENDS = {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}


class ProfileHealMixin:
    """Third phase of ``_ensure_openai_profiles_data``: mismatch healing."""

    @classmethod
    def _heal_profile_mismatches(
        cls,
        data: dict[str, Any],
        profiles: dict[str, dict[str, Any]],
        provider_raw: str,
        configured_model: str,
        active_profile: str,
    ) -> tuple[str, str]:
        """Heal provider/profile/model mismatches (anthropic↔openai, cloud↔local)."""
        compatible_profile_ids = [
            profile_id
            for profile_id, profile in profiles.items()
            if str(profile.get("backend") or "").strip().lower() != "openai"
        ]
        # Heal provider says Anthropic but model clearly targets another backend.
        if (
            provider_raw == "anthropic"
            and configured_model
            and not cls._looks_like_anthropic_model(configured_model)
        ):
            from agent.model_catalog import catalog_provider_for_model

            catalog_provider = catalog_provider_for_model(configured_model)
            if catalog_provider and catalog_provider != "openai":
                data["llm.provider"] = catalog_provider
                provider_raw = catalog_provider
            elif compatible_profile_ids:
                data["llm.provider"] = "openai"
                provider_raw = "openai"
                if active_profile == "openai_cloud":
                    model_match_profile = None
                    for profile_id in compatible_profile_ids:
                        model_hint = str(
                            (profiles.get(profile_id) or {}).get("default_model") or ""
                        ).strip()
                        if model_hint == configured_model:
                            model_match_profile = profile_id
                            break
                    active_profile = model_match_profile or compatible_profile_ids[0]

        # Heal first-party cloud catalog mismatches (e.g. Gemini under openai).
        if configured_model:
            from agent.model_catalog import catalog_provider_for_model

            catalog_provider = catalog_provider_for_model(configured_model)
            if catalog_provider and provider_raw != catalog_provider:
                data["llm.provider"] = catalog_provider
                provider_raw = catalog_provider
                if catalog_provider == "openai":
                    active_profile_candidate = profiles.get(active_profile) or {}
                    active_backend_candidate = str(
                        active_profile_candidate.get("backend") or ""
                    ).strip().lower()
                    if (
                        active_profile not in profiles
                        or active_backend_candidate in _LOCAL_COMPATIBLE_BACKENDS
                    ) and cls._looks_like_openai_cloud_model(configured_model):
                        active_profile = "openai_cloud"

        # Heal cloud-model/local-backend mismatch (e.g. GPT-5 + Ollama endpoint).
        active_profile_data = profiles.get(active_profile) if isinstance(profiles, dict) else None
        active_backend = str((active_profile_data or {}).get("backend") or "").strip().lower()
        if (
            provider_raw == "openai"
            and active_backend in _LOCAL_COMPATIBLE_BACKENDS
            and cls._looks_like_openai_cloud_model(configured_model)
        ):
            fallback_model = (
                str((active_profile_data or {}).get("default_model") or "").strip()
                or str(
                    OPENAI_PROFILE_DEFAULTS.get(active_backend, OPENAI_PROFILE_DEFAULTS["other"]).get(
                        "default_model"
                    )
                    or "llama3.1"
                ).strip()
            )
            if fallback_model and fallback_model != configured_model:
                data["llm.model"] = fallback_model

        return provider_raw, active_profile
