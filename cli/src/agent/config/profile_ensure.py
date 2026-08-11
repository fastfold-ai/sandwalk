"""Orchestrate profile schema normalization and legacy-field projection."""

from typing import Any


class ProfileEnsureMixin:
    """Ties together seed/bootstrap/heal phases and projects the active profile."""

    @classmethod
    def _ensure_openai_profiles_data(
        cls,
        data: dict[str, Any],
        *,
        apply_legacy_compat: bool = True,
    ) -> tuple[dict[str, dict[str, Any]], str, str]:
        """Ensure profile schema exists and migrate legacy OpenAI-compatible fields."""
        profiles, legacy_base_url, legacy_backend, legacy_key = cls._seed_profiles_and_legacy_fields(data)

        if apply_legacy_compat and legacy_base_url and not cls._is_openai_managed_base_url(legacy_base_url):
            cls._migrate_legacy_into_profile(data, profiles, legacy_base_url, legacy_backend, legacy_key)

        configured_model, provider_raw = cls._bootstrap_compatible_profile(
            data, profiles, apply_legacy_compat, legacy_backend, legacy_key
        )

        default_profile, active_profile = cls._resolve_profile_ids(data, profiles, legacy_base_url)

        provider_raw, active_profile = cls._heal_profile_mismatches(
            data, profiles, provider_raw, configured_model, active_profile
        )

        data["llm.openai_profiles"] = profiles
        data["llm.openai_active_profile"] = active_profile
        data["llm.openai_default_profile"] = default_profile

        cls._project_active_profile_to_legacy_data(data)
        return profiles, active_profile, default_profile

    @classmethod
    def _project_active_profile_to_legacy_data(cls, data: dict[str, Any]) -> None:
        """Mirror the active OpenAI profile back into legacy flat keys."""
        profiles = data.get("llm.openai_profiles")
        if not isinstance(profiles, dict):
            return
        active_profile_id = str(data.get("llm.openai_active_profile") or "").strip()
        active = profiles.get(active_profile_id)
        if not isinstance(active, dict):
            return

        backend = cls._normalize_compatible_backend_name(active.get("backend"))
        base_url = cls._normalize_openai_base_url(active.get("base_url"))
        api_key = cls._normalized_secret(active.get("api_key"))

        if backend == "openai":
            data["llm.openai_base_url"] = None
            data["llm.openai_compatible_backend"] = None
            if api_key and "llm.openai_api_key" not in data:
                data["llm.openai_api_key"] = api_key
        else:
            data["llm.openai_base_url"] = base_url
            data["llm.openai_compatible_backend"] = backend or "other"
            # Keys stay on the active profile only — never mirror into the
            # retired global llm.openai_compatible_api_key / env slot.
            data["llm.openai_compatible_api_key"] = None

    def _sync_openai_profile_projection(self, *, apply_legacy_compat: bool = True) -> None:
        """Refresh legacy OpenAI-compatible fields after profile updates."""
        self._ensure_openai_profiles_data(
            self._data,
            apply_legacy_compat=apply_legacy_compat,
        )
        self._dirty_keys.update(
            {
                "llm.openai_profiles",
                "llm.openai_active_profile",
                "llm.openai_default_profile",
                "llm.openai_api_key",
                "llm.openai_base_url",
                "llm.openai_compatible_backend",
                "llm.openai_compatible_api_key",
            }
        )
        self._unset_keys.difference_update(
            {
                "llm.openai_profiles",
                "llm.openai_active_profile",
                "llm.openai_default_profile",
                "llm.openai_api_key",
                "llm.openai_base_url",
                "llm.openai_compatible_backend",
                "llm.openai_compatible_api_key",
            }
        )
