"""`sandwalk trace export` — package a reproducible run bundle."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import typer

from agent.config import CONFIG_DIR
from cli.app import console
from cli.trace import trace_app
from cli.trace_helpers import _latest_report_path, _resolve_trace_path


@trace_app.command("export")
def trace_export(
    path: Path | None = typer.Option(None, "--path", "-p", help="Path to a trace JSONL file"),
    session_id: str | None = typer.Option(
        None,
        "--session-id",
        "-s",
        help="Session ID (looks up ~/.sandwalk/traces/<id>.trace.jsonl)",
    ),
    report: Path | None = typer.Option(
        None, "--report", "-r", help="Optional markdown report to include"
    ),
    out_dir: Path | None = typer.Option(
        None, "--out-dir", help="Bundle output directory (default: ~/.sandwalk/exports)"
    ),
    zip_bundle: bool = typer.Option(True, "--zip/--no-zip", help="Also produce a zip archive"),
):
    """Export a reproducible run bundle (trace, diagnostics, report, metadata)."""
    from agent.config import Config
    from agent.trace import TraceLogger
    from agent.trajectory import Trajectory

    trace_path = _resolve_trace_path(path, session_id)
    if trace_path is None:
        console.print("[yellow]No trace files found in ~/.sandwalk/traces[/yellow]")
        raise typer.Exit(code=2)
    if not trace_path.exists():
        console.print(f"[red]Trace file not found:[/red] {trace_path}")
        raise typer.Exit(code=2)

    trace = TraceLogger.load(trace_path)
    diag = trace.diagnostics()

    cfg = Config.load()
    resolved_report = report
    if resolved_report is None:
        resolved_report = _latest_report_path(cfg.get("sandbox.output_dir"))
    if resolved_report is not None and not resolved_report.exists():
        console.print(f"[red]Report file not found:[/red] {resolved_report}")
        raise typer.Exit(code=2)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    base = out_dir or (CONFIG_DIR / "exports")
    bundle_dir = base / f"ct_run_bundle_{trace.session_id or 'session'}_{ts}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    trace_copy = bundle_dir / "trace.jsonl"
    shutil.copy2(trace_path, trace_copy)
    (bundle_dir / "trace.txt").write_text(trace.to_text(), encoding="utf-8")
    (bundle_dir / "trace_diagnostics.json").write_text(
        json.dumps(diag, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (bundle_dir / "query_summaries.json").write_text(
        json.dumps(trace.query_summaries(), indent=2),
        encoding="utf-8",
    )

    copied_report = None
    if resolved_report is not None:
        copied_report = bundle_dir / "report.md"
        shutil.copy2(resolved_report, copied_report)

    copied_session = None
    session_file = None
    if trace.session_id:
        session_file = Trajectory.sessions_dir() / f"{trace.session_id}.jsonl"
    if session_file is not None and session_file.exists():
        copied_session = bundle_dir / "session.jsonl"
        shutil.copy2(session_file, copied_session)

    manifest = {
        "generated_at_utc": ts,
        "session_id": trace.session_id,
        "source_trace": str(trace_path),
        "included_files": {
            "trace_jsonl": str(trace_copy),
            "trace_txt": str(bundle_dir / "trace.txt"),
            "trace_diagnostics_json": str(bundle_dir / "trace_diagnostics.json"),
            "query_summaries_json": str(bundle_dir / "query_summaries.json"),
            "report_md": str(copied_report) if copied_report else None,
            "session_jsonl": str(copied_session) if copied_session else None,
        },
        "note": (
            "If report was auto-selected, it is the latest markdown report by mtime "
            "from sandbox.output_dir/reports."
            if report is None
            else "Report path explicitly provided."
        ),
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    console.print(f"[green]Bundle exported:[/green] {bundle_dir}")
    if copied_report:
        console.print(f"[dim]Included report:[/dim] {resolved_report}")
    else:
        console.print("[yellow]No report included (none found/provided).[/yellow]")

    if zip_bundle:
        archive = shutil.make_archive(str(bundle_dir), "zip", root_dir=bundle_dir)
        console.print(f"[green]Zip archive:[/green] {archive}")
