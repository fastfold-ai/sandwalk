"""`sandwalk auth` — manage local API key auth for serve / web UI."""

import typer

from cli.app import app, console

auth_app = typer.Typer(help="Manage local API key auth for serve / web UI")
app.add_typer(auth_app, name="auth")


@auth_app.command("status")
def auth_status_cmd():
    """Show whether API-key auth is enabled (does not print the secret)."""
    from agent_server.auth_settings import load_settings, settings_path

    settings = load_settings()
    console.print(f"  settings: [dim]{settings_path()}[/dim]")
    console.print(
        f"  auth_enabled: [{'green' if settings.auth_enabled else 'yellow'}]"
        f"{settings.auth_enabled}[/]"
    )
    console.print(
        f"  api_key_configured: [{'green' if settings.api_key_configured else 'yellow'}]"
        f"{settings.api_key_configured}[/]"
    )


@auth_app.command("show")
def auth_show_cmd():
    """Print the current API key (for copying into the web login)."""
    from agent_server.auth_settings import load_settings

    settings = load_settings()
    if not settings.api_key:
        console.print("  [yellow]No API key configured. Run `sandwalk auth generate`.[/yellow]")
        raise typer.Exit(code=1)
    if not settings.auth_enabled:
        console.print("  [dim]Auth is currently disabled (`sandwalk auth enable` to require it).[/dim]")
    console.print(settings.api_key)


@auth_app.command("generate")
def auth_generate_cmd():
    """Create a new API key (replaces any existing key) and print it."""
    from agent_server.auth_settings import (
        generate_api_key,
        load_settings,
        save_settings,
    )

    settings = load_settings()
    settings.api_key = generate_api_key()
    save_settings(settings)
    console.print("  [green]Generated new API key.[/green]")
    console.print(settings.api_key)
    if not settings.auth_enabled:
        console.print("  [dim]Auth is still disabled — run `sandwalk auth enable` to require login.[/dim]")


@auth_app.command("enable")
def auth_enable_cmd():
    """Require API key (or web login cookie) for /v1 and the dashboard."""
    from agent_server.auth_settings import ensure_api_key, load_settings, save_settings

    settings = ensure_api_key(load_settings())
    settings.auth_enabled = True
    save_settings(settings)
    console.print("  [green]Auth enabled.[/green]")
    console.print(f"  API key: {settings.api_key}")
    console.print("  [dim]Restart `sandwalk serve` if it is already running, then open the web UI.[/dim]")


@auth_app.command("disable")
def auth_disable_cmd():
    """Allow unauthenticated local /v1 and web UI access (development default)."""
    from agent_server.auth_settings import load_settings, save_settings

    settings = load_settings()
    settings.auth_enabled = False
    save_settings(settings)
    console.print("  [yellow]Auth disabled.[/yellow] Local requests no longer require an API key.")
    console.print("  [dim]Restart `sandwalk serve` if it is already running.[/dim]")


@auth_app.command("set")
def auth_set_cmd(
    key: str = typer.Argument(..., help="API key (≥4 printable chars, no whitespace)"),
):
    """Set the API key explicitly."""
    from agent_server.auth_settings import (
        AuthSettingsError,
        load_settings,
        save_settings,
        validate_api_key,
    )

    try:
        value = validate_api_key(key)
    except AuthSettingsError as exc:
        console.print(f"  [red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    settings = load_settings()
    settings.api_key = value
    save_settings(settings)
    console.print("  [green]API key updated.[/green]")
