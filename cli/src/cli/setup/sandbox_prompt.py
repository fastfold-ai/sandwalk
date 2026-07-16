"""Setup wizard step: choose Local vs Modal sandbox backend."""

import sys

import typer

from cli.app import console
from cli.setup.keys import _prompt_masked_secret


def _prompt_setup_sandbox(
    cfg,
    backend_arg: str | None = None,
    skip: bool = False,
) -> None:
    """Setup step: choose Local vs Modal sandbox (last config step)."""
    from agent.sandbox_probe import modal_tokens_present

    if skip:
        return

    current = str(cfg.get("sandbox.backend") or "builtin").strip().lower()
    if current not in {"builtin", "modal"}:
        current = "builtin"

    chosen = str(backend_arg or "").strip().lower() or None
    if chosen not in {None, "builtin", "modal", "local"}:
        console.print(
            f"  [yellow]Unknown sandbox backend:[/yellow] {backend_arg}. "
            "Use builtin or modal."
        )
        chosen = None
    if chosen == "local":
        chosen = "builtin"

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if chosen is None:
        if not interactive:
            console.print(
                "\n  [dim]Skipping sandbox setup (non-interactive). "
                f"Current backend: {current}.[/dim]"
            )
            return
        console.print("\n  [cyan]Sandbox[/cyan]")
        console.print(
            "  [dim]Where the agent runs code: Local Sandbox on this machine, "
            "or Modal in the cloud.[/dim]"
        )
        console.print(f"  [1] Local Sandbox  [dim](current: {current})[/dim]")
        console.print("  [2] Modal")
        console.print("  [3] Skip")
        try:
            pick = input("  Choose sandbox [1/2/3]: ").strip() or "3"
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if pick == "1":
            chosen = "builtin"
        elif pick == "2":
            chosen = "modal"
        else:
            console.print("  [dim]Sandbox unchanged.[/dim]")
            return

    if chosen == "modal":
        ok, detail = modal_tokens_present(cfg)
        if not ok and interactive:
            console.print(
                "  [yellow]Modal tokens not configured.[/yellow] "
                f"[dim]{detail}[/dim]"
            )
            try:
                token_id = _prompt_masked_secret(
                    "  Modal token id (Enter to keep Local): "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                token_id = ""
            if not token_id:
                chosen = "builtin"
            else:
                try:
                    token_secret = _prompt_masked_secret("  Modal token secret: ").strip()
                except (EOFError, KeyboardInterrupt):
                    token_secret = ""
                if not token_secret:
                    chosen = "builtin"
                else:
                    cfg.set("compute.modal_token_id", token_id)
                    cfg.set("compute.modal_token_secret", token_secret)
                    ok = True
        if chosen == "modal" and not ok:
            console.print(
                "  [yellow]Modal tokens missing — keeping Local Sandbox.[/yellow]"
            )
            chosen = "builtin"

    cfg.set("sandbox.backend", chosen)
    cfg.save()
    label = "Modal" if chosen == "modal" else "Local Sandbox"
    console.print(f"  [green]Sandbox backend:[/green] {label}")
