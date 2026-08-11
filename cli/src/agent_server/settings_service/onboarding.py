"""Onboarding progress settings (separate from runtime/model settings)."""

from __future__ import annotations

from agent.config import Config
from agent_server.models import OnboardingSettings, UpdateOnboardingSettingsRequest
from agent_server.settings_service.limits import ONBOARDING_MAX_STEP, bool_from_config, clamp_int


def get_onboarding_settings(config: Config) -> OnboardingSettings:
    return OnboardingSettings(
        completed=bool_from_config(config, "ui.onboarding_completed", False),
        step=clamp_int(
            config.get("ui.onboarding_step", 0),
            minimum=0,
            maximum=ONBOARDING_MAX_STEP,
            default=0,
        ),
    )


def apply_onboarding_update(config: Config, payload: UpdateOnboardingSettingsRequest) -> None:
    if payload.completed is not None:
        config.set("ui.onboarding_completed", bool(payload.completed))
    if payload.step is not None:
        config.set(
            "ui.onboarding_step",
            clamp_int(payload.step, minimum=0, maximum=ONBOARDING_MAX_STEP, default=0),
        )
