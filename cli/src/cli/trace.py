"""`sandwalk trace diagnose` — inspect execution trace health."""

from pathlib import Path

import typer
from rich.table import Table

from cli.app import app, console
from cli.trace_helpers import _resolve_trace_path

trace_app = typer.Typer(help="Inspect and diagnose execution traces")
app.add_typer(trace_app, name="trace")


@trace_app.command("diagnose")
def trace_diagnose(
    path: Path | None = typer.Option(None, "--path", "-p", help="Path to a trace JSONL file"),
    session_id: str | None = typer.Option(
        None,
        "--session-id",
        "-s",
        help="Session ID (looks up ~/.sandwalk/traces/<id>.trace.jsonl)",
    ),
    as_json: bool = typer.Option(False, "--json", help="Print diagnostics as JSON"),
    show_queries: bool = typer.Option(
        False, "--show-queries", help="Show per-query diagnostics table"
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Exit non-zero if health issues are detected"
    ),
):
    """Diagnose trace health (query integrity, failures, synthesis lifecycle)."""
    from agent.trace import TraceLogger
    from cli.trace_helpers import _print_trace_diagnostics_table, _trace_has_issues

    trace_path = _resolve_trace_path(path, session_id)
    if trace_path is None:
        console.print("[yellow]No trace files found in ~/.sandwalk/traces[/yellow]")
        raise typer.Exit(code=2)
    if not trace_path.exists():
        console.print(f"[red]Trace file not found:[/red] {trace_path}")
        raise typer.Exit(code=2)

    trace = TraceLogger.load(trace_path)
    diag = trace.diagnostics()

    if as_json:
        console.print_json(data=diag)
    else:
        _print_trace_diagnostics_table(diag, title=f"Trace Diagnostics: {trace_path.name}")

        if show_queries:
            q_table = Table(title="Per-Query Diagnostics")
            q_table.add_column("#", style="cyan")
            q_table.add_column("Closed")
            q_table.add_column("Plans")
            q_table.add_column("Step OK")
            q_table.add_column("Step Fail")
            q_table.add_column("Retries")
            q_table.add_column("Synth start/end")
            q_table.add_column("Query")
            for q in diag["queries"]:
                q_table.add_row(
                    str(q["query_number"]),
                    "yes" if q["closed"] else "no",
                    str(q["plan_count"]),
                    str(q["step_complete_count"]),
                    str(q["step_fail_count"]),
                    str(q["step_retry_count"]),
                    f"{q['synthesize_start_count']}/{q['synthesize_end_count']}",
                    (q["query"] or "")[:80],
                )
            console.print(q_table)

    has_issues = _trace_has_issues(diag)
    if strict and has_issues:
        raise typer.Exit(code=2)
