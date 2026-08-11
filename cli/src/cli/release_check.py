"""`sandwalk release-check` — production release gate."""

import os
from pathlib import Path

import typer
from rich.table import Table

from cli.app import app, console
from cli.trace_helpers import (
    _latest_trace_path,
    _print_trace_diagnostics_table,
    _run_step_command,
    _trace_has_issues,
)


@app.command("release-check")
def release_check_cmd(
    run_tests: bool = typer.Option(
        True, "--tests/--no-tests", help="Run local pytest regression suite"
    ),
    run_benchmark: bool = typer.Option(
        True, "--benchmark/--no-benchmark", help="Run strict knowledge benchmark gate"
    ),
    run_trace: bool = typer.Option(
        True, "--trace/--no-trace", help="Run strict diagnostics on latest trace"
    ),
    trace_path: Path | None = typer.Option(
        None, "--trace-path", help="Trace path for diagnostics"
    ),
    trace_required: bool = typer.Option(
        False, "--trace-required", help="Fail if no trace file is found"
    ),
    include_live: bool = typer.Option(
        False, "--live", help="Also run live API smoke + live E2E prompt matrix"
    ),
    matrix_limit: int = typer.Option(10, "--matrix-limit", help="Prompt limit for live E2E matrix"),
    matrix_strict: bool = typer.Option(
        True,
        "--matrix-strict/--no-matrix-strict",
        help="Enable strict assertions in live E2E matrix",
    ),
    matrix_max_failed: int = typer.Option(
        1, "--matrix-max-failed", help="Max failed prompts allowed in strict matrix mode"
    ),
    require_profile: str | None = typer.Option(
        None, "--require-profile", help="Require agent.profile to match (e.g. pharma)"
    ),
    pharma: bool = typer.Option(False, "--pharma", help="Enforce pharma deployment policy checks"),
):
    """Run a production release gate: doctor + tests + benchmark + trace diagnostics."""
    from agent.config import Config
    from agent.doctor import has_errors, run_checks, to_table
    from agent.trace import TraceLogger
    from kb.benchmarks import BenchmarkSuite

    failed = False

    console.print("\n[bold]Release Check[/bold]")

    cfg = Config.load()
    if pharma and not require_profile:
        require_profile = "pharma"

    if require_profile:
        expected = require_profile.strip().lower()
        actual = str(cfg.get("agent.profile", "research")).strip().lower()
        if actual != expected:
            console.print(f"[red]Profile mismatch:[/red] expected '{expected}', got '{actual}'.")
            failed = True

    if pharma:
        policy_issues = []
        if str(cfg.get("agent.synthesis_style", "standard")).strip().lower() != "pharma":
            policy_issues.append("agent.synthesis_style must be 'pharma'")
        if not bool(cfg.get("agent.quality_gate_strict", False)):
            policy_issues.append("agent.quality_gate_strict must be true")
        if bool(cfg.get("agent.enable_experimental_tools", False)):
            policy_issues.append("agent.enable_experimental_tools must be false")
        if bool(cfg.get("agent.enable_claude_code_tool", False)):
            policy_issues.append("agent.enable_claude_code_tool must be false")
        if policy_issues:
            console.print("[red]Pharma policy checks failed:[/red]")
            for issue in policy_issues:
                console.print(f"- {issue}")
            failed = True

    checks = run_checks(cfg)
    console.print(to_table(checks))
    if has_errors(checks):
        console.print("[red]Doctor checks have blocking errors.[/red]")
        failed = True

    if run_tests:
        ok = _run_step_command(
            "Local test suite",
            ["pytest", "-q", "tests", "-m", "not data_smoke and not e2e and not e2e_matrix"],
        )
        failed = failed or (not ok)

    if run_benchmark:
        suite = BenchmarkSuite.load()
        summary = suite.run()
        gate = suite.gate(summary, min_pass_rate=0.9)

        table = Table(title="Release Benchmark Gate")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")
        table.add_row("Total cases", str(summary["total_cases"]))
        table.add_row("Expected behavior matches", str(summary["expected_behavior_matches"]))
        table.add_row("Pass rate", str(summary["pass_rate"]))
        table.add_row("Gate", gate["message"])
        console.print(table)

        if not gate["ok"]:
            console.print("[red]Benchmark release gate failed.[/red]")
            failed = True

    if run_trace:
        resolved_trace = trace_path or _latest_trace_path()
        if resolved_trace is None or not resolved_trace.exists():
            msg = "No trace file found for diagnostics."
            if trace_required:
                console.print(f"[red]{msg}[/red]")
                failed = True
            else:
                console.print(f"[yellow]{msg}[/yellow]")
        else:
            trace = TraceLogger.load(resolved_trace)
            diag = trace.diagnostics()
            _print_trace_diagnostics_table(diag, title=f"Trace Diagnostics: {resolved_trace.name}")
            if _trace_has_issues(diag):
                console.print("[red]Trace diagnostics detected integrity issues.[/red]")
                failed = True

    if include_live:
        smoke_env = dict(os.environ)
        smoke_env["RUN_DATA_SMOKE"] = "1"
        smoke_env.setdefault("DATA_SMOKE_STRICT", "1")
        smoke_ok = _run_step_command(
            "Live data source smoke checks",
            ["pytest", "-q", "tests/test_api_smoke.py"],
            env=smoke_env,
        )
        failed = failed or (not smoke_ok)

        matrix_env = dict(os.environ)
        matrix_env["RUN_E2E_MATRIX"] = "1"
        matrix_env["E2E_MATRIX_LIMIT"] = str(max(1, matrix_limit))
        matrix_env["E2E_MATRIX_STRICT"] = "1" if matrix_strict else "0"
        matrix_env["E2E_MATRIX_MAX_FAILED_QUERIES"] = str(max(0, matrix_max_failed))
        matrix_ok = _run_step_command(
            "Live E2E prompt matrix",
            ["pytest", "-q", "tests/test_e2e_matrix.py", "--run-e2e"],
            env=matrix_env,
        )
        failed = failed or (not matrix_ok)

    if failed:
        console.print("\n[red]Release check failed.[/red]")
        raise typer.Exit(code=2)

    console.print("\n[green]Release check passed.[/green]")
