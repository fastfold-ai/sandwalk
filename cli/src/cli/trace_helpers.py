"""Shared helpers for trace inspection, used by `trace` and `release-check`."""

import subprocess
from pathlib import Path

from rich.table import Table

from cli.app import console


def _latest_trace_path() -> Path | None:
    from agent.trace import TraceLogger

    traces_dir = TraceLogger.traces_dir()
    traces = list(traces_dir.glob("*.trace.jsonl"))
    if not traces:
        return None
    return max(traces, key=lambda p: p.stat().st_mtime)


def _resolve_trace_path(path: Path | None, session_id: str | None) -> Path | None:
    import typer

    from agent.trace import TraceLogger

    if path is not None and session_id is not None:
        console.print("[red]Use either --path or --session-id, not both.[/red]")
        raise typer.Exit(code=2)

    if path is not None:
        return path
    if session_id:
        return TraceLogger.traces_dir() / f"{session_id}.trace.jsonl"
    return _latest_trace_path()


def _latest_report_path(output_base: str | None = None) -> Path | None:
    reports_dir = (
        Path(output_base) / "reports" if output_base else Path.cwd() / "outputs" / "reports"
    )
    if not reports_dir.exists():
        return None
    reports = list(reports_dir.glob("*.md"))
    if not reports:
        return None
    return max(reports, key=lambda p: p.stat().st_mtime)


def _trace_has_issues(diag: dict) -> bool:
    return any(
        (
            diag.get("unclosed_queries"),
            diag.get("queries_with_no_plan"),
            diag.get("queries_with_no_completion"),
            diag.get("queries_with_synthesis_mismatch"),
        )
    )


def _print_trace_diagnostics_table(diag: dict, title: str):
    table = Table(title=title)
    table.add_column("Metric", style="cyan")
    table.add_column("Value")
    table.add_row("Session", diag.get("session_id", "(unknown)") or "(unknown)")
    table.add_row("Events", str(diag.get("event_count", 0)))
    table.add_row("Queries", str(diag.get("query_count", 0)))
    table.add_row(
        "Query starts / ends",
        f"{diag.get('query_start_count', 0)} / {diag.get('query_end_count', 0)}",
    )
    table.add_row("Step starts", str(diag.get("total_step_start_count", 0)))
    table.add_row("Step completes", str(diag.get("total_step_complete_count", 0)))
    table.add_row("Step fails", str(diag.get("total_step_fail_count", 0)))
    table.add_row("Step retries", str(diag.get("total_step_retry_count", 0)))
    table.add_row("Unclosed queries", str(diag.get("unclosed_queries", [])))
    table.add_row("Queries with failures", str(diag.get("queries_with_failures", [])))
    table.add_row("Queries with no plan", str(diag.get("queries_with_no_plan", [])))
    table.add_row(
        "Queries with no completion",
        str(diag.get("queries_with_no_completion", [])),
    )
    table.add_row(
        "Synthesis mismatches",
        str(diag.get("queries_with_synthesis_mismatch", [])),
    )
    console.print(table)


def _run_step_command(label: str, cmd: list[str], env: dict | None = None) -> bool:
    console.print(f"\n[bold cyan]{label}[/bold cyan]")
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if stdout:
        console.print(stdout)
    if stderr:
        style = "yellow" if proc.returncode == 0 else "red"
        console.print(stderr, style=style)
    if proc.returncode == 0:
        console.print(f"[green]PASS[/green] {label}")
        return True
    console.print(f"[red]FAIL[/red] {label} (exit={proc.returncode})")
    return False
