"""Mixin: _probe_compatible_profile."""

from __future__ import annotations

from typing import Any


class _ProfileProbeMixin:
    def _probe_compatible_profile(
        self,
        *,
        base_url: str,
        backend: str,
        api_key: str | None,
    ) -> dict[str, Any]:
        """Probe one compatible profile and return health/model diagnostics."""
        backend_type = str(backend or "").strip().lower() or "other"
        models_path = self._compatible_models_path_label(backend_type)
        discovered: list[str] = []
        errors: list[str] = []
        source = ""

        if backend_type in {"unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
            models, err = self._fetch_openai_models(
                base_url,
                api_key=api_key,
                quiet=True,
                return_error=True,
            )
            discovered = list(models)
            source = "/v1/models"
            if err:
                errors.append(str(err))
        elif backend_type == "ollama":
            models, err = self._fetch_ollama_tags(
                base_url,
                api_key=api_key,
                quiet=True,
                return_error=True,
            )
            discovered = list(models)
            source = "/api/tags"
            if err:
                errors.append(str(err))
            if not discovered:
                models_fallback, err_fallback = self._fetch_openai_models(
                    base_url,
                    api_key=api_key,
                    quiet=True,
                    return_error=True,
                )
                discovered = list(models_fallback)
                source = "/v1/models"
                if err_fallback:
                    errors.append(str(err_fallback))
        else:
            models, err = self._fetch_openai_models(
                base_url,
                api_key=api_key,
                quiet=True,
                return_error=True,
            )
            discovered = list(models)
            source = "/v1/models"
            if err:
                errors.append(str(err))
            if not discovered:
                models_fallback, err_fallback = self._fetch_ollama_tags(
                    base_url,
                    api_key=api_key,
                    quiet=True,
                    return_error=True,
                )
                discovered = list(models_fallback)
                source = "/api/tags"
                if err_fallback:
                    errors.append(str(err_fallback))

        health = "[green]healthy[/green]" if discovered else "[yellow]no models[/yellow]"
        if not discovered and errors:
            health = "[red]error[/red]"
        error_text = ""
        if errors:
            joined_error = "; ".join(dict.fromkeys(errors))
            error_text = self._truncate_discovery_detail(joined_error, max_chars=120)

        return {
            "health": health,
            "models": discovered,
            "models_source": source,
            "models_path": models_path,
            "error": error_text,
        }
