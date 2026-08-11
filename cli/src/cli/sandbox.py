"""`sandwalk sandbox` — Local Sandbox / Modal Sandbox backend and probes."""

import json

import typer

from cli.app import app, console

sandbox_app = typer.Typer(
    help="Sandbox backend (Local Sandbox / Modal Sandbox) and Modal probes",
    invoke_without_command=True,
)
app.add_typer(sandbox_app, name="sandbox")


@sandbox_app.callback(invoke_without_command=True)
def sandbox_root(ctx: typer.Context):
    """Show the active sandbox backend (same as interactive /sandbox)."""
    if ctx.invoked_subcommand is not None:
        return
    from agent.sandbox_manage import handle_sandbox_argv

    handle_sandbox_argv(["status"], console)


@sandbox_app.command("status")
def sandbox_status_cmd():
    """Show the active sandbox backend (Local Sandbox or Modal Sandbox)."""
    from agent.sandbox_manage import handle_sandbox_argv

    handle_sandbox_argv(["status"], console)


@sandbox_app.command("builtin")
def sandbox_builtin_cmd():
    """Use Local Sandbox (default)."""
    from agent.sandbox_manage import handle_sandbox_argv

    handle_sandbox_argv(["builtin"], console)


@sandbox_app.command("modal")
def sandbox_modal_cmd():
    """Use Modal Sandbox (requires Modal tokens)."""
    from agent.sandbox_manage import handle_sandbox_argv

    handle_sandbox_argv(["modal"], console)


@sandbox_app.command("toggle")
def sandbox_toggle_cmd():
    """Flip between Local Sandbox and Modal Sandbox."""
    from agent.sandbox_manage import handle_sandbox_argv

    handle_sandbox_argv(["toggle"], console)


@sandbox_app.command("probe")
def sandbox_probe_cmd(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON",
    ),
    keep: bool = typer.Option(
        False,
        "--keep",
        help="Do not terminate the Modal sandbox after the probe",
    ),
):
    """Create a Modal sandbox, seed files, execute a probe skill, pull results."""
    from agent.sandbox_probe import run_modal_sandbox_probe

    report = run_modal_sandbox_probe(terminate=not keep)
    if json_output:
        console.print_json(json.dumps(report.to_dict()))
    else:
        for step in report.steps:
            mark = "[green]ok[/green]" if step.ok else "[red]fail[/red]"
            console.print(f"  {mark}  {step.name}: {step.detail}")
        if report.skipped:
            console.print(
                "\n[yellow]Skipped live Modal probe[/yellow] "
                "(set MODAL_TOKEN_ID / MODAL_TOKEN_SECRET or Integrations → Modal)."
            )
        elif report.ok:
            console.print("\n[green]Modal sandbox probe passed.[/green]")
        else:
            console.print("\n[red]Modal sandbox probe failed.[/red]")
    if not report.ok:
        raise typer.Exit(code=1)
