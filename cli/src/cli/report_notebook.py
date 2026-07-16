"""`sandwalk report notebook` — export an agent trace as a Jupyter notebook."""

from pathlib import Path

import typer

from cli.app import console
from cli.report import report_app


@report_app.command("notebook")
def report_notebook(
    session: str | None = typer.Option(
        None, "--session", "-s", help="Session ID (prefix or full). Default: most recent"
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Output notebook path"),
    html: bool = typer.Option(False, "--html", help="Also export as HTML"),
):
    """Export an agent trace as a Jupyter notebook (.ipynb)."""
    import re

    from agent.trace_store import TraceStore

    # Find trace file
    trace_path = TraceStore.find_trace(session)
    if trace_path is None:
        console.print(
            "[yellow]No trace files found. Run a query first to generate a trace.[/yellow]"
        )
        raise typer.Exit(code=2)

    console.print(f"  [dim]Trace:[/dim] {trace_path.name}")

    # Lazy import nbformat
    try:
        from reports.notebook import save_notebook, trace_to_notebook
    except ImportError:
        console.print("[red]nbformat is required. Install with:[/red] pip install nbformat")
        raise typer.Exit(code=2)

    # Convert trace to notebook
    nb = trace_to_notebook(trace_path)

    # Determine output path
    if out is None:
        from agent.config import Config

        cfg = Config.load()
        reports_dir = (
            Path(cfg.get("sandbox.output_dir")) / "reports"
            if cfg.get("sandbox.output_dir")
            else Path.cwd() / "outputs" / "reports"
        )
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", trace_path.stem.replace(".trace", "")).strip("_")
        out = reports_dir / f"{slug}.ipynb"

    out_path = save_notebook(nb, out)
    console.print(f"  [green]Notebook:[/green] {out_path}")

    # Optional HTML export
    if html:
        try:
            from nbconvert import HTMLExporter

            exporter = HTMLExporter()
            html_body, _ = exporter.from_notebook_node(nb)
            html_path = out_path.with_suffix(".html")
            html_path.write_text(html_body, encoding="utf-8")
            console.print(f"  [green]HTML:[/green] {html_path}")
        except ImportError:
            console.print(
                "[yellow]nbconvert not installed. Falling back to markdown-based HTML.[/yellow]\n"
                "  [dim]Install with: pip install nbconvert[/dim]"
            )
            # Fall back to existing HTML renderer on markdown cells
            from reports.html import render_html_report

            md_parts = [c.source for c in nb.cells if c.cell_type == "markdown"]
            md_text = "\n\n".join(md_parts)
            html_content = render_html_report(md_text, title="Fastfold Notebook Export")
            html_path = out_path.with_suffix(".html")
            html_path.write_text(html_content, encoding="utf-8")
            console.print(f"  [green]HTML (markdown only):[/green] {html_path}")
