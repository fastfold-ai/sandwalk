"""`sandwalk ssh` — manage SSH servers, remote command execution, Slurm status, and 1-click Remote-SSH bootstrap."""

from __future__ import annotations

import typer
from rich.table import Table

from cli.app import app, console

ssh_app = typer.Typer(
    help="Manage SSH servers, execute remote commands, inspect Slurm queues, and auto-bootstrap remote Sandwalk daemons.",
    invoke_without_command=True,
)
app.add_typer(ssh_app, name="ssh")


def _ssh_service():
    from agent_server.ssh_service import SshService
    from agent_server.store import AgentStore

    return SshService(AgentStore())


@ssh_app.callback(invoke_without_command=True)
def ssh_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    ssh_list_cmd()


@ssh_app.command("list")
def ssh_list_cmd() -> None:
    """List saved and ~/.ssh/config discovered SSH hosts."""
    svc = _ssh_service()
    hosts = svc.list_hosts(include_ssh_config=True)
    if not hosts:
        console.print("[dim]No SSH hosts found. Add one with `sandwalk ssh add user@host`.[/dim]")
        return
    table = Table(title="Sandwalk SSH Hosts")
    table.add_column("Alias", style="cyan", no_wrap=True)
    table.add_column("Target", style="bold")
    table.add_column("Source")
    table.add_column("Status")
    table.add_column("Platform / GPU")
    table.add_column("Workdir")
    for h in hosts:
        target_str = f"{h.user}@{h.host}:{h.port}" if h.user else f"{h.host}:{h.port}"
        plat = " ".join(filter(None, [h.platform, h.arch, h.gpu_summary])) or "—"
        table.add_row(
            h.alias,
            target_str,
            h.source,
            h.status,
            plat,
            h.default_workdir or "~",
        )
    console.print(table)


@ssh_app.command("add")
def ssh_add_cmd(
    target: str = typer.Argument(..., help="SSH target (e.g. 'user@hpc.edu' or 'ssh -p 2222 user@host')"),
    alias: str | None = typer.Option(None, "--alias", "-a", help="Friendly alias"),
    workdir: str | None = typer.Option(None, "--workdir", "-w", help="Default remote workspace folder"),
    remote_port: int = typer.Option(8787, "--remote-port", help="Remote Sandwalk server port"),
) -> None:
    """Save an SSH host in Sandwalk."""
    from agent_server.models.automations import CreateSshHostRequest

    svc = _ssh_service()
    host = svc.create_host(
        CreateSshHostRequest(
            target=target,
            alias=alias,
            default_workdir=workdir,
            remote_port=remote_port,
        )
    )
    console.print(
        f"[green]Added SSH host[/green] [bold]{host.alias}[/bold] ({host.user + '@' if host.user else ''}{host.host}:{host.port})"
    )


@ssh_app.command("probe")
def ssh_probe_cmd(
    host: str = typer.Argument(..., help="SSH host alias, ID, or user@host"),
) -> None:
    """Probe an SSH host (OS/arch, GPUs, Slurm availability, and Sandwalk daemon status)."""
    svc = _ssh_service()
    res = svc.probe_host(host)
    if not res.reachable:
        console.print(f"[red]Unreachable:[/red] {res.detail}")
        raise typer.Exit(code=1)
    console.print(
        f"[green]Connected[/green] to [bold]{res.hostname}[/bold] "
        f"({res.platform or 'Linux'} {res.arch or ''})"
    )
    console.print(f"  GPUs:             {res.gpu_summary or 'None detected'}")
    console.print(f"  Slurm (squeue):   {'Yes' if res.slurm_available else 'No'}")
    console.print(
        f"  Sandwalk CLI:     {res.sandwalk_version or ('Installed' if res.sandwalk_installed else 'Not installed')}"
    )
    console.print(f"  Remote Daemon:    {'Running' if res.daemon_running else 'Stopped'}")


@ssh_app.command("connect")
def ssh_connect_cmd(
    host: str = typer.Argument(..., help="SSH host alias, ID, or user@host"),
    workdir: str | None = typer.Option(None, "--workdir", "-w", help="Remote workspace folder"),
    no_tunnel: bool = typer.Option(False, "--no-tunnel", help="Skip local SSH tunnel creation"),
) -> None:
    """Auto-install Sandwalk remotely, start the persistent 24/7 daemon, and open an SSH tunnel."""
    from agent_server.models.automations import SshConnectRequest

    svc = _ssh_service()
    res = svc.connect_and_bootstrap(
        SshConnectRequest(
            host_id_or_target=host,
            auto_install=True,
            start_daemon=True,
            open_tunnel=not no_tunnel,
            enable_watchdog=True,
            default_workdir=workdir,
        )
    )
    for step in res.steps:
        color = "green" if step.status == "completed" else "red"
        console.print(f"  [{color}]{step.step}[/{color}]: {step.detail}")
    if res.local_url:
        console.print(f"\n[bold green]Remote Sandwalk ready at:[/bold green] {res.local_url}")


@ssh_app.command("exec")
def ssh_exec_cmd(
    host: str = typer.Argument(..., help="SSH host alias, ID, or user@host"),
    command: str = typer.Argument(..., help="Remote shell command to execute"),
    workdir: str | None = typer.Option(None, "--workdir", "-w", help="Remote working directory"),
) -> None:
    """Execute a command on a remote SSH server."""
    svc = _ssh_service()
    res = svc.exec_command(host, command, workdir=workdir)
    if res.stdout:
        console.print(res.stdout.rstrip())
    if res.stderr:
        console.print(f"[red]{res.stderr.rstrip()}[/red]")
    if res.exit_code != 0:
        raise typer.Exit(code=res.exit_code)


@ssh_app.command("slurm")
def ssh_slurm_cmd(
    host: str = typer.Argument(..., help="SSH host alias, ID, or user@host"),
) -> None:
    """Inspect active Slurm queue (`squeue`) on a remote cluster."""
    svc = _ssh_service()
    res = svc.get_slurm_status(host)
    if not res.slurm_available:
        console.print(f"[yellow]Slurm (squeue) not detected on {host}.[/yellow]")
        return
    if not res.jobs:
        console.print(f"[dim]No active Slurm jobs for current user on {host}.[/dim]")
        return
    table = Table(title=f"Slurm Queue on {host}")
    for col in ("Job ID", "Partition", "Name", "State", "Time", "Nodes", "Nodelist / Reason"):
        table.add_column(col)
    for j in res.jobs:
        table.add_row(
            j.job_id,
            j.partition,
            j.name,
            j.state,
            j.time_used,
            j.nodes,
            j.reason_or_nodelist,
        )
    console.print(table)
