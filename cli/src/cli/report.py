"""`sandwalk report` — list/publish/show generated markdown reports."""

from datetime import datetime
from pathlib import Path

import typer
from rich.table import Table

from cli.app import app, console
from cli.trace_helpers import _latest_report_path

report_app = typer.Typer(help="Generate and publish reports")
app.add_typer(report_app, name="report")


@report_app.command("list")
def report_list():
    """List available markdown reports."""
    from agent.config import Config

    cfg = Config.load()
    reports_dir = (
        Path(cfg.get("sandbox.output_dir")) / "reports"
        if cfg.get("sandbox.output_dir")
        else Path.cwd() / "outputs" / "reports"
    )
    if not reports_dir.exists():
        console.print("[dim]No reports directory found.[/dim]")
        raise typer.Exit()

    reports = sorted(reports_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        console.print("[dim]No reports found.[/dim]")
        raise typer.Exit()

    table = Table(title="Reports")
    table.add_column("#", style="dim")
    table.add_column("File", style="cyan")
    table.add_column("Size", style="dim")
    table.add_column("Modified")
    for i, r in enumerate(reports[:20], 1):
        size = r.stat().st_size
        size_str = f"{size / 1024:.1f}K" if size > 1024 else f"{size}B"
        mtime = datetime.fromtimestamp(r.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(str(i), r.name, size_str, mtime)
    console.print(table)


@report_app.command("publish")
def report_publish(
    path: Path | None = typer.Option(None, "--path", "-p", help="Markdown report to convert"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Output HTML path"),
):
    """Convert a markdown report to a shareable HTML page."""
    from agent.config import Config
    from reports.html import publish_report

    if path is None:
        cfg = Config.load()
        path = _latest_report_path(cfg.get("sandbox.output_dir"))
        if path is None:
            console.print("[yellow]No reports found. Run a query first.[/yellow]")
            raise typer.Exit(code=2)

    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(code=2)

    result = publish_report(path, out_path=out)
    console.print(f"[green]Published:[/green] {result}")


@report_app.command("show")
def report_show(
    path: Path | None = typer.Option(None, "--path", "-p", help="HTML report to open"),
):
    """Open an HTML report in the default browser."""
    import webbrowser

    from agent.config import Config
    from reports.html import publish_report

    if path is None:
        cfg = Config.load()
        md_path = _latest_report_path(cfg.get("sandbox.output_dir"))
        if md_path is None:
            console.print("[yellow]No reports found.[/yellow]")
            raise typer.Exit(code=2)
        html_path = md_path.with_suffix(".html")
        if not html_path.exists():
            html_path = publish_report(md_path)
            console.print(f"[dim]Auto-published: {html_path}[/dim]")
        path = html_path

    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(code=2)

    webbrowser.open(f"file://{path.resolve()}")
    console.print(f"[green]Opened in browser:[/green] {path}")
