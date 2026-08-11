"""Mixin: _compatible_install_url, _resolve_optional_api_key_input, _current_compatible_backend_label, _mention_completing."""

from __future__ import annotations


class _CompatibleBackendInfoMixin:
    @staticmethod
    def _compatible_install_url(backend: str) -> str:
        """Return install/reference URL for a compatible backend template."""
        try:
            from agent.config import Config

            return Config.compatible_backend_install_url(backend)
        except Exception:
            backend_type = str(backend or "").strip().lower()
            fallback = ""
            urls = {
                "ollama": "https://github.com/ollama/ollama",
                "unsloth": "https://github.com/unslothai/unsloth",
                "omlx": "https://github.com/jundot/omlx",
                "ds4": "https://github.com/antirez/ds4",
                "llama_cpp": "https://github.com/ggml-org/llama.cpp",
                "lm_studio": "https://lmstudio.ai/docs/developer/openai-compat",
                "other": fallback,
            }
            return urls.get(backend_type, fallback)

    @staticmethod
    def _resolve_optional_api_key_input(
        raw_input: str,
        *,
        existing_key: str = "",
        default_key: str = "",
    ) -> str | None:
        """Resolve optional key input where blank means unset/clear."""
        normalized = str(raw_input or "").strip()
        lowered = normalized.lower()
        if lowered in {":keep", "keep"}:
            kept = str(existing_key or default_key or "").strip()
            return kept or None
        if lowered in {":default", "default"}:
            chosen = str(default_key or "").strip()
            return chosen or None
        if not normalized:
            return None
        return normalized

    def _current_compatible_backend_label(self) -> str | None:
        """Return compatible backend label for status line, when applicable."""
        _, provider_label, endpoint = self._current_provider_status()
        profile = None
        if hasattr(self.session.config, "get_openai_profile"):
            try:
                profile = self.session.config.get_openai_profile()
            except Exception:
                profile = None
        if not isinstance(profile, dict):
            profile = None
        backend = str((profile or {}).get("backend") or "").strip().lower()
        if backend not in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other", "custom"}:
            backend = str(
                self.session.config.get("llm.openai_compatible_backend") or ""
            ).strip().lower()
        if not endpoint or "OpenAI-compatible" not in provider_label:
            return None

        if backend in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
            return self._compatible_backend_display_name(backend)
        if backend in {"other", "custom"}:
            return "Custom"

        # Fallback heuristics for older configs that predate backend selection.
        key = str(
            (profile or {}).get("api_key")
            or ""
        ).strip().lower()
        endpoint_text = str(endpoint).strip().lower()
        if key.startswith("sk-unsloth-") or "8888" in endpoint_text:
            return "Unsloth"
        if (
            key.startswith("dsv4-")
            or key.startswith("sk-ds4-")
            or "ds4" in endpoint_text
            or "deepseek-v4" in endpoint_text
        ):
            return "DS4"
        if "1234" in endpoint_text or "lmstudio" in endpoint_text or "lm-studio" in endpoint_text:
            return "LM Studio"
        if (
            "8080" in endpoint_text
            or "llama.cpp" in endpoint_text
            or "llama-cpp" in endpoint_text
            or "llamacpp" in endpoint_text
        ):
            return "llama.cpp"
        if "8000" in endpoint_text or "omlx" in endpoint_text:
            return "oMLX"
        if "11434" in endpoint_text:
            return "Ollama"
        return "Custom"

    def _mention_completing(self) -> bool:
        """Check if ``#`` tool/dataset/workflow completions are currently active."""
        try:
            from prompt_toolkit.application.current import get_app

            buf = get_app().current_buffer
            if buf.complete_state and "#" in (buf.text or ""):
                # Prefer # trigger when both # and @ are present.
                at = (buf.text or "").rfind("@")
                hash_pos = (buf.text or "").rfind("#")
                return hash_pos >= 0 and hash_pos >= at
        except Exception:
            pass
        try:
            buf = self._prompt_session.app.current_buffer
            if buf.complete_state and "#" in buf.text:
                return True
        except Exception:
            pass
        return False
