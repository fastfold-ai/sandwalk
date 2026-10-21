"""`sandwalk cron` & `sandwalk automations` — CLI management for scheduled automations."""

from __future__ import annotations

import asyncio
import subprocess

import typer
from rich.table import Table

from cli.app import app, console

cron_app = typer.Typer(
    help="Schedule and manage recurring agent workflows, cron jobs, and Slurm/SSH watchers.",
    invoke_without_command=True,
)
app.add_typer(cron_app, name="cron")
app.add_typer(cron_app, name="automations")


def _services():
    from agent_server.automations_service import AutomationsService
    from agent_server.ssh_service import SshService
    from agent_server.store import AgentStore

    store = AgentStore()
    ssh_svc = SshService(store)
    auto_svc = AutomationsService(store, ssh_service=ssh_svc)
    return store, auto_svc, ssh_svc


@cron_app.callback(invoke_without_command=True)
def cron_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    cron_list_cmd()


@cron_app.command("list")
def cron_list_cmd() -> None:
    """List all scheduled automations and cron jobs."""
    _, auto_svc, _ = _services()
    items = auto_svc.list_automations()
    if not items:
        console.print("[dim]No automations configured yet. Create one with `sandwalk cron create`.[/dim]")
        return
    table = Table(title="Sandwalk Automations (Cron)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Schedule")
    table.add_column("Mode")
    table.add_column("Status")
    table.add_column("Next Run")
    for item in items:
        status_str = item.last_status if item.enabled else "paused"
        next_str = (
            item.next_run_at.strftime("%Y-%m-%d %H:%M UTC")
            if item.next_run_at and item.enabled
            else "—"
        )
        table.add_row(
            item.id[:8],
            item.name,
            item.schedule_label,
            item.session_mode,
            status_str,
            next_str,
        )
    console.print(table)


@cron_app.command("templates")
def cron_templates_cmd() -> None:
    """List built-in starter templates (Slurm/HPC, Bio/CompChem, Memory/Wiki, Code/CI)."""
    _, auto_svc, _ = _services()
    table = Table(title="Automation Starter Templates")
    table.add_column("Template ID", style="cyan", no_wrap=True)
    table.add_column("Category")
    table.add_column("Name", style="bold")
    table.add_column("Schedule")
    for tpl in auto_svc.list_templates():
        table.add_row(tpl.id, tpl.category, tpl.name, tpl.schedule_label)
    console.print(table)


@cron_app.command("create")
def cron_create_cmd(
    schedule: str = typer.Argument(..., help="Schedule (e.g. 'every 15m', 'daily at 9am', '0 9 * * 1-5')"),
    prompt: str = typer.Argument("", help="Task prompt for the agent"),
    name: str | None = typer.Option(None, "--name", "-n", help="Automation name"),
    command: str | None = typer.Option(None, "--command", "-c", help="Shell/Slurm command"),
    mode: str = typer.Option("fresh", "--mode", "-m", help="'fresh', 'continue', or 'no_agent'"),
    specialist: str | None = typer.Option(None, "--specialist", help="Specialist slug or ID"),
    ssh_host: str | None = typer.Option(None, "--ssh", help="SSH host alias or user@host"),
    workdir: str | None = typer.Option(None, "--workdir", help="Local or remote working directory"),
    skill: list[str] | None = typer.Option(None, "--skill", "-s", help="Attach skill (repeatable)"),
    continuity: bool = typer.Option(False, "--continuity", help="Carry previous output into next run"),
    context_from: list[str] | None = typer.Option(None, "--context-from", help="Upstream automation ID"),
    wake_on_change: bool = typer.Option(False, "--wake-on-change", help="Only wake LLM when command stdout changes"),
    template: str | None = typer.Option(None, "--template", "-t", help="Starter template ID"),
) -> None:
    """Create a scheduled automation or cron job."""
    from agent_server.models.automations import CreateAutomationRequest

    store, auto_svc, ssh_svc = _services()
    resolved_ssh_id: str | None = None
    if ssh_host:
        resolved_ssh_id = ssh_svc.resolve_or_create_host(ssh_host).id

    resolved_spec_id: str | None = None
    if specialist:
        needle = specialist.strip().lower()
        for sp in store.list_specialists():
            if sp.id.lower() == needle or sp.slug.lower() == needle or sp.name.lower() == needle:
                resolved_spec_id = sp.id
                break

    created = auto_svc.create_automation(
        CreateAutomationRequest(
            name=name,
            prompt=prompt,
            command=command,
            schedule_expr=schedule,
            session_mode=mode if mode in {"fresh", "continue", "no_agent"} else "fresh",  # type: ignore[arg-type]
            specialist_id=resolved_spec_id,
            workdir=workdir if not resolved_ssh_id else None,
            ssh_host_id=resolved_ssh_id,
            remote_workdir=workdir if resolved_ssh_id else None,
            skill_names=list(skill or []),
            continuity=continuity,
            context_from=list(context_from or []),
            wake_on_change_only=wake_on_change,
            template_id=template,
        )
    )
    console.print(
        f"[green]Created automation[/green] [bold]{created.name}[/bold] "
        f"([cyan]{created.id[:8]}[/cyan]) · {created.schedule_label}"
    )


