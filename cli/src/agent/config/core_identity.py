"""``Config.__init__`` / ``__repr__`` / ``get`` / ``validate``."""

from typing import Any

from .validation import _validate_config


class CoreIdentityMixin:
    """Instance construction, safe repr, plain getters, and schema validation."""

    def __init__(self, data: dict = None):
        self._data = data or {}
        self._ensure_openai_profiles_data(self._data)
        self._env_loaded_keys: set[str] = set()
        # Track mutations so save() only applies intentional changes.
        self._dirty_keys: set[str] = set(self._data.keys())
        self._unset_keys: set[str] = set()

    def __repr__(self) -> str:
        """Safe repr that masks API keys and secrets."""
        safe = {}
        for k, v in self._data.items():
            if k == "llm.openai_profiles" and isinstance(v, dict):
                masked_profiles: dict[str, Any] = {}
                for profile_id, profile in v.items():
                    if not isinstance(profile, dict):
                        masked_profiles[str(profile_id)] = profile
                        continue
                    profile_copy = dict(profile)
                    profile_secret = self._normalized_secret(profile_copy.get("api_key"))
                    if profile_secret:
                        profile_copy["api_key"] = (
                            profile_secret[:4] + "..." if len(profile_secret) > 4 else "***"
                        )
                    masked_profiles[str(profile_id)] = profile_copy
                safe[k] = masked_profiles
                continue
            if ("api_key" in k or "secret" in k or k.startswith("api.")) and v:
                safe[k] = str(v)[:4] + "..." if len(str(v)) > 4 else "***"
            else:
                safe[k] = v
        return f"Config({safe})"

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value, falling back to defaults."""
        from .defaults import DEFAULTS

        return self._data.get(key, DEFAULTS.get(key, default))

    def validate(self) -> list[str]:
        """Run schema validation on current config data. Returns list of issues."""
        return _validate_config(self._data)
