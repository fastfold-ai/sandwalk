"""API-key resolution (cli arg / existing config / env var / prompt) for setup."""

import os

import typer

from cli.app import console
from cli.setup.compatible_backend import _infer_openai_compatible_backend
from cli.setup.keys import (
    _prompt_api_key,
    _prompt_openai_api_key,
    _prompt_openai_api_key_with_default,
    _prompt_openai_compatible_api_key,
    _prompt_provider_api_key,
)
from cli.setup.openai_endpoint import (
    _is_openai_managed_base_url,
    _normalize_compatible_backend_name,
)


def _resolve_provider_key(
    cfg,
    provider: str,
    cli_key: str | None = None,
    openai_base_url: str | None = None,
    compatible_backend: str | None = None,
) -> str:
    """Resolve provider key from cli arg, existing config, env var, or prompt."""
    provider = str(provider).strip().lower()
    if provider in {"openai", "openai_compatible"}:
        is_compat = provider == "openai_compatible" or (
            bool(openai_base_url) and not _is_openai_managed_base_url(openai_base_url)
        )
        if is_compat:
            config_key = "llm.openai_compatible_api_key"
            env_var_name = ""  # keys live on Local LLM profiles, not a global env
            label = "OpenAI-compatible"
            backend = _normalize_compatible_backend_name(compatible_backend)
            if backend not in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}:
                backend = _infer_openai_compatible_backend(openai_base_url, None)
            active = cfg.get_openai_profile()
            existing_key = None
            if active and str(active.get("backend") or "").strip().lower() != "openai":
                existing_key = cfg._normalized_secret((active or {}).get("api_key"))
            if not existing_key:
                existing_key = cfg.llm_api_key("openai")
            default_compat_key = "ollama" if backend == "ollama" else None

            def prompt_fn():
                return _prompt_openai_compatible_api_key(backend=backend)
        else:
            config_key = "llm.openai_api_key"
            existing_key = cfg.get(config_key) or cfg.llm_api_key("openai")
            env_var_name = "OPENAI_API_KEY"
            prompt_fn = _prompt_openai_api_key
            label = "OpenAI"
            default_compat_key = None
    elif provider in ("xai", "google", "moonshot", "nvidia", "opencode"):
        from agent.config import OPENAI_COMPATIBLE_PROVIDERS

        meta = OPENAI_COMPATIBLE_PROVIDERS[provider]
        existing_key = cfg.llm_api_key(provider)
        env_var_name = meta["env_var"]
        label = meta["label"]
        config_key = meta["config_key"]
        signup_url = meta["signup_url"]
        def prompt_fn():
            return _prompt_provider_api_key(label, signup_url)
        default_compat_key = None
    else:
        existing_key = cfg.llm_api_key("anthropic")
        env_var_name = "ANTHROPIC_API_KEY"
        prompt_fn = _prompt_api_key
        label = "Anthropic"
        config_key = "llm.anthropic_api_key"
        default_compat_key = None

    console.print(f"\n  [cyan]{label} setup[/cyan]")
    if cli_key:
        candidate = cli_key.strip()
        issue = cfg.validate_llm_api_key(
            config_key,
            candidate,
            openai_base_url=openai_base_url,
        )
        if issue:
            console.print(f"  [red]{issue}[/red]")
            raise typer.Exit(code=2)
        return candidate
    if existing_key:
        existing_issue = cfg.validate_llm_api_key(
            config_key,
            existing_key,
            openai_base_url=openai_base_url,
        )
        if existing_issue:
            console.print(
                f"  [yellow]Existing {label} key is invalid and will be replaced:[/yellow] {existing_issue}"
            )
        else:
            masked = existing_key[:7] + "..." + existing_key[-4:] if len(existing_key) > 11 else "***"
            console.print(f"  API key already configured: [green]{masked}[/green]")
            try:
                keep = input("  Keep existing key? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\n  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
            if keep in ("", "y", "yes"):
                console.print("  [green]Keeping existing key.[/green]")
                return existing_key

    env_key = os.environ.get(env_var_name) if env_var_name else None
    if env_key:
        env_issue = cfg.validate_llm_api_key(
            config_key,
            env_key,
            openai_base_url=openai_base_url,
        )
        if env_issue:
            console.print(
                f"  [yellow]Ignoring invalid {env_var_name} value:[/yellow] {env_issue}"
            )
        else:
            masked = env_key[:7] + "..." + env_key[-4:] if len(env_key) > 11 else "***"
            console.print(f"  Found {env_var_name} in environment: [green]{masked}[/green]")
            try:
                save_it = input("  Save to sandwalk config? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\n  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
            if save_it in ("", "y", "yes"):
                return env_key

    while True:
        if default_compat_key:
            candidate = _prompt_openai_api_key_with_default(default_compat_key)
        else:
            candidate = prompt_fn()
        issue = cfg.validate_llm_api_key(
            config_key,
            candidate,
            openai_base_url=openai_base_url,
        )
        if not issue:
            return candidate
        console.print(f"  [yellow]{issue}[/yellow]")
