"""Build the flat model catalog used by /models (modal + numbered fallback)."""

from __future__ import annotations

from typing import Any

from .model_ids import AVAILABLE_MODELS

# Cloud catalog ids that are not in OPENAI_COMPATIBLE_PROVIDERS.
_CLOUD_PROVIDER_LABELS = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
}


def provider_display_label(provider: str, *, fallback: str | None = None) -> str:
    """Canonical section title for a provider id (avoids openrouter vs OpenRouter)."""
    prov = str(provider or "").strip().lower()
    if not prov:
        return str(fallback or "Models").strip() or "Models"
    if prov in _CLOUD_PROVIDER_LABELS:
        return _CLOUD_PROVIDER_LABELS[prov]
    try:
        from agent.config import OPENAI_COMPATIBLE_PROVIDERS

        meta = OPENAI_COMPATIBLE_PROVIDERS.get(prov) or {}
        label = str(meta.get("label") or "").strip()
        if label:
            return label
    except Exception:  # noqa: BLE001
        pass
    text = str(fallback or provider or "Models").strip() or "Models"
    # If fallback is just the raw id, title-case it for display.
    if text.lower() == prov:
        return prov.capitalize() if len(prov) <= 4 else text.title()
    return text


def collect_model_options(terminal: Any) -> tuple[list[dict], list[str]]:
    """Return ``(options, discovery_warnings)`` for the model picker.

    Each option dict has: provider, model_id, display, desc, profile_id,
    and optional backend / provider_label.
    """
    from agent.config import Config

    cfg = getattr(getattr(terminal, "session", None), "config", None)
    models_with_provider: list[dict] = []
    profile_discovery_warnings: list[str] = []

    hidden_models: set[str] = set()
    if isinstance(cfg, Config):
        try:
            hidden_models = set(cfg.hidden_models())
        except Exception:  # noqa: BLE001
            hidden_models = set()

    for prov, models in AVAILABLE_MODELS.items():
        for model_id, display, desc in models:
            if model_id == "__custom_openai_compatible__":
                continue
            if isinstance(cfg, Config):
                if cfg.is_model_hidden(model_id, prov):
                    continue
            elif model_id in hidden_models:
                continue
            models_with_provider.append(
                {
                    "provider": prov,
                    "model_id": model_id,
                    "display": display,
                    "desc": desc,
                    "profile_id": None,
                    "provider_label": provider_display_label(prov),
                }
            )

    if isinstance(cfg, Config):
        from agent.config import OPENAI_COMPATIBLE_PROVIDERS
        from agent.model_catalog import (
            format_discovered_model_label,
            opencode_model_is_supported,
        )
        from agent.model_discovery import probe_compatible_profile

        existing_keys = {
            (
                str(item.get("provider") or ""),
                str(item.get("model_id") or ""),
                str(item.get("profile_id") or ""),
            )
            for item in models_with_provider
        }
        for prov, meta in OPENAI_COMPATIBLE_PROVIDERS.items():
            if str(meta.get("discover_models") or "").strip().lower() not in {
                "1",
                "true",
                "yes",
            }:
                continue
            api_key = cfg.llm_api_key(prov)
            if not api_key:
                continue
            base_url = str(meta.get("base_url") or "").strip()
            if not base_url:
                continue
            label = str(meta.get("label") or prov)
            probe = probe_compatible_profile(
                base_url=base_url,
                backend="other",
                api_key=api_key,
            )
            discovered_models = list(probe.get("models") or [])
            if not discovered_models:
                fallback = str(meta.get("default_model") or "").strip()
                if fallback:
                    discovered_models = [fallback]
            for model_id in discovered_models:
                if prov == "opencode" and not opencode_model_is_supported(model_id):
                    continue
                key = (prov, model_id, "")
                if key in existing_keys or cfg.is_model_hidden(model_id, prov):
                    continue
                existing_keys.add(key)
                models_with_provider.append(
                    {
                        "provider": prov,
                        "model_id": model_id,
                        "display": format_discovered_model_label(model_id),
                        "desc": f"{label} (discovered)",
                        "profile_id": None,
                        "provider_label": provider_display_label(
                            prov, fallback=label
                        ),
                    }
                )

        compatible_profiles = cfg.openai_profiles(include_cloud=False)
        for profile_id, profile in sorted(
            compatible_profiles.items(),
            key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
        ):
            backend = str(profile.get("backend") or "other").strip().lower()
            base_url = str(profile.get("base_url") or "").strip()
            if not base_url:
                continue
            profile_label = str(profile.get("label") or profile_id).strip()
            api_key = str(profile.get("api_key") or "").strip() or None
            fetch = getattr(terminal, "_fetch_compatible_models", None)
            discovered_models = (
                fetch(base_url, backend=backend, api_key=api_key, quiet=True)
                if callable(fetch)
                else []
            )
            if not discovered_models:
                backend_label = "other"
                display_name = getattr(
                    terminal, "_compatible_backend_display_name", None
                )
                if callable(display_name):
                    backend_label = display_name(backend)
                issue = ""
                probe_fn = getattr(terminal, "_probe_compatible_profile", None)
                if callable(probe_fn):
                    probe = probe_fn(
                        base_url=base_url, backend=backend, api_key=api_key
                    )
                    if isinstance(probe, dict):
                        issue = str(probe.get("error") or "").strip()
                if issue:
                    profile_discovery_warnings.append(
                        f"{profile_label} ({backend_label}): {issue}"
                    )
                else:
                    profile_discovery_warnings.append(
                        f"{profile_label} ({backend_label}): no models discovered"
                    )
            if not discovered_models and profile_id == cfg.active_openai_profile_id():
                fallback_model = str(profile.get("default_model") or "").strip()
                if fallback_model:
                    discovered_models = [fallback_model]
            for discovered_model in discovered_models:
                models_with_provider.append(
                    {
                        "provider": "local",
                        "model_id": discovered_model,
                        "display": f"{profile_label}: {discovered_model}",
                        "desc": f"{backend} profile model",
                        "profile_id": profile_id,
                        "backend": backend,
                        "provider_label": profile_label,
                    }
                )

    return models_with_provider, profile_discovery_warnings


def option_pref_key(option: dict) -> str:
    from agent.config import Config

    return Config.model_pref_key(
        str(option.get("provider") or ""),
        str(option.get("model_id") or ""),
        profile_id=str(option.get("profile_id") or "").strip() or None,
    )


def is_current_option(
    option: dict,
    *,
    current_model: str,
    current_provider: str,
    active_profile_id: str | None,
    active_backend: str,
) -> bool:
    model_id = str(option.get("model_id") or "")
    prov = str(option.get("provider") or "")
    profile_id = str(option.get("profile_id") or "").strip() or None
    status = str(current_provider).strip().lower()
    if model_id != current_model:
        return False
    if profile_id:
        # Profile rows are catalogued as provider "local"; status reports openai.
        if status not in {"openai", "local"}:
            return False
        return profile_id == (active_profile_id or "")
    if status != prov:
        return False
    if prov == "openai":
        return active_backend in {"", "openai"}
    return True
