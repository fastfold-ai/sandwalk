"""User-added custom cloud model preferences."""

from .constants import VALID_LLM_PROVIDERS


class ModelCustomMixin:
    """Custom cloud model registry exposed on ``Config``."""

    def custom_models(self) -> list[dict[str, str]]:
        """Return user-added cloud model IDs (provider + id), normalized."""
        raw = self.get("llm.custom_models", [])
        if not isinstance(raw, list):
            return []
        items: list[dict[str, str]] = []
        seen: set[str] = set()
        for entry in raw:
            if isinstance(entry, str):
                model_id = entry.strip()
                provider = "openai"
                label = model_id
            elif isinstance(entry, dict):
                model_id = str(entry.get("id") or "").strip()
                provider = str(entry.get("provider") or "openai").strip().lower() or "openai"
                label = str(entry.get("label") or model_id).strip() or model_id
            else:
                continue
            if not model_id or model_id in seen:
                continue
            if provider not in VALID_LLM_PROVIDERS:
                provider = "openai"
            seen.add(model_id)
            items.append({"id": model_id, "provider": provider, "label": label})
        return items

    def add_custom_model(
        self,
        *,
        model_id: str,
        provider: str = "openai",
        label: str | None = None,
    ) -> dict[str, str]:
        """Add a custom cloud model ID. Raises ValueError on invalid/duplicate."""
        target = str(model_id or "").strip()
        if not target:
            raise ValueError("model_id is required.")
        provider_norm = str(provider or "openai").strip().lower() or "openai"
        if provider_norm not in VALID_LLM_PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{provider}'. Use one of: {', '.join(sorted(VALID_LLM_PROVIDERS))}."
            )
        from agent.model_catalog import cloud_catalog_models

        catalog_ids = {item["id"] for item in cloud_catalog_models()}
        if target in catalog_ids:
            raise ValueError(f"Model '{target}' is already in the built-in catalog.")
        existing = self.custom_models()
        if any(item["id"] == target for item in existing):
            raise ValueError(f"Custom model '{target}' already exists.")
        record = {
            "id": target,
            "provider": provider_norm,
            "label": str(label or target).strip() or target,
        }
        next_list = [*existing, record]
        self.set("llm.custom_models", next_list)
        return record

    def remove_custom_model(self, model_id: str) -> bool:
        """Remove a custom cloud model. Returns True if something was removed."""
        target = str(model_id or "").strip()
        if not target:
            raise ValueError("model_id is required.")
        existing = self.custom_models()
        next_list = [item for item in existing if item["id"] != target]
        if len(next_list) == len(existing):
            return False
        self.set("llm.custom_models", next_list)
        # Also un-hide if it was toggled off.
        hidden = set(self.hidden_models())
        if target in hidden:
            hidden.discard(target)
            self.set("llm.hidden_models", sorted(hidden))
        return True
