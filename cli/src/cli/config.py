"""`sandwalk config` and `sandwalk keys` — configuration management."""

import typer

from cli.app import app, console

config_app = typer.Typer(help="Manage sandwalk configuration")
app.add_typer(config_app, name="config")


@config_app.command("set")
def config_set(key: str, value: str):
    """Set a configuration value."""
    from agent.config import Config

    cfg = Config.load()
    try:
        cfg.set(key, value)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)
    cfg.save()
    if key == "agent.profile":
        console.print(
            f"  [green]Set[/green] {key} = {cfg.get('agent.profile')} (applied preset settings)"
        )
    else:
        console.print(f"  [green]Set[/green] {key} = {value}")


@config_app.command("unset")
def config_unset(key: str):
    """Unset a configuration value (revert to default/env fallback)."""
    from agent.config import Config

    cfg = Config.load()
    cfg.unset(key)
    cfg.save()
    console.print(f"  [green]Unset[/green] {key}")


@config_app.command("get")
def config_get(key: str):
    """Get a configuration value."""
    from agent.config import Config

    cfg = Config.load()
    val = cfg.get(key)
    console.print(f"  {key} = {val}")


@config_app.command("show")
def config_show():
    """Show all configuration."""
    from agent.config import Config

    cfg = Config.load()
    console.print(cfg.to_table())


@config_app.command("validate")
def config_validate():
    """Validate configuration and report issues."""
    from agent.config import Config

    cfg = Config.load()
    issues = cfg.validate()
    if not issues:
        console.print("[green]Configuration is valid. No issues found.[/green]")
        return
    console.print(f"[yellow]Found {len(issues)} issue(s):[/yellow]")
    for issue in issues:
        console.print(f"  - {issue}")
    raise typer.Exit(code=2)


@app.command("keys")
def keys_cmd():
    """Show status of optional API keys and what they unlock."""
    from agent.config import Config

    cfg = Config.load()
    console.print(cfg.keys_table())
