"""Favorite / recent model preferences for the /models picker."""

from __future__ import annotations

_MAX_RECENT = 12


class ModelFavoritesMixin:
    """Pinned favorites + recently selected models on ``Config``."""

    def favorite_models(self) -> list[str]:
        raw = self.get("llm.favorite_models", [])
        if not isinstance(raw, list):
            return []
        seen: list[str] = []
        for item in raw:
            key = str(item or "").strip()
            if key and key not in seen:
                seen.append(key)
        return seen

    def recent_models(self) -> list[str]:
        raw = self.get("llm.recent_models", [])
        if not isinstance(raw, list):
            return []
        seen: list[str] = []
        for item in raw:
            key = str(item or "").strip()
            if key and key not in seen:
                seen.append(key)
        return seen[:_MAX_RECENT]

    @staticmethod
    def model_pref_key(
        provider: str | None,
        model_id: str,
        *,
        profile_id: str | None = None,
    ) -> str:
        """Stable key for favorites/recent: ``provider:model`` or ``local:profile:model``."""
        mid = str(model_id or "").strip()
        pid = str(profile_id or "").strip()
        prov = str(provider or "").strip().lower()
        if pid:
            return f"local:{pid}:{mid}"
        if prov and mid:
            return f"{prov}:{mid}"
        return mid

    def is_model_favorite(
        self,
        model_id: str,
        provider: str | None = None,
        *,
        profile_id: str | None = None,
    ) -> bool:
        key = self.model_pref_key(provider, model_id, profile_id=profile_id)
        return bool(key) and key in set(self.favorite_models())

    def toggle_model_favorite(
        self,
        model_id: str,
        provider: str | None = None,
        *,
        profile_id: str | None = None,
    ) -> bool:
        """Toggle favorite. Returns True when the model is now favorited."""
        key = self.model_pref_key(provider, model_id, profile_id=profile_id)
        if not key:
            return False
        current = self.favorite_models()
        if key in current:
            next_list = [item for item in current if item != key]
            self.set("llm.favorite_models", next_list)
            return False
        self.set("llm.favorite_models", [*current, key])
        return True

    def push_recent_model(
        self,
        model_id: str,
        provider: str | None = None,
        *,
        profile_id: str | None = None,
    ) -> list[str]:
        key = self.model_pref_key(provider, model_id, profile_id=profile_id)
        if not key:
            return self.recent_models()
        rest = [item for item in self.recent_models() if item != key]
        next_list = [key, *rest][:_MAX_RECENT]
        self.set("llm.recent_models", next_list)
        return next_list
