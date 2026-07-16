"""`sandwalk run` (hidden) — main single-query / interactive dispatch command."""

from pathlib import Path

import typer

from _version import __version__
from cli.app import app, console


@app.command("run", hidden=True)
def run_cmd(
    query_parts: list[str] = typer.Argument(None, help="Research question to investigate"),
    smiles: str | None = typer.Option(None, "--smiles", "-s", help="Compound SMILES string"),
    target: str | None = typer.Option(
        None, "--target", "-t", help="Target protein (UniProt ID or gene symbol)"
    ),
    indication: str | None = typer.Option(
        None, "--indication", "-i", help="Cancer type / indication"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output directory for reports"
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="LLM model to use"),
    agents: int | None = typer.Option(
        None, "--agents", "-a", help="Run with N parallel research agents"
    ),
    resume: str | None = typer.Option(
        None, "--resume", "-r", help="Resume a previous session (ID or 'last')"
    ),
    continue_last: bool = typer.Option(
        False, "--continue", "-c", help="Continue the most recent session"
    ),
    specialist: str | None = typer.Option(
        None,
        "--specialist",
        help="Specialist slug/name/id for this run (overrides CLI active specialist)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    version: bool = typer.Option(False, "--version", "-V", help="Show version"),
):
    """
    sandwalk — a thinking path for open science.

    Run without arguments for interactive mode.
    Pass a question for single-query mode.
    """
    from cli.interactive import run_interactive
    from cli.run_query import run_query

    if version:
        console.print(f"sandwalk v{__version__}")
        raise typer.Exit()

    query = " ".join(query_parts).strip() if query_parts else None

    # Build context from flags
    context = {}
    if smiles:
        context["compound_smiles"] = smiles
    if target:
        context["target"] = target
    if indication:
        context["indication"] = indication

    from agent.specialists_manage import (
        apply_specialist_to_context,
        get_active_specialist,
        resolve_specialist_ref,
        set_active_specialist_ref,
    )

    if specialist:
        resolved = resolve_specialist_ref(specialist)
        if resolved is None:
            console.print(f"  [red]Specialist not found:[/red] {specialist}")
            raise typer.Exit(code=2)
        # Persist for interactive follow-ups in this CLI install.
        set_active_specialist_ref(resolved.slug)
        console.print(
            f"  [dim]Specialist:[/dim] [bold]{resolved.name}[/bold] "
            f"[dim]({resolved.slug})[/dim]"
        )
        if query:
            context = apply_specialist_to_context(context, resolved)
    else:
        active = get_active_specialist()
        if active is not None:
            console.print(
                f"  [dim]Specialist:[/dim] [bold]{active.name}[/bold] "
                f"[dim]({active.slug})[/dim]"
            )
            if query:
                context = apply_specialist_to_context(context, active)

    # Determine session resume
    resume_id = None
    if continue_last:
        resume_id = "last"
    elif resume:
        resume_id = resume

    if query:
        # Single query mode
        run_query(query, context, output, model, verbose, agents=agents)
    else:
        # Interactive mode
        run_interactive(context, output, model, verbose, resume_id=resume_id)
