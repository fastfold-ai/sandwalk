"""Update/remove/validate mixin for ``IntegrationsService``."""

from __future__ import annotations

import os

from agent.config import Config, sync_process_env_from_config, unset_process_env_for_config_keys
from agent_server.models import IntegrationProvider, ValidateIntegrationResponse


class MutateMixin:
    def update(self, key: str, values: dict[str, str]) -> IntegrationProvider:
        entries = self._providers.get(key)
        if entries is None:
            raise KeyError(key)
        by_env = {str(info["env_var"]): config_key for config_key, info in entries}
        normalized = {
            env_name: str(value).strip()
            for env_name, value in values.items()
            if env_name in by_env and str(value).strip()
        }
        if not normalized:
            raise ValueError("At least one integration value is required.")
        with self._lock:
            config = Config.load()
            for env_name, value in normalized.items():
                config.set(by_env[env_name], value)
                # Force into process env so web runs/PTY match CLI immediately.
                os.environ[env_name] = value
            config.save()
            sync_process_env_from_config(config)
        return self._provider(key, entries)

    def remove(self, key: str) -> IntegrationProvider:
        entries = self._providers.get(key)
        if entries is None:
            raise KeyError(key)
        with self._lock:
            config = Config.load()
            removed_keys = [config_key for config_key, _ in entries]
            for config_key, _ in entries:
                config.unset(config_key)
            config.save()
            unset_process_env_for_config_keys(removed_keys)
        return self._provider(key, entries)

    def validate(self, key: str) -> ValidateIntegrationResponse:
        provider = self.get(key)
        if provider is None:
            raise KeyError(key)
        return ValidateIntegrationResponse(
            ok=provider.configured,
            configured=provider.configured,
            source=provider.source,
            message=(
                f"{provider.name} is configured."
                if provider.configured
                else f"{provider.name} is not configured."
            ),
        )
