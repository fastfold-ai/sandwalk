"""`sandwalk case-study` — run curated drug case studies."""

import typer
from rich.panel import Panel
from rich.table import Table

from cli.app import app, console

case_study_app = typer.Typer(help="Run curated drug case studies")
app.add_typer(case_study_app, name="case-study")


@case_study_app.command("list")
def case_study_list():
    """List available curated case studies."""
    from agent.case_studies import CASE_STUDIES

    table = Table(title="Case Studies")
    table.add_column("ID", style="cyan")
    table.add_column("Drug")
    table.add_column("Threads", style="dim")
    table.add_column("Description")
    for case_id, case in CASE_STUDIES.items():
        table.add_row(
            case_id,
            case.name,
            str(len(case.thread_goals)),
            case.description[:80] + ("..." if len(case.description) > 80 else ""),
        )
    console.print(table)


@case_study_app.command("run")
def case_study_run(
    case_id: str = typer.Argument(..., help="Case study ID (e.g., revlimid, gleevec)"),
    threads: int | None = typer.Option(
        None, "--threads", "-t", help="Number of parallel threads"
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="LLM model to use"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run a curated drug case study with multi-agent analysis."""
    from agent.case_studies import CASE_STUDIES, run_case_study
    from agent.config import Config
    from agent.session import Session
    from cli.banner import print_banner
    from cli.setup.wizard import setup_cmd
    from cli.trace_helpers import _latest_report_path
    from reports.html import publish_report

    if case_id not in CASE_STUDIES:
        available = ", ".join(sorted(CASE_STUDIES.keys()))
        console.print(f"[red]Unknown case study '{case_id}'.[/red] Available: {available}")
        raise typer.Exit(code=2)

    cfg = Config.load()
    if model:
        cfg.set("llm.model", model)

    llm_issue = cfg.llm_preflight_issue()
    if llm_issue:
        console.print("\n  [yellow]First-time setup required.[/yellow]\n")
        setup_cmd(api_key=None, openai_api_key=None, fastfold_api_key=None, provider=None)
        cfg = Config.load()
        if model:
            cfg.set("llm.model", model)
        llm_issue = cfg.llm_preflight_issue()
        if llm_issue:
            console.print(f"\n  [red]Setup incomplete:[/red] {llm_issue}")
            raise typer.Exit(code=2)

    session = Session(config=cfg, verbose=verbose)
    case = CASE_STUDIES[case_id]

    print_banner(cfg)
    console.print(
        Panel(
            f"[bold]{case.name}[/bold]\n[dim]{case.description}[/dim]",
            title="[cyan]Case Study[/cyan]",
            border_style="cyan",
        )
    )
    console.print()

    _result = run_case_study(session, case_id, n_threads=threads)

    # Auto-publish HTML
    md_path = _latest_report_path(cfg.get("sandbox.output_dir"))
    if md_path:
        html_path = publish_report(md_path)
        console.print(f"\n  [green]HTML report:[/green] {html_path}")

    console.print()
