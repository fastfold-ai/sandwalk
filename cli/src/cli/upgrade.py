"""`sandwalk upgrade` command and the shared execute_upgrade() helper."""

import subprocess
import sys

import typer
from rich.console import Console

from cli.app import app, console, spinner
from cli.banner_support import _has_fastfold_skills_installed
from cli.version_check import build_upgrade_command, resolve_upgrade_flavor


def _maybe_offer_fastfold_skills_install_after_upgrade(
    *,
    ui: Console,
    install_missing: bool = False,
    prompt_if_missing: bool = True,
) -> None:
    """Offer to install official Fastfold skills after a successful upgrade."""
    from cli.setup.skills_install import _install_skill_sources

    if _has_fastfold_skills_installed():
        return

    if install_missing:
        ui.print("\n[cyan]Installing official Fastfold skills...[/cyan]")
        _install_skill_sources(["fastfold-ai/skills"])
        return

    if not prompt_if_missing:
        return

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        ui.print(
            "\n  [dim]No official Fastfold skills detected. "
            "Install them with `sandwalk skills add fastfold-ai/skills`.[/dim]"
        )
        return

    try:
        answer = input(
            "\n  Install official Fastfold skills now? [Y/n] "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        ui.print("\n  [dim]Skipped Fastfold skills install.[/dim]")
        return

    if answer in {"n", "no"}:
        ui.print(
            "  [dim]Skipped. Add later with "
            "`sandwalk skills add fastfold-ai/skills`.[/dim]"
        )
        return

    ui.print("  [cyan]Installing official Fastfold skills...[/cyan]")
    _install_skill_sources(["fastfold-ai/skills"])


def execute_upgrade(
    console_obj: Console | None = None,
    cfg=None,
    *,
    install_missing_skills: bool = False,
    prompt_missing_skills: bool = True,
) -> bool:
    """Run uv tool upgrade with persisted (or fallback) install flavor."""
    ui = console_obj or console
    flavor = resolve_upgrade_flavor(cfg=cfg, persist=True)
    cmd = build_upgrade_command(flavor)
    ui.print("\n[bold cyan]Upgrading sandwalk[/bold cyan]")
    ui.print(f"[dim]Flavor:[/dim] {flavor}")
    ui.print(f"[dim]$ {' '.join(cmd)}[/dim]")

    try:
        with spinner("Upgrading via uv (this may take a moment)...", console=ui):
            proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        ui.print("[red]`uv` command not found. Install uv first: https://docs.astral.sh/uv/[/red]")
        return False
    except Exception as exc:
        ui.print(f"[red]Upgrade failed to start:[/red] {exc}")
        return False

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if stdout:
        ui.print(stdout)
    if stderr:
        ui.print(stderr, style="yellow" if proc.returncode == 0 else "red")

    if proc.returncode != 0:
        ui.print(f"[red]Upgrade failed[/red] (exit={proc.returncode}).")
        return False

    ui.print("[green]Upgrade complete.[/green] Restart `sandwalk` to use the new version.")
    _maybe_offer_fastfold_skills_install_after_upgrade(
        ui=ui,
        install_missing=install_missing_skills,
        prompt_if_missing=prompt_missing_skills,
    )
    ui.print("[cyan]Running skills-upgrade...[/cyan]")
    try:
        from agent.skills import GLOBAL_SKILLS_DIR, upgrade_skills

        with ui.status("[green]Syncing agent skills...[/green]", spinner="dots") as status:
            result = upgrade_skills(
                include_catalog=True,
                include_npx=True,
                progress=lambda msg: status.update(f"[green]{msg}[/green]"),
            )
    except Exception as exc:
        ui.print(f"[yellow]skills-upgrade failed:[/yellow] {exc}")
        return True

    if result["added"]:
        ui.print(f"  [green]Added:[/green] {', '.join(result['added'])}")
    if result["updated"]:
        ui.print(f"  [green]Updated:[/green] {', '.join(result['updated'])}")
    if result.get("npx_synced"):
        ui.print(
            f"  [green]npx-synced:[/green] {result['npx_synced']} project-local source(s)"
        )
    if result["failed"]:
        for source, reason in result["failed"]:
            ui.print(f"  [yellow]Failed:[/yellow] {source} — {reason}")
    ui.print(f"  [dim]{result['summary']}[/dim]")
    ui.print(f"  [dim]Location: {GLOBAL_SKILLS_DIR}[/dim]")
    return True


@app.command("upgrade")
def upgrade_cmd(
    install_skills: bool = typer.Option(
        False,
        "--install-skills",
        help="Auto-install official Fastfold skills if missing",
    ),
    skip_skills_prompt: bool = typer.Option(
        False,
        "--skip-skills-prompt",
        help="Skip the post-upgrade Fastfold skills prompt",
    ),
):
    """Upgrade sandwalk with uv tool install --upgrade."""
    from agent.config import Config

    cfg = Config.load()
    ok = execute_upgrade(
        console_obj=console,
        cfg=cfg,
        install_missing_skills=install_skills,
        prompt_missing_skills=not skip_skills_prompt,
    )
    if not ok:
        raise typer.Exit(code=1)
