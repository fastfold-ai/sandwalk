"""Interactive-mode entry point (terminal REPL) for `sandwalk`."""

from pathlib import Path

from cli.app import console
from cli.banner import print_banner
from cli.banner_support import _start_skills_update_check
from cli.upgrade import _maybe_offer_fastfold_skills_install_after_upgrade
from cli.version_check import _start_upgrade_check_refresh


def run_interactive(
    context: dict,
    output: Path | None,
    model: str | None,
    verbose: bool,
    resume_id: str = None,
):
    """Run interactive session."""
    from agent.config import Config

    def _pin_startup_to_bottom() -> None:
        """Place startup banner/prompt near terminal bottom like Claude Code."""
        try:
            rows = int(getattr(console.size, "height", 0) or 0)
        except Exception:
            rows = 0
        # Approximate visible startup footprint:
        # mark (~6 lines) + spacing + first prompt/separator.
        startup_lines = 11
        spacer = max(0, rows - startup_lines)
        console.clear()
        if spacer:
            console.print("\n" * spacer, end="")

    cfg = Config.load()
    if model:
        cfg.set("llm.model", model)

    llm_issue = cfg.llm_preflight_issue()
    if llm_issue:
        from cli.setup.wizard import setup_cmd

        console.print("\n  [yellow]First-time setup required.[/yellow]\n")
        setup_cmd(api_key=None, openai_api_key=None, fastfold_api_key=None, provider=None)
        # Reload config after setup
        cfg = Config.load()
        llm_issue = cfg.llm_preflight_issue()
        if llm_issue:
            console.print(f"\n  [red]Setup incomplete:[/red] {llm_issue}")
            return

    _pin_startup_to_bottom()
    print_banner(cfg)
    _maybe_offer_fastfold_skills_install_after_upgrade(
        ui=console,
        install_missing=False,
        prompt_if_missing=True,
    )
    # Refresh the skills-update cache in the background so the next boot's banner
    # notice is fresh — no network on this boot's path.
    _start_skills_update_check()
    _start_upgrade_check_refresh()

    console.print()

    import faulthandler
    import traceback

    from agent.diagnostics import ensure_cli_logging_configured
    from ui.terminal import InteractiveTerminal

    # File-only logging so runner WARNING+tracebacks don't hit stderr and
    # shatter the fullscreen transcript TUI (Python lastResort → stderr).
    ensure_cli_logging_configured()

    # Surface native crashes (segfaults) that otherwise look like a silent exit.
    faulthandler.enable()

    terminal = InteractiveTerminal(config=cfg, verbose=verbose)
    try:
        terminal.run(initial_context=context, resume_id=resume_id)
    except (KeyboardInterrupt, EOFError):
        console.print("\n  [dim]Bye![/dim]")
    except Exception:
        console.print("\n  [red]CLI crashed with an unhandled error:[/red]")
        console.print(traceback.format_exc())
        raise
