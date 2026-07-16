"""Provider construction, listing, and lookup mixin for ``IntegrationsService``."""

from __future__ import annotations

import os
import threading

from agent.config import API_KEYS, Config
from agent_server.integrations_service.metadata import (
    KEY_ALIASES,
    PROVIDER_METADATA,
    category_for,
)
from agent_server.models import IntegrationField, IntegrationProvider


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

    def _provider(self, key: str, entries: list[tuple[str, dict]]) -> IntegrationProvider:
        config = Config.load()
        fields: list[IntegrationField] = []
        for config_key, info in entries:
            env_value = str(os.environ.get(info["env_var"]) or "").strip()
            config_value = str(config.get(config_key) or "").strip()
            value = env_value or config_value
            source = "environment" if env_value else "config" if config_value else "none"
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
                )
            )

        first_config_key, first_info = entries[0]
        metadata = PROVIDER_METADATA.get(key, {})
        configured_fields = [field for field in fields if field.configured]
        primary = configured_fields[0] if configured_fields else fields[0]
        return IntegrationProvider(
            key=key,
            name=str(metadata.get("name") or first_info["name"]),
            category=str(metadata.get("category") or category_for(first_config_key)),
            description=str(metadata.get("description") or first_info["description"]),
            env_var=fields[0].env_var,
            configured=bool(configured_fields),
            source=primary.source,
            masked_preview=primary.masked_preview,
            setup_url=str(first_info.get("url") or "") or None,
            free=all(bool(info.get("free")) for _, info in entries),
            fields=fields,
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
