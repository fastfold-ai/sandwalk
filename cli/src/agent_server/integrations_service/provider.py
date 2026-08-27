"""Provider construction, listing, and lookup mixin for ``IntegrationsService``."""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime

from agent.config import API_KEYS, Config
from agent_server.integrations_service.capabilities import (
    find_boltz_cli,
    find_npx_skills_cli,
)
from agent_server.integrations_service.metadata import (
    KEY_ALIASES,
    PROVIDER_METADATA,
    category_for,
)
from agent_server.models import IntegrationField, IntegrationProvider, IntegrationUnlock


def _env_secret(info: dict) -> str:
    """Read the secret from the primary env var or any aliases."""
    names = [str(info.get("env_var") or "").strip()]
    aliases = str(info.get("env_var_aliases") or "").strip()
    if aliases:
        names.extend(part.strip() for part in aliases.replace(",", " ").split())
    for name in names:
        if not name:
            continue
        value = str(os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


class ProviderMixin:
    _lock: threading.RLock
    _providers: dict[str, list[tuple[str, dict]]]

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._providers = {}
        for config_key, info in API_KEYS.items():
            if info.get("ui") is False:
                continue
            key = str(
                info.get("provider_key")
                or KEY_ALIASES.get(config_key)
                or info["env_var"].lower().replace("_", "-")
            )
            self._providers.setdefault(key, []).append((config_key, info))

    @staticmethod
    def _masked(value: str, *, is_secret: bool = True) -> str | None:
        normalized = value.strip()
        if not normalized:
            return None
        if not is_secret:
            return normalized
        if len(normalized) <= 8:
            return "••••••••"
        return f"{normalized[:4]}…{normalized[-4:]}"

    @staticmethod
    def _updated_at(config: Config) -> dict[str, str]:
        value = config.get("integrations.updated_at")
        if not isinstance(value, dict):
            return {}
        return {
            str(config_key): str(timestamp)
            for config_key, timestamp in value.items()
            if str(timestamp).strip()
        }

    @classmethod
    def _mark_updated(cls, config: Config, config_keys: list[str]) -> None:
        timestamps = cls._updated_at(config)
        timestamp = datetime.now(UTC).isoformat()
        for config_key in config_keys:
            timestamps[config_key] = timestamp
        config.set("integrations.updated_at", timestamps)

    @classmethod
    def _clear_updated(cls, config: Config, config_keys: list[str]) -> None:
        timestamps = cls._updated_at(config)
        for config_key in config_keys:
            timestamps.pop(config_key, None)
        if timestamps:
            config.set("integrations.updated_at", timestamps)
            return
        config.unset("integrations.updated_at")

    def _provider(self, key: str, entries: list[tuple[str, dict]]) -> IntegrationProvider:
        config = Config.load()
        timestamps = self._updated_at(config)
        fields: list[IntegrationField] = []
        for config_key, info in entries:
            config_value = str(config.get(config_key) or "").strip()
            env_value = _env_secret(info)
            # Prefer config over process env (long-lived agent-server can hold
            # stale QWEN/DASHSCOPE vars after a key rotate).
            value = config_value or env_value
            source = (
                "config"
                if config_value
                else "environment"
                if env_value
                else "none"
            )
            fields.append(
                IntegrationField(
                    env_var=str(info["env_var"]),
                    label=str(info["name"]),
                    is_secret=bool(info.get("secret", True)),
                    configured=bool(value),
                    source=source,
                    masked_preview=self._masked(
                        value,
                        is_secret=bool(info.get("secret", True)),
                    ),
                    updated_at=timestamps.get(config_key),
                )
            )

        first_config_key, first_info = entries[0]
        metadata = PROVIDER_METADATA.get(key, {})
        unlocks = [
            IntegrationUnlock.model_validate(unlock)
            for unlock in list(metadata.get("unlocks") or [])
        ]
        if key == "boltz":
            cli_path = find_boltz_cli()
            unlocks = [
                unlock.model_copy(
                    update={
                        "installed": cli_path is not None,
                        "status_detail": str(cli_path) if cli_path else None,
                    }
                )
                if unlock.id == "boltz-api-cli"
                else unlock
                for unlock in unlocks
            ]
        if key == "skills-sh":
            cli_path = find_npx_skills_cli()
            unlocks = [
                unlock.model_copy(
                    update={
                        "installed": cli_path is not None,
                        "status_detail": str(cli_path) if cli_path else None,
                    }
                )
                if unlock.id == "npx-skills-cli"
                else unlock
                for unlock in unlocks
            ]
        configured_fields = [field for field in fields if field.configured]
        # Endpoint / non-secret companions must not mark the provider "connected".
        secret_configured = [field for field in configured_fields if field.is_secret]
        profile_configured = any(
            field.env_var == "AWS_PROFILE" and field.configured for field in fields
        )
        bedrock_verified = bool(config.get("llm.bedrock_verified")) if key == "bedrock" else False
        if key == "fastfold-cloud":
            # Slack Relay Agent needs the FastFold key — surface that on the unlock.
            key_ready = bool(secret_configured or configured_fields)
            unlocks = [
                unlock.model_copy(
                    update={
                        "installed": key_ready,
                        "status_detail": (
                            None
                            if key_ready
                            else "Save a FastFold API key to enable Slack relay."
                        ),
                    }
                )
                if unlock.id == "slack-relay-agent"
                else unlock
                for unlock in unlocks
            ]
        primary = (
            secret_configured[0]
            if secret_configured
            else configured_fields[0]
            if configured_fields
            else fields[0]
        )
        secret_field = next((field for field in fields if field.is_secret), fields[0])
        return IntegrationProvider(
            key=key,
            name=str(metadata.get("name") or first_info["name"]),
            category=str(metadata.get("category") or category_for(first_config_key)),
            description=str(metadata.get("description") or first_info["description"]),
            env_var=secret_field.env_var,
            configured=(
                bool(secret_configured)
                or (key == "bedrock" and (profile_configured or bedrock_verified))
            ),
            source=primary.source,
            masked_preview=primary.masked_preview,
            setup_url=str(first_info.get("url") or "") or None,
            free=all(bool(info.get("free")) for _, info in entries),
            fields=fields,
            unlocks=unlocks,
        )

    def list(self) -> list[IntegrationProvider]:
        return sorted(
            (
                self._provider(key, entries)
                for key, entries in self._providers.items()
            ),
            key=lambda provider: (provider.category, provider.name.lower()),
        )

    def get(self, key: str) -> IntegrationProvider | None:
        entries = self._providers.get(key)
        return self._provider(key, entries) if entries else None
