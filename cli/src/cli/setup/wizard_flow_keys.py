"""Per-provider API-key resolution helpers used by the setup wizard flow."""

import typer

from cli.app import console
from cli.setup.provider_key import _resolve_provider_key


def _apply_existing_profile(profile: dict, args: dict, label: str | None, console_obj) -> tuple[dict, dict, str | None]:
    """Backfill setup args from a reused compatible profile; returns updated (profile, args, label)."""
    selected_label = str(profile.get("label") or "").strip()
    selected_backend = str(profile.get("backend") or "other").strip().lower()
    selected_endpoint = str(profile.get("base_url") or "").strip()
    from cli.setup.openai_endpoint import _compatible_backend_display_name

    console_obj.print(
        f"  [dim]Using existing compatible profile:[/dim] {selected_label} "
        f"[dim]({_compatible_backend_display_name(selected_backend)}, {selected_endpoint or '—'})[/dim]"
    )
    args = dict(args)
    if not args["openai_compatible_backend"]:
        args["openai_compatible_backend"] = selected_backend or None
    if not args["openai_base_url"]:
        args["openai_base_url"] = selected_endpoint or None
    if not args["profile_default_model"]:
        args["profile_default_model"] = str(profile.get("default_model") or "").strip() or None
    if not label:
        label = selected_label or None
    return profile, args, label


def _resolve_all_provider_keys(
    cfg, selected_providers, args, selected_compatible_profile,
    resolved_openai_base_url, resolved_openai_backend,
) -> dict:
    resolved_keys: dict[str, str] = {}
    for prov in selected_providers:
        cli_key_for_provider = args["api_key"]
        if prov == "openai":
            cli_key_for_provider = args["openai_api_key"]
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
            cli_key_for_provider = None
        elif prov == "openai_compatible":
            cli_key_for_provider = args["profile_key"] or args["openai_api_key"]
            if not cli_key_for_provider and selected_compatible_profile:
                cli_key_for_provider = str(
                    selected_compatible_profile.get("api_key") or ""
                ).strip() or None
        chosen_key = _resolve_provider_key(
            cfg,
            provider=prov,
            cli_key=cli_key_for_provider,
            openai_base_url=resolved_openai_base_url if prov == "openai_compatible" else None,
            compatible_backend=resolved_openai_backend if prov == "openai_compatible" else None,
        )
        if prov == "anthropic" and (not chosen_key or not chosen_key.startswith("sk-ant-")):
            console.print(
                "\n  [yellow]Warning:[/yellow] Key doesn't start with 'sk-ant-'. "
                "Anthropic API keys typically begin with 'sk-ant-api03-'."
            )
            try:
                proceed = input("  Continue anyway? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\n  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
            if proceed not in ("y", "yes"):
                console.print("  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
        resolved_keys[prov] = chosen_key
    return resolved_keys
