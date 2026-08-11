"""Runtime settings shared by terminal and web presentation layers.

Split package — re-exports the public surface previously defined in
``agent_server/settings_service.py`` so existing imports keep working.
"""

from __future__ import annotations

from agent.config import Config, sync_process_env_from_config
from agent_server.models import (
    OnboardingSettings,
    RuntimeSettings,
    UpdateOnboardingSettingsRequest,
    UpdateRuntimeSettingsRequest,
)
from agent_server.settings_service.onboarding import (
    apply_onboarding_update,
    get_onboarding_settings,
)
from agent_server.settings_service.runtime_get import get_runtime_settings
from agent_server.settings_service.runtime_update_model import (
    apply_model_update,
    apply_provider_updates,
)
from agent_server.settings_service.runtime_update_numeric import apply_numeric_updates
from agent_server.settings_service.runtime_update_reasoning import apply_reasoning_update


class SettingsService:
    @staticmethod
    def get() -> RuntimeSettings:
        return get_runtime_settings(Config.load())

    @staticmethod
    def update(payload: UpdateRuntimeSettingsRequest) -> RuntimeSettings:
        config = Config.load()
        # Apply everything except the model first. The model is set last so that
        # activating the OpenAI cloud profile (in apply_model_update) — which runs
        # the config auto-heal — cannot clobber a freshly-selected cloud model.
        apply_provider_updates(config, payload)
        apply_reasoning_update(config, payload)
        apply_numeric_updates(config, payload)
        apply_model_update(config, payload)

        config.save()
        # Keep process env aligned for settings-backed vars (do not clobber
        # unrelated shell-exported API keys).
        sync_process_env_from_config(
            config,
            only_missing=False,
            config_keys=[
                "llm.openai_base_url",
                "llm.openai_api_key",
                "llm.provider",
                "llm.model",
                "data.base",
            ],
        )
        return SettingsService.get()

    @staticmethod
    def get_onboarding() -> OnboardingSettings:
        return get_onboarding_settings(Config.load())

    @staticmethod
    def update_onboarding(payload: UpdateOnboardingSettingsRequest) -> OnboardingSettings:
        config = Config.load()
        apply_onboarding_update(config, payload)
        config.save()
        return SettingsService.get_onboarding()


__all__ = ["SettingsService"]
