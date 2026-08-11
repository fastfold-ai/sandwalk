"""Persist resolved setup-wizard provider choices into config."""

import os

from cli.app import console
from cli.setup.compatible_profile import _find_compatible_profile_id_by_label
from cli.setup.openai_endpoint import _normalize_openai_base_url
from cli.setup.providers import _setup_provider_runtime_id


def _setup_persist_provider_choice(cfg, selection: dict, args: dict) -> None:
    """Save resolved provider keys/profile and activate the chosen provider."""
    selected_providers = selection["selected_providers"]
    resolved_openai_backend = selection["resolved_openai_backend"]
    resolved_openai_base_url = selection["resolved_openai_base_url"]
    resolved_compatible_profile_label = selection["resolved_compatible_profile_label"]

    resolved_compatible_profile_id: str | None = None
    for prov, key in selection["resolved_keys"].items():
        if prov == "openai":
            cfg.set("llm.openai_api_key", key)
            cfg.upsert_openai_profile(
                profile_id="openai_cloud",
                label="OpenAI Cloud",
                backend="openai",
                base_url="https://api.openai.com/v1",
                api_key=key,
            )
        elif prov == "openai_compatible":
            backend = str(resolved_openai_backend or "").strip().lower() or "other"
            default_endpoints = {
                "ollama": "http://localhost:11434/v1",
                "unsloth": "http://localhost:8888/v1",
                "omlx": "http://localhost:8000/v1",
            }
            endpoint = (
                _normalize_openai_base_url(resolved_openai_base_url)
                or default_endpoints.get(backend, "http://localhost:11434/v1")
            )
            profile_id = selection["selected_compatible_profile_id"] or _find_compatible_profile_id_by_label(
                cfg, resolved_compatible_profile_label
            )
            desired_model = (
                str(args["profile_default_model"] or "").strip()
                or str(selection["resolved_openai_compatible_model"] or "").strip()
                or None
            )
            resolved_compatible_profile_id = cfg.upsert_openai_profile(
                profile_id=profile_id,
                label=resolved_compatible_profile_label,
                backend=backend,
                base_url=endpoint,
                api_key=key,
                default_model=desired_model,
                set_active=True,
                set_default=args["set_default_profile"],
            )
            if desired_model:
                cfg.set("llm.model", desired_model)
        elif prov == "anthropic":
            cfg.set("llm.anthropic_api_key", key)
        elif prov in (
            "xai",
            "google",
            "moonshot",
            "nvidia",
            "opencode",
            "deepseek",
            "minimax",
            "mistral",
            "qwen",
            "together",
            "openrouter",
        ):
            from agent.config import OPENAI_COMPATIBLE_PROVIDERS

            cfg.set(OPENAI_COMPATIBLE_PROVIDERS[prov]["config_key"], key)

    active_setup_provider = (
        args["default_provider"] if args["default_provider"] in selected_providers else selected_providers[0]
    )
    cfg.set("llm.provider", _setup_provider_runtime_id(active_setup_provider))
    _apply_default_model(cfg, active_setup_provider, selected_providers, resolved_compatible_profile_id)

    if args["set_default_profile"] and "openai" in selected_providers and "openai_compatible" not in selected_providers:
        cfg.set_openai_default_profile("openai_cloud")

    cloud_key, boltz_key = args["cloud_key"], args["boltz_key"]
    if cloud_key:
        cfg.set("api.fastfold_cloud_key", cloud_key)
        # Make available immediately to subprocess tools/skills in this run.
        os.environ["FASTFOLD_API_KEY"] = cloud_key
    if boltz_key:
        cfg.set("api.boltz_api_key", boltz_key)
        os.environ["BOLTZ_API_KEY"] = boltz_key
    cfg.save()


def _apply_default_model(cfg, active_setup_provider, selected_providers, resolved_compatible_profile_id) -> None:
    # Ensure a sensible default model when activating a first-party
    # OpenAI-compatible provider (xAI / Google Gemini / NVIDIA / OpenCode Go).
    from agent.config import OPENAI_COMPATIBLE_PROVIDERS as _OCP

    if active_setup_provider in _OCP:
        meta = _OCP[active_setup_provider]
        current_model = str(cfg.get("llm.model") or "").strip().lower()
        default_model = str(meta.get("default_model") or "")
        prefixes = {
            "xai": "grok",
            "google": "gemini",
            "moonshot": "kimi-",
            "nvidia": "nvidia/",
            "opencode": "",
            "deepseek": "deepseek",
            "minimax": "minimax",
            "mistral": "mistral",
            "qwen": "qwen",
            "together": "",
            "openrouter": "",
        }
        prefix = prefixes.get(active_setup_provider, "")
        if default_model and (not prefix or not current_model.startswith(prefix)):
            cfg.set("llm.model", default_model)
    if active_setup_provider == "openai":
        current_model = str(cfg.get("llm.model") or "").strip()
        from agent.config import Config as _Cfg

        if not _Cfg._looks_like_openai_cloud_model(current_model):
            cfg.set("llm.model", "gpt-5.6-sol")
        if "openai_compatible" in selected_providers and resolved_compatible_profile_id:
            cfg.set_openai_active_profile(resolved_compatible_profile_id)
        else:
            cfg.set_openai_active_profile("openai_cloud")


def _setup_print_provider_summary(selected_providers: list[str], cloud_key: str | None, boltz_key: str | None) -> None:
    from cli.constants import BOLTZ_API_KEYS_URL, FASTFOLD_CLOUD_API_KEYS_URL

    provider_labels = ", ".join(
        (
            "OpenAI"
            if p == "openai"
            else "OpenAI-compatible"
            if p == "openai_compatible"
            else "xAI"
            if p == "xai"
            else "Google Gemini"
            if p == "google"
            else "NVIDIA"
            if p == "nvidia"
            else "OpenCode Zen"
            if p == "opencode"
            else "DeepSeek"
            if p == "deepseek"
            else "MiniMax"
            if p == "minimax"
            else "Mistral"
            if p == "mistral"
            else "Qwen"
            if p == "qwen"
            else "Together AI"
            if p == "together"
            else "OpenRouter"
            if p == "openrouter"
            else "Anthropic"
        )
        for p in selected_providers
    )
    console.print(
        f"\n  [green]{provider_labels} API key(s) saved to ~/.sandwalk/config.json[/green]"
    )
    if cloud_key:
        console.print("  [green]Fastfold AI Cloud API key saved.[/green]")
    else:
        console.print(
            "  [yellow]Fastfold AI Cloud API key skipped.[/yellow] "
            f"Set later with `sandwalk config set api.fastfold_cloud_key <key>` "
            f"or visit {FASTFOLD_CLOUD_API_KEYS_URL}"
        )
    if boltz_key:
        console.print("  [green]Boltz API key saved.[/green]")
    else:
        console.print(
            "  [yellow]Boltz API key skipped.[/yellow] "
            "Set later with `sandwalk config set api.boltz_api_key <key>` "
            f"or visit {BOLTZ_API_KEYS_URL}"
        )
