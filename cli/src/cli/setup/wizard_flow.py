"""Provider/endpoint selection for `sandwalk setup` (resolution orchestrator)."""

import os

from cli.app import console
from cli.setup.compatible_backend import _resolve_openai_compatible_endpoint
from cli.setup.compatible_profile import (
    _find_compatible_profile_id_by_label,
    _prompt_setup_compatible_profile_id,
)
from cli.setup.model_prompt import _prompt_compatible_model_for_setup
from cli.setup.openai_endpoint_mode import _resolve_openai_base_url
from cli.setup.providers import _parse_provider_list, _prompt_setup_providers
from cli.setup.wizard_flow_keys import _apply_existing_profile, _resolve_all_provider_keys


def _setup_check_foundry_shortcut(cfg, default_provider: str) -> bool:
    """Return True (and persist) when Azure AI Foundry env vars make setup a no-op."""
    if default_provider != "anthropic":
        return False
    if not (os.environ.get("ANTHROPIC_FOUNDRY_API_KEY") or os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE")):
        return False
    console.print("\n  [green]Azure AI Foundry detected. No API key needed.[/green]")
    cfg.set("llm.provider", "anthropic")
    cfg.save()
    return True


def _setup_resolve_providers_and_keys(cfg, args: dict) -> dict:
    """Resolve selected providers, endpoint config, and API keys for each."""
    provider = args["provider"]
    selected_providers = (
        _parse_provider_list(provider) if provider else _prompt_setup_providers(args["default_provider"])
    )

    resolved_openai_base_url: str | None = None
    resolved_openai_backend: str | None = None
    resolved_openai_compatible_model: str | None = None
    selected_compatible_profile_id: str | None = None
    selected_compatible_profile: dict | None = None
    resolved_compatible_profile_label = str(args["profile_label"] or "").strip() or None

    if "openai_compatible" in selected_providers:
        selected_compatible_profile_id = _find_compatible_profile_id_by_label(
            cfg, resolved_compatible_profile_label
        )
        if selected_compatible_profile_id is None and not resolved_compatible_profile_label:
            selected_compatible_profile_id = _prompt_setup_compatible_profile_id(cfg)
        if selected_compatible_profile_id:
            selected_compatible_profile = cfg.get_openai_profile(selected_compatible_profile_id)
            if selected_compatible_profile:
                selected_compatible_profile, args, resolved_compatible_profile_label = _apply_existing_profile(
                    selected_compatible_profile, args, resolved_compatible_profile_label, console
                )
        resolved_openai_base_url, resolved_openai_backend = _resolve_openai_compatible_endpoint(
            cfg,
            cli_base_url=args["openai_base_url"],
            cli_backend=args["openai_compatible_backend"],
        )
        if not resolved_compatible_profile_label:
            label_defaults = {
                "ollama": "Ollama",
                "unsloth": "Unsloth",
                "omlx": "oMLX",
                "ds4": "DS4",
                "llama_cpp": "llama.cpp",
                "lm_studio": "LM Studio",
                "other": "Custom Compatible Endpoint",
            }
            resolved_compatible_profile_label = label_defaults.get(
                str(resolved_openai_backend or "").strip().lower(),
                "Compatible Endpoint",
            )
    elif "openai" in selected_providers:
        resolved_openai_base_url = _resolve_openai_base_url(
            cfg, cli_base_url=args["openai_base_url"], force_mode="cloud"
        )

    resolved_keys = _resolve_all_provider_keys(
        cfg, selected_providers, args, selected_compatible_profile,
        resolved_openai_base_url, resolved_openai_backend,
    )
    if "openai_compatible" in resolved_keys:
        chosen_key = resolved_keys["openai_compatible"]
        profile_name = str(resolved_compatible_profile_label or "Compatible Endpoint").strip()
        backend_name = {"omlx": "oMLX", "ollama": "Ollama", "unsloth": "Unsloth"}.get(
            str(resolved_openai_backend).strip().lower(), "Custom"
        )
        console.print(
            f"  [dim]Profile:[/dim] {profile_name}  "
            f"[dim]Template:[/dim] {backend_name}  "
            f"[dim]Endpoint:[/dim] {resolved_openai_base_url}"
        )
        choice = _prompt_compatible_model_for_setup(
            cfg, base_url=resolved_openai_base_url, backend=resolved_openai_backend, api_key=chosen_key,
        )
        if isinstance(choice, tuple):
            resolved_openai_compatible_model = choice[0]
            retry_key = str(choice[1] or "").strip()
            if retry_key:
                resolved_keys["openai_compatible"] = retry_key
        else:
            resolved_openai_compatible_model = choice
        if not resolved_openai_compatible_model and args["profile_default_model"]:
            resolved_openai_compatible_model = str(args["profile_default_model"]).strip() or None

    return {
        "selected_providers": selected_providers,
        "resolved_keys": resolved_keys,
        "resolved_openai_base_url": resolved_openai_base_url,
        "resolved_openai_backend": resolved_openai_backend,
        "resolved_openai_compatible_model": resolved_openai_compatible_model,
        "selected_compatible_profile_id": selected_compatible_profile_id,
        "resolved_compatible_profile_label": resolved_compatible_profile_label,
    }


