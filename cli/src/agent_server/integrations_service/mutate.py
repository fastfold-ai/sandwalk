"""Update/remove/validate mixin for ``IntegrationsService``."""

from __future__ import annotations

import os

from agent.config import Config, sync_process_env_from_config, unset_process_env_for_config_keys
from agent.doctor.model_provider_http import probe_llm_api_key, supports_llm_key_probe
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
            # Not set up ⇒ that provider's models must be off in the list.
            from agent_server.models_service.mutate import disable_models_for_provider

            disable_models_for_provider(config, key)
            config.save()
            unset_process_env_for_config_keys(removed_keys)
        return self._provider(key, entries)

    def _secret_value(self, key: str) -> str:
        """Return the stored/env secret for an integration (empty if unset)."""
        entries = self._providers.get(key)
        if not entries:
            return ""
        config = Config.load()
        for config_key, info in entries:
            if not bool(info.get("secret", True)):
                continue
            env_value = str(os.environ.get(info["env_var"]) or "").strip()
            if env_value:
                return env_value
            config_value = str(config.get(config_key) or "").strip()
            if config_value:
                return config_value
        return ""

    def validate(self, key: str) -> ValidateIntegrationResponse:
        """Live-check credentials. LLM keys hit GET /models."""
        provider = self.get(key)
        if provider is None:
            raise KeyError(key)
        if not provider.configured:
            return ValidateIntegrationResponse(
                ok=False,
                configured=False,
                source=provider.source,
                message=f"{provider.name} is not configured.",
            )

        # LLM providers: cheap GET /models probe (no completion / no tokens).
        if supports_llm_key_probe(key):
            result = probe_llm_api_key(
                key,
                self._secret_value(key),
                label=provider.name,
            )
            return ValidateIntegrationResponse(
                ok=result.ok,
                configured=True,
                source=provider.source,
                message=result.message,
            )

        return ValidateIntegrationResponse(
            ok=True,
            configured=True,
            source=provider.source,
            message=f"{provider.name} is configured.",
        )
