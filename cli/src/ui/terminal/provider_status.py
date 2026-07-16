"""Mixin: _current_provider_status, _compatible_backend_display_name, _compatible_default_base_url."""

from __future__ import annotations

from ui.terminal.model_ids import _ANTHROPIC_MODEL_IDS
from ui.terminal.model_ids import _is_openai_managed_base_url


class _ProviderStatusMixin:
    def _current_provider_status(self) -> tuple[str, str, str | None]:
        """Return effective provider id, user-facing label, and endpoint (if any)."""
        raw_provider = str(self.session.config.get("llm.provider", "anthropic") or "anthropic").strip().lower()
        current_model = str(self.session.current_model or "").strip()
        profile = None
        if hasattr(self.session.config, "get_openai_profile"):
            try:
                profile = self.session.config.get_openai_profile()
            except Exception:
                profile = None
        if not isinstance(profile, dict):
            profile = None
        if not profile:
            legacy_base_url = str(self.session.config.get("llm.openai_base_url") or "").strip()
            legacy_backend = str(self.session.config.get("llm.openai_compatible_backend") or "").strip().lower()
            if legacy_base_url and not _is_openai_managed_base_url(legacy_base_url):
                if legacy_backend not in {
                    "ollama",
                    "unsloth",
                    "omlx",
                    "ds4",
                    "llama_cpp",
                    "lm_studio",
                    "other",
                }:
                    legacy_backend = "other"
                profile = {
                    "id": "legacy_compatible",
                    "label": "OpenAI-compatible endpoint",
                    "backend": legacy_backend,
                    "base_url": legacy_base_url,
                    "api_key": "",
                }
            else:
                profile = {
                    "id": "openai_cloud",
                    "label": "OpenAI Cloud",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": str(self.session.config.get("llm.openai_api_key") or "").strip(),
                }
        profile_backend = str((profile or {}).get("backend") or "").strip().lower()
        profile_label = str((profile or {}).get("label") or "").strip()
        openai_base_url = ""
        if hasattr(self.session.config, "llm_openai_base_url"):
            try:
                candidate_base_url = self.session.config.llm_openai_base_url()
                if isinstance(candidate_base_url, str):
                    openai_base_url = candidate_base_url.strip()
            except Exception:
                openai_base_url = ""
        if not openai_base_url:
            openai_base_url = str(self.session.config.get("llm.openai_base_url") or "").strip()
        is_compat_endpoint = bool(openai_base_url) and (
            profile_backend != "openai" or not _is_openai_managed_base_url(openai_base_url)
        )

        if raw_provider == "openai":
            if is_compat_endpoint:
                label = profile_label or "OpenAI-compatible profile"
                if label.lower() in {"openai-compatible endpoint", "openai-compatible profile"}:
                    return "openai", "OpenAI-compatible custom endpoint", openai_base_url
                return "openai", f"OpenAI-compatible custom endpoint ({label})", openai_base_url
            return "openai", "OpenAI", None
        if raw_provider == "anthropic":
            # If a custom OpenAI-compatible endpoint is configured and the active
            # model is not an Anthropic id, treat this as OpenAI-compatible mode.
            if (
                is_compat_endpoint
                and current_model
                and current_model not in _ANTHROPIC_MODEL_IDS
            ):
                label = profile_label or "OpenAI-compatible profile"
                if label.lower() in {"openai-compatible endpoint", "openai-compatible profile"}:
                    return "openai", "OpenAI-compatible custom endpoint", openai_base_url
                return "openai", f"OpenAI-compatible custom endpoint ({label})", openai_base_url
            return "anthropic", "Anthropic", None
        from agent.config import OPENAI_COMPATIBLE_PROVIDERS

        if raw_provider in OPENAI_COMPATIBLE_PROVIDERS:
            meta = OPENAI_COMPATIBLE_PROVIDERS[raw_provider]
            return (
                raw_provider,
                str(meta.get("label") or raw_provider),
                str(meta.get("base_url") or "") or None,
            )
        return raw_provider or "anthropic", (raw_provider or "anthropic"), None

    @staticmethod
    def _compatible_backend_display_name(backend: str) -> str:
        """Return user-facing backend label."""
        backend_type = str(backend or "").strip().lower()
        if backend_type == "omlx":
            return "oMLX"
        if backend_type == "ollama":
            return "Ollama"
        if backend_type == "unsloth":
            return "Unsloth"
        if backend_type == "ds4":
            return "DS4"
        if backend_type == "llama_cpp":
            return "llama.cpp"
        if backend_type == "lm_studio":
            return "LM Studio"
        return "Custom"

    @staticmethod
    def _compatible_default_base_url(backend: str, fallback: str = "http://localhost:11434/v1") -> str:
        """Return default endpoint for a compatible backend."""
        backend_type = str(backend or "").strip().lower()
        defaults = {
            "ollama": "http://localhost:11434/v1",
            "unsloth": "http://localhost:8888/v1",
            "omlx": "http://localhost:8000/v1",
            "ds4": "http://localhost:8000/v1",
            "llama_cpp": "http://localhost:8080/v1",
            "lm_studio": "http://localhost:1234/v1",
        }
        return defaults.get(backend_type, fallback)
