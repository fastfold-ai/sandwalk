"""Mixin: _create_or_edit_compatible_profile."""

from __future__ import annotations


class _CompatibleProfileEditMixin:
    def _create_or_edit_compatible_profile(self, profile_id: str | None = None) -> str | None:
        """Create or edit an OpenAI-compatible profile and return profile id."""
        cfg = self.session.config
        existing_profile = cfg.get_openai_profile(profile_id) if profile_id else None
        existing_backend = str((existing_profile or {}).get("backend") or "").strip().lower()
        existing_base_url = str((existing_profile or {}).get("base_url") or "").strip()
        existing_key = str((existing_profile or {}).get("api_key") or "").strip()
        existing_default_model = str((existing_profile or {}).get("default_model") or "").strip()

        default_base_url = existing_base_url or "http://localhost:11434/v1"
        backend = self._prompt_openai_compatible_backend(default_base_url)
        if not backend:
            return None
        if backend != "other":
            default_base_url = self._compatible_default_base_url(
                backend,
                fallback=default_base_url,
            )

        label_defaults = {
            "ollama": "Ollama",
            "unsloth": "Unsloth",
            "omlx": "oMLX",
            "ds4": "DS4",
            "llama_cpp": "llama.cpp",
            "lm_studio": "LM Studio",
            "other": "Custom Compatible Endpoint",
        }
        default_label = str((existing_profile or {}).get("label") or "").strip() or label_defaults.get(
            backend, "Compatible Endpoint"
        )
        label = self._prompt_profile_label(default_label)
        if not label:
            return None

        try:
            endpoint_input = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Endpoint base URL [{default_base_url}]: ")]
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        base_url = (endpoint_input or default_base_url).rstrip("/")
        if not base_url:
            return None

        if backend == "ollama":
            default_key = existing_key or "ollama"
            key_hint = (
                "  API key [(optional) Enter leaves blank; :default uses ollama; :keep keeps existing]: "
            )
        elif backend == "unsloth":
            default_key = existing_key or ""
            key_hint = "  API key [Unsloth sk-unsloth-...; Enter leaves blank; :keep keeps existing]: "
        elif backend == "omlx":
            default_key = existing_key or ""
            key_hint = "  API key [oMLX; Enter leaves blank; :keep keeps existing]: "
        elif backend == "ds4":
            default_key = existing_key or ""
            key_hint = "  API key [DS4 token (optional); Enter leaves blank; :keep keeps existing]: "
        elif backend == "llama_cpp":
            default_key = existing_key or ""
            key_hint = "  API key [llama.cpp key (optional); Enter leaves blank; :keep keeps existing]: "
        elif backend == "lm_studio":
            default_key = existing_key or ""
            key_hint = "  API key [LM Studio key (optional); Enter leaves blank; :keep keeps existing]: "
        else:
            default_key = existing_key or ""
            key_hint = "  API key [optional; Enter leaves blank; :keep keeps existing]: "
        try:
            api_key_input = self._secret_prompt_session.prompt(
                [("class:prompt", key_hint)],
                is_password=True,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        effective_key = self._resolve_optional_api_key_input(
            api_key_input,
            existing_key=existing_key,
            default_key=default_key,
        )

        profile_default_model = existing_default_model or str(self.session.current_model or "").strip() or "llama3.1"
        if profile_default_model == "__custom_openai_compatible__":
            profile_default_model = "llama3.1"

        saved_profile_id = cfg.upsert_openai_profile(
            profile_id=profile_id,
            label=label,
            backend=backend,
            base_url=base_url,
            api_key=effective_key,
            default_model=profile_default_model,
            set_active=(existing_backend != "openai"),
        )
        cfg.save()
        return saved_profile_id
