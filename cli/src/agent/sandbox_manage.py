"""CLI helpers for sandbox backend selection (builtin vs Modal)."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from agent.config import Config

# CLI-only preference (mirrors agent.cli_specialist). Keeps interactive /
# `sandwalk sandbox` independent from the web dashboard's sandbox.backend.
CLI_SANDBOX_CONFIG_KEY = "agent.cli_sandbox"
_ALIASES = {
    "off": "builtin",
    "local": "builtin",
    "built-in": "builtin",
    "builtin": "builtin",
    "on": "modal",
    "modal": "modal",
    "remote": "modal",
}


def normalize_sandbox_backend(raw: Any) -> str:
    value = str(raw or "builtin").strip().lower()
    value = _ALIASES.get(value, value)
    if value not in {"builtin", "modal"}:
        raise ValueError("sandbox backend must be 'builtin' or 'modal'")
    return value


def get_sandbox_backend(config: Config | None = None) -> str:
    """Return the CLI sandbox backend. Default is Built-in unless Modal is set."""
    cfg = config or Config.load()
    raw = cfg.get(CLI_SANDBOX_CONFIG_KEY, "")
    if raw is None or str(raw).strip() == "":
        return "builtin"
    try:
        return normalize_sandbox_backend(raw)
    except ValueError:
        return "builtin"


def sandbox_toolbar_label(backend: str | None = None, config: Config | None = None) -> str:
    kind = backend or get_sandbox_backend(config)
    return "Modal" if kind == "modal" else "Built-in"


def set_sandbox_backend(backend: str, config: Config | None = None) -> str:
    cfg = config or Config.load()
    normalized = normalize_sandbox_backend(backend)
    if normalized == "modal":
        from agent.sandbox_probe import modal_tokens_present

        ok, detail = modal_tokens_present(cfg)
        if not ok:
            raise RuntimeError(
                detail
                or "Modal tokens missing. Set compute.modal_token_id / "
                "compute.modal_token_secret (Integrations → Modal)."
            )
    cfg.set(CLI_SANDBOX_CONFIG_KEY, normalized)
    cfg.save()
    return normalized


def toggle_sandbox_backend(config: Config | None = None) -> str:
    cfg = config or Config.load()
    current = get_sandbox_backend(cfg)
    target = "builtin" if current == "modal" else "modal"
    return set_sandbox_backend(target, cfg)


def handle_sandbox_argv(argv: list[str], console: Console, config: Config | None = None) -> None:
    """Interactive `/sandbox` and `sandwalk sandbox` command handler."""
    cfg = config or Config.load()
    parts = [str(p).strip() for p in argv if str(p).strip()]
    if parts and parts[0].lstrip("/").lower() == "sandbox":
        parts = parts[1:]

    action = (parts[0].lower() if parts else "status")
    rest = parts[1:] if len(parts) > 1 else []

    if action in {"help", "-h", "--help"}:
        console.print("  [bold]/sandbox[/bold] — choose Built-in or Modal sandbox")
        console.print("    /sandbox              Show current backend")
        console.print("    /sandbox builtin|off  Use local Built-in sandbox (default)")
        console.print("    /sandbox modal|on     Use Modal sandbox")
        console.print("    /sandbox toggle       Flip Built-in ↔ Modal")
        return

    if action in {"status", "show", "get"}:
        kind = get_sandbox_backend(cfg)
        label = sandbox_toolbar_label(kind)
        console.print(f"  Sandbox: [bold]{label}[/bold] ([cyan]{kind}[/cyan])")
        if kind == "builtin":
            console.print("  [dim]Default for CLI. Only Modal is shown in the status bar.[/dim]")
        if kind == "modal":
            from agent.sandbox_probe import modal_tokens_present

            ok, detail = modal_tokens_present(cfg)
            if ok:
                console.print("  [dim]Modal tokens configured.[/dim]")
            else:
                console.print(f"  [yellow]Modal tokens missing:[/yellow] {detail}")
        console.print("  [dim]Change with[/dim] /sandbox builtin|modal|toggle")
        return

    if action == "toggle":
        try:
            kind = toggle_sandbox_backend(cfg)
        except RuntimeError as exc:
            console.print(f"  [red]{exc}[/red]")
            return
        console.print(
            f"  Sandbox → [bold]{sandbox_toolbar_label(kind)}[/bold] ([cyan]{kind}[/cyan])"
        )
        return

    if action in _ALIASES or action in {"builtin", "modal"}:
        try:
            kind = set_sandbox_backend(action, cfg)
        except (RuntimeError, ValueError) as exc:
            console.print(f"  [red]{exc}[/red]")
            return
        console.print(
            f"  Sandbox → [bold]{sandbox_toolbar_label(kind)}[/bold] ([cyan]{kind}[/cyan])"
        )
        return

    if rest:
        console.print(f"  [yellow]Unknown sandbox args:[/yellow] {' '.join(parts)}")
    else:
        console.print(f"  [yellow]Unknown sandbox command:[/yellow] {action}")
    console.print("  [dim]Try[/dim] /sandbox help")
