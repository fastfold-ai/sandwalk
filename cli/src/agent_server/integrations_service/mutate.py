"""Update/remove/validate mixin for ``IntegrationsService``."""

from __future__ import annotations

import os

import httpx

from agent.config import Config, sync_process_env_from_config, unset_process_env_for_config_keys
from agent.doctor.model_provider_http import probe_llm_api_key, supports_llm_key_probe
from agent_server.models import IntegrationProvider, ValidateIntegrationResponse

_PROBE_USER_AGENT = (
    "Mozilla/5.0 (compatible; Sandwalk/1.0; "
    "+https://github.com/fastfold-ai/sandwalk)"
)


def _probe_boltz_api_key(api_key: str) -> tuple[bool, str]:
    """Validate a Boltz key using its non-billable auth context endpoint."""
    try:
        response = httpx.get(
            "https://api.boltz.bio/compute/v1/auth/me",
            headers={
                "Accept": "application/json",
                "x-api-key": api_key,
                "User-Agent": _PROBE_USER_AGENT,
            },
            timeout=15.0,
            follow_redirects=True,
        )
    except Exception as exc:
        return False, f"Couldn't reach Boltz ({exc.__class__.__name__})."

    if response.status_code < 300:
        return True, "Boltz API key works."
    if response.status_code in (401, 403):
        return False, "Invalid API key."
    return False, f"Boltz returned HTTP {response.status_code}."


def _probe_fastfold_api_key(api_key: str) -> tuple[bool, str]:
    """Validate a Fastfold Cloud key via the dual-auth /users/me endpoint."""
    try:
        response = httpx.get(
            "https://api.fastfold.ai/v1/users/me",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": _PROBE_USER_AGENT,
            },
            timeout=15.0,
            follow_redirects=True,
        )
    except Exception as exc:
        return False, f"Couldn't reach Fastfold Cloud ({exc.__class__.__name__})."

    if response.status_code < 300:
        return True, "Fastfold Cloud API key works."
    if response.status_code in (401, 403):
        return False, "Invalid API key."
    return False, f"Fastfold Cloud returned HTTP {response.status_code}."


def _probe_vercel_skills_token(token: str) -> tuple[bool, str]:
    """Validate a Vercel OIDC token against the skills.sh search API."""
    try:
        response = httpx.get(
            "https://skills.sh/api/v1/skills/search",
            params={"q": "fold", "limit": 1},
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": _PROBE_USER_AGENT,
            },
            timeout=15.0,
            follow_redirects=True,
        )
    except Exception as exc:
        return False, f"Couldn't reach skills.sh ({exc.__class__.__name__})."

    if response.status_code < 300:
        return True, "Vercel OIDC token works with skills.sh."
    if response.status_code in (401, 403):
        return False, "Invalid or expired Vercel OIDC token."
    return False, f"skills.sh returned HTTP {response.status_code}."


class MutateMixin:
    def update(self, key: str, values: dict[str, str]) -> IntegrationProvider:
        entries = self._providers.get(key)
        if entries is None:
            raise KeyError(key)
        by_env = {
            str(info["env_var"]): (config_key, info) for config_key, info in entries
        }
        sets: dict[str, str] = {}
        clears: list[str] = []
        for env_name, value in values.items():
            entry = by_env.get(env_name)
            if entry is None:
                continue
            config_key, info = entry
            text = str(value).strip()
            if text:
                sets[env_name] = text
                continue
            # Explicit blank clears non-secret fields (e.g. Qwen endpoint = Auto).
            if not bool(info.get("secret", True)):
                clears.append(env_name)
        if not sets and not clears:
            raise ValueError("At least one integration value is required.")
        with self._lock:
            config = Config.load()
            touched = []
            for env_name, value in sets.items():
                config_key, info = by_env[env_name]
                stored = value
                if config_key == "llm.qwen_base_url":
                    from agent.config import normalize_qwen_base_url

                    stored = normalize_qwen_base_url(value)
                config.set(config_key, stored)
                # Force-overwrite primary + aliases so a stale process env
                # (e.g. old DASHSCOPE_API_KEY) cannot outrank the saved key.
                from agent.config.env_sync import _env_names_for_info

                for name in _env_names_for_info(info) or [env_name]:
                    os.environ[name] = stored
                touched.append(config_key)
            for env_name in clears:
                config_key, info = by_env[env_name]
                config.unset(config_key)
                from agent.config.env_sync import _env_names_for_info

                for name in _env_names_for_info(info) or [env_name]:
                    os.environ.pop(name, None)
                touched.append(config_key)
            self._mark_updated(config, touched)
            config.save()
            sync_process_env_from_config(config)
            if clears:
                unset_process_env_for_config_keys(
                    [by_env[env_name][0] for env_name in clears]
                )
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
            self._clear_updated(config, removed_keys)
            # Not set up ⇒ that provider's models must be off in the list.
            from agent_server.models_service.mutate import disable_models_for_provider

            disable_models_for_provider(config, key)
            config.save()
            unset_process_env_for_config_keys(removed_keys)
        return self._provider(key, entries)

    def _secret_value(self, key: str) -> str:
        """Return the stored/env secret for an integration (empty if unset).

        Prefer config.json over process env. The agent-server is long-lived, so
        a stale ``QWEN_API_KEY`` / ``DASHSCOPE_API_KEY`` in ``os.environ`` can
        otherwise outrank a freshly saved key and fail Test.
        """
        entries = self._providers.get(key)
        if not entries:
            return ""
        config = Config.load()
        for config_key, info in entries:
            if not bool(info.get("secret", True)):
                continue
            config_value = str(config.get(config_key) or "").strip()
            if config_value:
                return config_value
            from agent_server.integrations_service.provider import _env_secret

            env_value = _env_secret(info)
            if env_value:
                return env_value
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

        # LLM providers: 1-token chat probe (GET /models is not trusted).
        if supports_llm_key_probe(key):
            result = probe_llm_api_key(
                key,
                self._secret_value(key),
                label=provider.name,
            )
            # Persist discovered host only when the user left endpoint on Auto.
            if key == "qwen" and result.base_url:
                with self._lock:
                    config = Config.load()
                    if not str(config.get("llm.qwen_base_url") or "").strip():
                        config.set("llm.qwen_base_url", result.base_url)
                        config.save()
            return ValidateIntegrationResponse(
                ok=result.ok,
                configured=True,
                source=provider.source,
                message=result.message,
            )

        if key == "boltz":
            ok, message = _probe_boltz_api_key(self._secret_value(key))
            return ValidateIntegrationResponse(
                ok=ok,
                configured=True,
                source=provider.source,
                message=message,
            )

        if key == "fastfold-cloud":
            ok, message = _probe_fastfold_api_key(self._secret_value(key))
            return ValidateIntegrationResponse(
                ok=ok,
                configured=True,
                source=provider.source,
                message=message,
            )

        if key == "skills-sh":
            ok, message = _probe_vercel_skills_token(self._secret_value(key))
            return ValidateIntegrationResponse(
                ok=ok,
                configured=True,
                source=provider.source,
                message=message,
            )

        return ValidateIntegrationResponse(
            ok=True,
            configured=True,
            source=provider.source,
            message=f"{provider.name} is configured.",
        )
