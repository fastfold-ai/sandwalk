"""``Config.set`` / ``Config.unset`` mutators."""

import json
from typing import Any

from .defaults import AGENT_PROFILE_PRESETS, DEFAULTS
from .providers import OPENAI_PROFILE_DEFAULTS


class CoreMutateMixin:
    """Key mutation with type coercion, profile-aware side effects, and unset."""

    def set(self, key: str, value: Any):
        """Set a config value."""
        if key == "agent.profile":
            profile = str(value).strip().lower()
            if profile not in AGENT_PROFILE_PRESETS:
                valid = ", ".join(sorted(AGENT_PROFILE_PRESETS.keys()))
                raise ValueError(
                    f"Invalid agent.profile '{value}'. Valid profiles: {valid}"
                )
            for preset_key, preset_val in AGENT_PROFILE_PRESETS[profile].items():
                self._data[preset_key] = preset_val
            self._data["agent.profile"] = profile
            return

        if key == "llm.openai_active_profile":
            self.set_openai_active_profile(str(value or ""))
            return

        if key == "llm.openai_default_profile":
            self.set_openai_default_profile(str(value or ""))
            return

        if key == "llm.openai_profiles":
            parsed_value = value
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    try:
                        parsed_value = json.loads(stripped)
                    except Exception as exc:
                        raise ValueError("llm.openai_profiles must be valid JSON object.") from exc
            if not isinstance(parsed_value, dict):
                raise ValueError("llm.openai_profiles must be a JSON object.")
            self._data[key] = parsed_value
            self._dirty_keys.add(key)
            self._unset_keys.discard(key)
            self._sync_openai_profile_projection(apply_legacy_compat=False)
            return

        # Type coercion
        if key in DEFAULTS and DEFAULTS[key] is not None:
            expected_type = type(DEFAULTS[key])
            if expected_type is bool:
                value = value.lower() in ("true", "1", "yes") if isinstance(value, str) else bool(value)
            elif expected_type is float:
                value = float(value)
            elif expected_type is int:
                value = int(value)

        if key in {
            "llm.anthropic_api_key",
            "llm.api_key",
            "llm.openai_api_key",
            "llm.openai_compatible_api_key",
        }:
            value = self._normalized_secret(value)
            issue = self.validate_llm_api_key(
                key,
                value,
                openai_base_url=self.get("llm.openai_base_url"),
            )
            if issue:
                raise ValueError(issue)

        if key in {
            "llm.openai_base_url",
            "llm.openai_compatible_backend",
            "llm.openai_compatible_api_key",
        }:
            if key == "llm.openai_base_url":
                value = self._normalize_openai_base_url(value)
            elif key == "llm.openai_compatible_backend":
                value = self._normalize_compatible_backend_name(value) or None
            self._data[key] = value
            self._dirty_keys.add(key)
            self._unset_keys.discard(key)
            self._sync_openai_profile_projection(apply_legacy_compat=True)
            return

        self._data[key] = value
        self._dirty_keys.add(key)
        self._unset_keys.discard(key)

        if key == "llm.openai_api_key":
            profiles, _, _ = self._ensure_openai_profiles_data(self._data)
            cloud = dict(profiles.get("openai_cloud") or {})
            cloud["backend"] = "openai"
            cloud["label"] = cloud.get("label") or OPENAI_PROFILE_DEFAULTS["openai"]["label"]
            cloud["base_url"] = cloud.get("base_url") or OPENAI_PROFILE_DEFAULTS["openai"]["base_url"]
            cloud["api_key"] = self._normalized_secret(value)
            profiles["openai_cloud"] = self._normalize_profile_record("openai_cloud", cloud)
            self._data["llm.openai_profiles"] = profiles
            self._sync_openai_profile_projection(apply_legacy_compat=False)

    def unset(self, key: str) -> None:
        """Remove a config key override, falling back to defaults/env."""
        if key in {"llm.openai_active_profile", "llm.openai_default_profile", "llm.openai_profiles"}:
            if key == "llm.openai_profiles":
                self._data.pop("llm.openai_profiles", None)
                self._data.pop("llm.openai_active_profile", None)
                self._data.pop("llm.openai_default_profile", None)
            else:
                self._data.pop(key, None)
            self._dirty_keys.discard("llm.openai_profiles")
            self._dirty_keys.discard("llm.openai_active_profile")
            self._dirty_keys.discard("llm.openai_default_profile")
            self._unset_keys.update(
                {
                    "llm.openai_profiles",
                    "llm.openai_active_profile",
                    "llm.openai_default_profile",
                }
            )
            self._ensure_openai_profiles_data(self._data)
            self._sync_openai_profile_projection(apply_legacy_compat=False)
            return

        if key in {
            "llm.openai_base_url",
            "llm.openai_compatible_backend",
            "llm.openai_compatible_api_key",
        }:
            self._data.pop(key, None)
            self._dirty_keys.discard(key)
            self._unset_keys.add(key)
            self._sync_openai_profile_projection(apply_legacy_compat=True)
            return

        if key == "llm.openai_api_key":
            profiles, _, _ = self._ensure_openai_profiles_data(self._data)
            cloud = dict(profiles.get("openai_cloud") or {})
            cloud["api_key"] = None
            profiles["openai_cloud"] = self._normalize_profile_record("openai_cloud", cloud)
            self._data["llm.openai_profiles"] = profiles

        self._data.pop(key, None)
        self._dirty_keys.discard(key)
        self._unset_keys.add(key)
