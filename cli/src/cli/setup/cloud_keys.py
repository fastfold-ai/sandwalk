"""Fastfold Cloud + Boltz API key prompts for the setup wizard."""

import os

import typer

from cli.app import console
from cli.constants import BOLTZ_API_KEYS_URL, FASTFOLD_CLOUD_API_KEYS_URL
from cli.setup.keys import _prompt_masked_secret


def _prompt_fastfold_cloud_api_key(cfg, cli_value: str | None = None) -> str | None:
    """Prompt for Fastfold AI Cloud API key, allowing users to keep/skip."""
    existing = cfg.get("api.fastfold_cloud_key") or os.environ.get("FASTFOLD_API_KEY")
    if isinstance(cli_value, str) and cli_value:
        return cli_value.strip() or None

    console.print()
    console.print(
        "  Fastfold AI Cloud API keys: "
        f"[link={FASTFOLD_CLOUD_API_KEYS_URL}]{FASTFOLD_CLOUD_API_KEYS_URL}[/link]"
    )
    if existing:
        masked = existing[:7] + "..." + existing[-4:] if len(existing) > 11 else "***"
        console.print(f"  Existing Fastfold key detected: [green]{masked}[/green]")
        try:
            keep = input("  Keep existing Fastfold key? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if keep in ("", "y", "yes"):
            return existing

    console.print("  Press Enter to skip this step.")
    try:
        key = _prompt_masked_secret("  Enter your Fastfold AI Cloud API key: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key or None


def _prompt_boltz_api_key(cfg, cli_value: str | None = None) -> str | None:
    """Prompt for Boltz API key, allowing users to keep/skip."""
    existing = cfg.get("api.boltz_api_key") or os.environ.get("BOLTZ_API_KEY")
    if isinstance(cli_value, str) and cli_value:
        return cli_value.strip() or None

    console.print()
    console.print(
        "  Boltz API keys: "
        f"[link={BOLTZ_API_KEYS_URL}]{BOLTZ_API_KEYS_URL}[/link]"
    )
    if existing:
        masked = existing[:7] + "..." + existing[-4:] if len(existing) > 11 else "***"
        console.print(f"  Existing Boltz key detected: [green]{masked}[/green]")
        try:
            keep = input("  Keep existing Boltz key? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if keep in ("", "y", "yes"):
            return existing

    console.print("  Press Enter to skip this step.")
    try:
        key = _prompt_masked_secret("  Enter your Boltz API key: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key or None
