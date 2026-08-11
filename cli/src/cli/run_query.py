"""Single-query execution path shared by `sandwalk run` and case studies."""

from pathlib import Path
from uuid import uuid4

import typer
from rich.panel import Panel

from cli.app import console
from cli.banner import print_banner


def run_query(
    query: str,
    context: dict,
    output: Path | None,
    model: str | None,
    verbose: bool,
    agents: int | None = None,
):
    """Execute a single research query."""
    from agent.config import Config
    from agent.session import Session
    from cli.setup.wizard import setup_cmd

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

    print_banner(cfg)
    console.print(
        Panel(
            f"[bold]{query}[/bold]",
            title="[cyan]sandwalk[/cyan]",
            border_style="cyan",
        )
    )
    console.print()

    # Multi-agent mode
    if agents is not None and agents > 1:
        from agent.orchestrator import ResearchOrchestrator

        orchestrator = ResearchOrchestrator(session, n_threads=agents)
        result = orchestrator.run(query, context)

        if output:
            output.mkdir(parents=True, exist_ok=True)
            report_path = output / "report.md"
            report_path.write_text(result.to_markdown())
            console.print(f"\n  Report saved to {report_path}")

        console.print()
        return

    # Execute via Agent SDK runner (default) or legacy AgentLoop (fallback)
    use_sdk = cfg.get("agent.use_sdk", True)

    if use_sdk:
        from agent.runner import AgentRunner
        from agent_server.service import resolve_session_workspace
        from agent_server.store import AgentStore

        # One-shot CLI runs still need a session workspace so fold downloads
        # do not expand empty $SANDWALK_SESSION_WORKSPACE to /artifacts/...
        if not str(context.get("workspace_path") or "").strip():
            oneshot_id = str(uuid4())[:8]
            context = {
                **context,
                "workspace_path": str(
                    resolve_session_workspace(
                        oneshot_id, store=AgentStore(), persist=True
                    )
                ),
            }

        agent = AgentRunner(session)
        result = agent.run(query, context)
    else:
        from agent.loop import AgentLoop, ClarificationNeeded

        agent = AgentLoop(session)
        try:
            result = agent.run(query, context)
        except ClarificationNeeded as e:
            console.print(f"\n  [cyan]{e.clarification.question}[/cyan]")
            if e.clarification.suggestions:
                console.print(f"  [dim]e.g. {', '.join(e.clarification.suggestions[:3])}[/dim]")
            console.print(
                "\n  [dim]Tip: provide context with --smiles, --target, or --indication flags.[/dim]"
            )
            return

    # Output
    if output:
        output.mkdir(parents=True, exist_ok=True)
        report_path = output / "report.md"
        report_path.write_text(result.to_markdown())
        console.print(f"\n  Report saved to {report_path}")

    # Summary already streamed to stdout during synthesis
    console.print()
