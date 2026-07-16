"""Bootstrap a compatible profile from legacy hints and resolve default/active ids."""

from typing import Any

from .providers import OPENAI_PROFILE_DEFAULTS


class ProfileBootstrapMixin:
    """Second phase of ``_ensure_openai_profiles_data``: bootstrap + id resolution."""

    @classmethod
    def _bootstrap_compatible_profile(
        cls,
        data: dict[str, Any],
        profiles: dict[str, dict[str, Any]],
        apply_legacy_compat: bool,
        legacy_backend: str,
        legacy_key: str | None,
    ) -> tuple[str, str]:
        """Resolve the configured model/provider and bootstrap a profile if needed."""
        has_compatible_profiles = any(
            str(profile.get("backend") or "").strip().lower() != "openai"
            for profile in profiles.values()
        )
        configured_model = str(data.get("llm.model") or "").strip()
        try:
            from agent.model_catalog import resolve_catalog_model_id

            resolved_model = resolve_catalog_model_id(configured_model)
            if resolved_model and resolved_model != configured_model:
                data["llm.model"] = resolved_model
                configured_model = resolved_model
        except Exception:
            pass
        provider_raw = str(data.get("llm.provider") or "").strip().lower()
        if apply_legacy_compat and not has_compatible_profiles and legacy_key:
            bootstrap_backend = (
                legacy_backend
                if legacy_backend in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}
                else "other"
            )
            inferred_model_backend = cls._infer_backend_from_model_name(configured_model)
            if inferred_model_backend:
                bootstrap_backend = inferred_model_backend
            bootstrap_defaults = OPENAI_PROFILE_DEFAULTS.get(bootstrap_backend, OPENAI_PROFILE_DEFAULTS["other"])
            bootstrap_id = cls._unique_profile_id(f"{bootstrap_backend}_legacy", profiles)
            profiles[bootstrap_id] = cls._normalize_profile_record(
                bootstrap_id,
                {
                    "label": str(bootstrap_defaults.get("label") or "Compatible Endpoint"),
                    "backend": bootstrap_backend,
                    "base_url": str(bootstrap_defaults.get("base_url") or "http://localhost:11434/v1"),
                    "api_key": legacy_key,
                    "default_model": configured_model,
                    "discovery": bootstrap_defaults.get("discovery"),
                },
            )
            if (
                "llm.openai_active_profile" not in data
                or provider_raw == "openai"
                or (configured_model and not cls._looks_like_anthropic_model(configured_model))
            ):
                data["llm.openai_active_profile"] = bootstrap_id
        return configured_model, provider_raw

    @classmethod
    def _resolve_profile_ids(
        cls,
        data: dict[str, Any],
        profiles: dict[str, dict[str, Any]],
        legacy_base_url: str | None,
    ) -> tuple[str, str]:
        """Resolve the default and active profile ids, healing stale references."""
        default_profile = cls._slugify_profile_id(str(data.get("llm.openai_default_profile") or "").strip())
        if default_profile not in profiles:
            default_profile = "openai_cloud"

        active_profile = cls._slugify_profile_id(str(data.get("llm.openai_active_profile") or "").strip())
        if active_profile not in profiles:
            active_profile = default_profile
            if legacy_base_url and not cls._is_openai_managed_base_url(legacy_base_url):
                for existing_id, existing_profile in profiles.items():
                    if cls._normalize_openai_base_url(existing_profile.get("base_url")) == legacy_base_url:
                        active_profile = existing_id
                        break
        return default_profile, active_profile
