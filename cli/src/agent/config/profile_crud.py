"""Public CRUD API for OpenAI / OpenAI-compatible profiles."""

from typing import Any

from .constants import _UNSET


class ProfileCrudMixin:
    """Public profile accessors and mutators exposed on ``Config``."""

    def openai_profiles(self, *, include_cloud: bool = True) -> dict[str, dict[str, Any]]:
        """Return configured OpenAI/OpenAI-compatible profiles."""
        profiles, _, _ = self._ensure_openai_profiles_data(self._data)
        if include_cloud:
            return {profile_id: dict(profile) for profile_id, profile in profiles.items()}
        return {
            profile_id: dict(profile)
            for profile_id, profile in profiles.items()
            if str(profile.get("backend") or "").strip().lower() != "openai"
        }

    def active_openai_profile_id(self) -> str:
        """Return active OpenAI profile id."""
        _, active_profile_id, _ = self._ensure_openai_profiles_data(self._data)
        return active_profile_id

    def compatible_openai_profile_ids(self) -> list[str]:
        """Return configured non-cloud OpenAI-compatible profile ids."""
        profiles = self.openai_profiles(include_cloud=False)
        return sorted(profiles.keys())

    def default_openai_profile_id(self) -> str:
        """Return default OpenAI profile id."""
        _, _, default_profile_id = self._ensure_openai_profiles_data(self._data)
        return default_profile_id

    def get_openai_profile(self, profile_id: str | None = None) -> dict[str, Any] | None:
        """Return an OpenAI profile by id (or active profile when omitted)."""
        profiles, active_profile_id, _ = self._ensure_openai_profiles_data(self._data)
        selected_profile_id = self._slugify_profile_id(profile_id or active_profile_id)
        profile = profiles.get(selected_profile_id)
        if not profile:
            return None
        return {"id": selected_profile_id, **dict(profile)}

    def set_openai_active_profile(self, profile_id: str) -> None:
        """Set active OpenAI profile and sync legacy projection fields.

        Active profile is written before ``_ensure_openai_profiles_data`` so the
        cloud-model/local-backend heal does not rewrite an intentionally selected
        cloud model (e.g. ``gpt-5.6-sol``) back to the local profile default
        while we are switching away from Ollama/oMLX.
        """
        selected_profile_id = self._slugify_profile_id(profile_id)
        profiles = self._data.get("llm.openai_profiles")
        if not isinstance(profiles, dict) or selected_profile_id not in profiles:
            profiles, _, _ = self._ensure_openai_profiles_data(
                self._data,
                apply_legacy_compat=False,
            )
        if selected_profile_id not in profiles:
            raise ValueError(f"Unknown OpenAI profile '{profile_id}'.")
        self._data["llm.openai_active_profile"] = selected_profile_id
        self._sync_openai_profile_projection(apply_legacy_compat=False)

    def set_openai_default_profile(self, profile_id: str) -> None:
        """Set default OpenAI profile used for future selections."""
        profiles, _, _ = self._ensure_openai_profiles_data(self._data)
        selected_profile_id = self._slugify_profile_id(profile_id)
        if selected_profile_id not in profiles:
            raise ValueError(f"Unknown OpenAI profile '{profile_id}'.")
        self._data["llm.openai_default_profile"] = selected_profile_id
        self._sync_openai_profile_projection(apply_legacy_compat=False)

    def upsert_openai_profile(
        self,
        *,
        profile_id: str | None = None,
        label: str | None = None,
        backend: str | None = None,
        base_url: str | None = None,
        api_key: Any = _UNSET,
        default_model: str | None = None,
        discovery: list[str] | None = None,
        set_active: bool = False,
        set_default: bool = False,
    ) -> str:
        """Create or update an OpenAI profile and return its profile id."""
        from .constants import OPENAI_PROFILE_BACKENDS

        profiles, active_profile_id, default_profile_id = self._ensure_openai_profiles_data(self._data)
        requested_backend = str(backend or "").strip().lower()
        if requested_backend and requested_backend not in OPENAI_PROFILE_BACKENDS:
            raise ValueError(f"Unsupported OpenAI profile backend '{backend}'.")

        if profile_id:
            resolved_profile_id = self._slugify_profile_id(profile_id)
            existing = dict(profiles.get(resolved_profile_id) or {})
        else:
            inferred_backend = requested_backend or "other"
            base_candidate = label or f"{inferred_backend}_profile"
            resolved_profile_id = self._unique_profile_id(base_candidate, profiles)
            existing = {}

        payload = dict(existing)
        if requested_backend:
            payload["backend"] = requested_backend
        if label is not None:
            payload["label"] = str(label).strip()
        if base_url is not None:
            payload["base_url"] = base_url
        if default_model is not None:
            payload["default_model"] = str(default_model).strip()
        if discovery is not None:
            payload["discovery"] = list(discovery)
        if api_key is not _UNSET:
            payload["api_key"] = self._normalized_secret(api_key)

        if not payload.get("backend"):
            payload["backend"] = self.infer_openai_compatible_backend(
                payload.get("base_url"),
                payload.get("api_key"),
            )

        normalized = self._normalize_profile_record(resolved_profile_id, payload)
        profiles[resolved_profile_id] = normalized
        self._data["llm.openai_profiles"] = profiles

        if set_default:
            self._data["llm.openai_default_profile"] = resolved_profile_id
        elif default_profile_id not in profiles:
            self._data["llm.openai_default_profile"] = resolved_profile_id

        if set_active:
            self._data["llm.openai_active_profile"] = resolved_profile_id
        elif active_profile_id not in profiles:
            self._data["llm.openai_active_profile"] = resolved_profile_id

        self._sync_openai_profile_projection(apply_legacy_compat=False)
        return resolved_profile_id

    def remove_openai_profile(self, profile_id: str) -> bool:
        """Remove an OpenAI-compatible profile (cloud profile is protected)."""
        profiles, active_profile_id, default_profile_id = self._ensure_openai_profiles_data(self._data)
        selected_profile_id = self._slugify_profile_id(profile_id)
        if selected_profile_id == "openai_cloud":
            return False
        if selected_profile_id not in profiles:
            return False
        profiles.pop(selected_profile_id, None)
        self._data["llm.openai_profiles"] = profiles
        if self._slugify_profile_id(active_profile_id) == selected_profile_id:
            self._data["llm.openai_active_profile"] = self._slugify_profile_id(default_profile_id or "openai_cloud")
        if self._slugify_profile_id(default_profile_id) == selected_profile_id:
            self._data["llm.openai_default_profile"] = "openai_cloud"
        self._sync_openai_profile_projection(apply_legacy_compat=False)
        return True
