"""Profile id/record normalization helpers mixed into ``Config``."""

import re
from typing import Any

from .constants import OPENAI_PROFILE_BACKENDS
from .providers import OPENAI_PROFILE_DEFAULTS


class ProfileRecordMixin:
    """Helpers that normalize a single OpenAI/OpenAI-compatible profile record."""

    @staticmethod
    def _slugify_profile_id(value: str) -> str:
        """Create stable profile IDs from labels."""
        normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
        return normalized or "profile"

    @classmethod
    def _unique_profile_id(cls, base_id: str, existing: dict[str, dict]) -> str:
        """Return a unique profile id using numeric suffixes when required."""
        candidate = cls._slugify_profile_id(base_id)
        if candidate not in existing:
            return candidate
        idx = 2
        while f"{candidate}_{idx}" in existing:
            idx += 1
        return f"{candidate}_{idx}"

    @classmethod
    def _normalize_discovery_sequence(cls, backend: str, value: Any) -> list[str]:
        """Normalize model discovery strategies for profile records."""
        allowed = {"v1_models", "ollama_tags"}
        if isinstance(value, list):
            parsed = [str(item or "").strip().lower() for item in value]
            filtered = [item for item in parsed if item in allowed]
            if filtered:
                deduped: list[str] = []
                for item in filtered:
                    if item not in deduped:
                        deduped.append(item)
                return deduped
        default_seq = OPENAI_PROFILE_DEFAULTS.get(backend, OPENAI_PROFILE_DEFAULTS["other"]).get("discovery", [])
        return [str(item) for item in default_seq]

    @classmethod
    def _normalize_profile_record(cls, profile_id: str, raw: Any) -> dict[str, Any]:
        """Normalize an OpenAI profile record with backend defaults."""
        payload = raw if isinstance(raw, dict) else {}
        backend = cls._normalize_compatible_backend_name(payload.get("backend"))
        if backend not in OPENAI_PROFILE_BACKENDS:
            backend = cls.infer_openai_compatible_backend(payload.get("base_url"), payload.get("api_key"))
        if profile_id == "openai_cloud":
            backend = "openai"

        defaults = OPENAI_PROFILE_DEFAULTS.get(backend, OPENAI_PROFILE_DEFAULTS["other"])

        label_raw = str(payload.get("label") or "").strip()
        label = label_raw or str(defaults.get("label") or "OpenAI Profile")

        base_url = cls._normalize_openai_base_url(payload.get("base_url")) or str(defaults.get("base_url") or "")
        if backend == "openai":
            if not cls._is_openai_managed_base_url(base_url):
                base_url = str(OPENAI_PROFILE_DEFAULTS["openai"]["base_url"])
        else:
            if cls._is_openai_managed_base_url(base_url):
                base_url = str(defaults.get("base_url") or OPENAI_PROFILE_DEFAULTS["other"]["base_url"])

        default_model_raw = str(payload.get("default_model") or "").strip()
        default_model = default_model_raw or str(defaults.get("default_model") or "")

        return {
            "label": label,
            "backend": backend,
            "base_url": base_url.rstrip("/"),
            "api_key": cls._normalized_secret(payload.get("api_key")),
            "discovery": cls._normalize_discovery_sequence(backend, payload.get("discovery")),
            "default_model": default_model,
        }
