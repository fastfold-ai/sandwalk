"""`sandwalk doctor` — environment and configuration health checks."""

import json
from pathlib import Path

import typer

from cli.app import app, console


@app.command("doctor")
def doctor_cmd(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of a table",
    ),
    export: Path | None = typer.Option(
        None,
        "--export",
        help="Write a diagnostics zip (system info, doctor report, redacted config, logs)",
    ),
):
    """Run environment and configuration health checks."""
    from agent.config import Config
    from agent.doctor import has_errors, run_checks, to_report, to_table
    from agent.session import Session

    cfg = Config.load()
    checks = run_checks(cfg, session=Session(config=cfg, mode="batch"))
    if export is not None:
        from _version import __version__
        from agent.diagnostics import build_diagnostics_zip

        data, default_name = build_diagnostics_zip(
            version=__version__,
            doctor_report=to_report(checks),
        )
        out = export.expanduser()
        if out.is_dir() or str(out).endswith(("/", "\\")):
            out = out / default_name
        elif out.suffix.lower() != ".zip":
            out = out.with_suffix(".zip")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        console.print(f"  [green]Wrote diagnostics bundle:[/green] {out}")

    if json_output:
        console.print_json(json.dumps(to_report(checks)))
    else:
        console.print(to_table(checks))

    if has_errors(checks):
        if not json_output:
            console.print(
                "\n[red]Blocking issues found.[/red] Fix errors above, then rerun `sandwalk doctor`."
            )
        raise typer.Exit(code=1)

    if not json_output:
        console.print("\n[green]No blocking issues found.[/green]")
