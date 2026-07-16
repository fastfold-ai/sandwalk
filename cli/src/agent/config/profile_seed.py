"""Seed the profiles dict from raw config data and migrate the legacy single slot."""

from typing import Any

from .constants import OPENAI_PROFILE_BACKENDS
from .providers import OPENAI_PROFILE_DEFAULTS


class ProfileSeedMixin:
    """First phase of ``_ensure_openai_profiles_data``: build + legacy migration."""

    @classmethod
    def _seed_profiles_and_legacy_fields(
        cls, data: dict[str, Any]
    ) -> tuple[dict[str, dict[str, Any]], str | None, str, str | None]:
        """Build the profiles dict (with a cloud profile) and read legacy fields."""
        profiles: dict[str, dict[str, Any]] = {}
        raw_profiles = data.get("llm.openai_profiles")
        if isinstance(raw_profiles, dict):
            for raw_profile_id, raw_profile in raw_profiles.items():
                profile_id = cls._slugify_profile_id(raw_profile_id)
                profile_id = cls._unique_profile_id(profile_id, profiles)
                profiles[profile_id] = cls._normalize_profile_record(profile_id, raw_profile)

        # Always keep a cloud profile available.
        if "openai_cloud" not in profiles:
            profiles["openai_cloud"] = cls._normalize_profile_record(
                "openai_cloud",
                {
                    "label": "OpenAI Cloud",
                    "backend": "openai",
                    "base_url": OPENAI_PROFILE_DEFAULTS["openai"]["base_url"],
                    "api_key": cls._normalized_secret(data.get("llm.openai_api_key")),
                    "default_model": OPENAI_PROFILE_DEFAULTS["openai"]["default_model"],
                    "discovery": OPENAI_PROFILE_DEFAULTS["openai"]["discovery"],
                },
            )
        else:
            openai_key = cls._normalized_secret(data.get("llm.openai_api_key"))
            if openai_key and not profiles["openai_cloud"].get("api_key"):
                profiles["openai_cloud"]["api_key"] = openai_key

        legacy_base_url = cls._normalize_openai_base_url(data.get("llm.openai_base_url"))
        legacy_backend = cls._normalize_compatible_backend_name(
            data.get("llm.openai_compatible_backend")
        )
        legacy_key = cls._normalized_secret(data.get("llm.openai_compatible_api_key"))
        if legacy_backend not in OPENAI_PROFILE_BACKENDS:
            legacy_backend = cls.infer_openai_compatible_backend(legacy_base_url, legacy_key)
        return profiles, legacy_base_url, legacy_backend, legacy_key

    @classmethod
    def _migrate_legacy_into_profile(
        cls,
        data: dict[str, Any],
        profiles: dict[str, dict[str, Any]],
        legacy_base_url: str | None,
        legacy_backend: str,
        legacy_key: str | None,
    ) -> None:
        """Migrate the legacy single-slot compatible config into a profile."""
        profile_match_id = None
        for existing_id, existing_profile in profiles.items():
            existing_url = cls._normalize_openai_base_url(existing_profile.get("base_url"))
            if existing_profile.get("backend") != "openai" and existing_url == legacy_base_url:
                profile_match_id = existing_id
                break
        if not profile_match_id:
            base_candidate = f"{legacy_backend or 'compatible'}_profile"
            profile_match_id = cls._unique_profile_id(base_candidate, profiles)
            profiles[profile_match_id] = cls._normalize_profile_record(
                profile_match_id,
                {
                    "label": str(
                        OPENAI_PROFILE_DEFAULTS.get(legacy_backend, OPENAI_PROFILE_DEFAULTS["other"]).get("label")
                        or "Compatible Endpoint"
                    ),
                    "backend": legacy_backend,
                    "base_url": legacy_base_url,
                    "api_key": legacy_key,
                    "default_model": data.get("llm.model"),
                },
            )
        else:
            updated = dict(profiles[profile_match_id])
            if legacy_backend and legacy_backend in OPENAI_PROFILE_BACKENDS:
                updated["backend"] = legacy_backend
            if legacy_key:
                updated["api_key"] = legacy_key
            updated["base_url"] = legacy_base_url
            profiles[profile_match_id] = cls._normalize_profile_record(profile_match_id, updated)
        if "llm.openai_active_profile" not in data and str(data.get("llm.provider") or "").strip().lower() == "openai":
            data["llm.openai_active_profile"] = profile_match_id
