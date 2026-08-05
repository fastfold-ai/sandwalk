"""Hidden-models/tools preferences and one-time catalog-defaults migration."""

import logging

logger = logging.getLogger("config")


class ModelHiddenMixin:
    """Agent model/tool visibility toggles exposed on ``Config``."""

    def hidden_models(self) -> list[str]:
        """Return model IDs hidden from agent model selection."""
        raw = self.get("llm.hidden_models", [])
        if not isinstance(raw, list):
            return []
        return sorted(
            {
                str(item).strip()
                for item in raw
                if str(item or "").strip()
            }
        )

    @staticmethod
    def provider_model_key(provider: str | None, model_id: str) -> str:
        """Stable hide key for a provider-scoped catalog row."""
        mid = str(model_id or "").strip()
        prov = str(provider or "").strip().lower()
        if prov and mid:
            return f"{prov}:{mid}"
        return mid

    def is_model_hidden(self, model_id: str, provider: str | None = None) -> bool:
        """True when ``model_id`` is hidden globally or for ``provider``.

        Provider sync writes ``{provider}:{model_id}`` so Moonshot auto-hide
        does not suppress the same bare id under OpenCode Zen.
        """
        target = str(model_id or "").strip()
        if not target:
            return False
        hidden = set(self.hidden_models())
        if target in hidden:
            return True
        if provider:
            return self.provider_model_key(provider, target) in hidden
        return False

    def set_model_hidden(self, model_id: str, hidden: bool) -> list[str]:
        """Hide or show a model ID for agent use. Returns the updated hidden list."""
        target = str(model_id or "").strip()
        if not target:
            raise ValueError("model_id is required.")
        current = set(self.hidden_models())
        if hidden:
            current.add(target)
        else:
            current.discard(target)
        next_list = sorted(current)
        self.set("llm.hidden_models", next_list)
        return next_list

    def _migrate_catalog_defaults(self) -> None:
        """Seed newly default-disabled catalog models into hidden_models once.

        Also unhides curated OpenRouter models that are default-enabled so a
        prior discovery seed (opt-in hide) does not keep them stuck off after
        we promote them into the curated enabled set.
        """
        from agent.model_catalog import (
            AVAILABLE_MODELS,
            CATALOG_DEFAULTS_VERSION,
            DEFAULT_DISABLED_MODELS,
        )

        try:
            current_version = int(self.get("llm.catalog_defaults_version", 0) or 0)
        except (TypeError, ValueError):
            current_version = 0
        if current_version >= CATALOG_DEFAULTS_VERSION:
            return

        hidden = set(self.hidden_models())
        hidden.update(DEFAULT_DISABLED_MODELS)
        curated_enabled = {
            mid
            for mid, _label, _desc in AVAILABLE_MODELS.get("openrouter", [])
            if mid not in DEFAULT_DISABLED_MODELS
        }
        for mid in curated_enabled:
            hidden.discard(mid)
            hidden.discard(f"openrouter:{mid}")
        self.set("llm.hidden_models", sorted(hidden))
        self.set("llm.catalog_defaults_version", CATALOG_DEFAULTS_VERSION)
        try:
            # load() clears dirty tracking before migration. If we save only the
            # migration keys, in-memory env-loaded secrets would be dropped when
            # save() replaces self._data with the merged disk payload.
            self._dirty_keys.update(self._data.keys())
            self.save()
        except Exception as exc:  # pragma: no cover - best-effort persistence
            logger.warning("Failed to persist catalog defaults migration: %s", exc)

    def hidden_tools(self) -> list[str]:
        """Return tool IDs disabled from agent tool discovery/calls.

        Registry core tools are never hidden — they stay available even if an
        older config still lists them under ``agent.hidden_tools``.
        """
        from agent.tool_tiers import CORE_TOOL_NAMES

        raw = self.get("agent.hidden_tools", [])
        if not isinstance(raw, list):
            return []
        return sorted(
            {
                str(item).strip()
                for item in raw
                if str(item or "").strip()
                and str(item).strip() not in CORE_TOOL_NAMES
            }
        )

    def is_tool_hidden(self, tool_id: str) -> bool:
        target = str(tool_id or "").strip()
        if not target:
            return False
        from agent.tool_tiers import is_core_tool

        if is_core_tool(target):
            return False
        return target in set(self.hidden_tools())

    def set_tool_hidden(self, tool_id: str, hidden: bool) -> list[str]:
        """Enable/disable a tool for agent use. Returns the updated hidden list.

        Core registry tools cannot be hidden.
        """
        from agent.tool_tiers import is_core_tool

        target = str(tool_id or "").strip()
        if not target:
            raise ValueError("tool_id is required.")
        if is_core_tool(target) and hidden:
            raise ValueError(
                f"Core tool '{target}' cannot be disabled."
            )
        current = set(self.hidden_tools())
        # Drop any stale core entries still on disk.
        from agent.tool_tiers import CORE_TOOL_NAMES

        current -= set(CORE_TOOL_NAMES)
        if hidden:
            current.add(target)
        else:
            current.discard(target)
        next_list = sorted(current)
        self.set("agent.hidden_tools", next_list)
        return next_list