@cron_app.command("pause")
def cron_pause_cmd(ref: str = typer.Argument(..., help="Automation ID or name")) -> None:
    """Pause an automation."""
    _, auto_svc, _ = _services()
    updated = auto_svc.pause_automation(ref)
    if updated is None:
        console.print(f"[red]Automation not found:[/red] {ref}")
        raise typer.Exit(code=1)
    console.print(f"[yellow]Paused[/yellow] {updated.name} ({updated.id[:8]})")


@cron_app.command("resume")
def cron_resume_cmd(ref: str = typer.Argument(..., help="Automation ID or name")) -> None:
    """Resume a paused automation."""
    _, auto_svc, _ = _services()
    updated = auto_svc.resume_automation(ref)
    if updated is None:
        console.print(f"[red]Automation not found:[/red] {ref}")
        raise typer.Exit(code=1)
    console.print(f"[green]Resumed[/green] {updated.name} ({updated.id[:8]})")


@cron_app.command("remove")
def cron_remove_cmd(ref: str = typer.Argument(..., help="Automation ID or name")) -> None:
    """Delete an automation."""
    _, auto_svc, _ = _services()
    if not auto_svc.delete_automation(ref):
        console.print(f"[red]Automation not found:[/red] {ref}")
        raise typer.Exit(code=1)
    console.print(f"[green]Removed[/green] {ref}")


@cron_app.command("run")
def cron_run_cmd(
    ref: str = typer.Argument(..., help="Automation ID or name"),
    context: str | None = typer.Option(None, "--context", help="Transient run context"),
) -> None:
    """Trigger an automation immediately."""
    _, auto_svc, _ = _services()
    try:
        run = asyncio.run(
            auto_svc.trigger_automation(
                ref,
                trigger_source="cli",
                transient_context=context,
                wait=True,
            )
        )
    except KeyError:
        console.print(f"[red]Automation not found:[/red] {ref}")
        raise typer.Exit(code=1) from None
    console.print(
        f"[green]Run {run.id[:8]}[/green] finished with status [bold]{run.status}[/bold]"
    )
    if run.output_excerpt:
        console.print(run.output_excerpt)


@cron_app.command("tick")
def cron_tick_cmd(
    ensure_daemon: bool = typer.Option(
        False,
        "--ensure-daemon",
        help="Ensure background `sandwalk serve` daemon is running (used by crontab watchdog).",
    ),
    port: int = typer.Option(8787, "--port", help="Daemon port when --ensure-daemon is set."),
) -> None:
    """Run one scheduler tick (and optionally ensure the background server daemon is alive)."""
    if ensure_daemon:
        import urllib.request

        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/v1/health", timeout=2
            ) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass
    _, auto_svc, _ = _services()
    runs = asyncio.run(auto_svc.tick_once(catch_up_missed=True))
    if runs:
        console.print(f"Executed {len(runs)} due automation(s).")


@cron_app.command("sync-crontab")
def cron_sync_crontab_cmd(
    port: int = typer.Option(8787, "--port", help="Port for background sandwalk serve"),
) -> None:
    """Install a user crontab watchdog so scheduled jobs survive reboots on Linux/HPC."""
    watchdog_line = (
        f"* * * * * export PATH=$HOME/.local/bin:$HOME/.sandwalk/bin:/usr/local/bin:/usr/bin:/bin; "
        f"curl -fsS --max-time 2 http://127.0.0.1:{port}/v1/health >/dev/null 2>&1 || "
        f"(setsid nohup sandwalk serve --host 127.0.0.1 --port {port} >> $HOME/.sandwalk/logs/remote-serve.log 2>&1 < /dev/null &)"
    )
    cmd = (
        f'(crontab -l 2>/dev/null | grep -v "sandwalk serve --host 127.0.0.1 --port {port}" || true; '
        f'echo "{watchdog_line}") | crontab -'
    )
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if proc.returncode != 0:
        console.print(f"[red]Failed to update crontab:[/red] {proc.stderr}")
        raise typer.Exit(code=1)
    console.print("[green]Installed user crontab watchdog for Sandwalk Automations.[/green]")
