"""Interactive OpenAI cloud-vs-compatible mode/endpoint prompts for setup."""

import sys

import typer

from cli.app import console
from cli.setup.openai_endpoint import _is_openai_managed_base_url, _normalize_openai_base_url


def _prompt_openai_endpoint_mode(default_mode: str = "cloud") -> str:
    """Prompt whether to use OpenAI cloud or custom compatible endpoint."""
    default_mode = "compatible" if str(default_mode).strip().lower() == "compatible" else "cloud"

    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            selector_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "highlighted": "noreverse bold",
                    "selected": "fg:#4caf50 bold",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )
            selected = questionary.select(
                "OpenAI setup mode",
                choices=[
                    questionary.Choice(
                        title="OpenAI cloud (api.openai.com)",
                        value="cloud",
                    ),
                    questionary.Choice(
                        title="OpenAI-compatible custom endpoint (Ollama/Unsloth/vLLM/LM Studio/proxy)",
                        value="compatible",
                    ),
                ],
                default=default_mode,
                instruction="(↑/↓ move, enter confirm)",
                style=selector_style,
                qmark="❯",
            ).ask()
            if selected is None:
                console.print("  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
            return "compatible" if selected == "compatible" else "cloud"
        except typer.Exit:
            raise
        except Exception:
            pass

    console.print("\n  [cyan]OpenAI setup mode[/cyan]")
    console.print("  [dim]Options:[/dim] cloud (c), compatible (k)")
    prompt_default = "compatible" if default_mode == "compatible" else "cloud"
    console.print(f"  [dim]Press Enter to keep default:[/dim] {prompt_default}")
    try:
        raw = input("  Mode: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    if not raw:
        return prompt_default
    if raw in {"compatible", "compat", "custom", "k"}:
        return "compatible"
    if raw in {"cloud", "openai", "c"}:
        return "cloud"
    console.print("  [yellow]Invalid mode selection; defaulting to cloud.[/yellow]")
    return "cloud"


def _resolve_openai_base_url(
    cfg,
    cli_base_url: str | None = None,
    force_mode: str | None = None,
) -> str | None:
    """Resolve OpenAI-compatible base URL from CLI/config/prompt.

    Returns None for OpenAI default endpoint to avoid redundant config writes.
    """
    mode_override = str(force_mode or "").strip().lower()

    if cli_base_url is not None:
        normalized = _normalize_openai_base_url(cli_base_url)
        if not normalized:
            return None
        if mode_override == "compatible":
            return normalized
        if _is_openai_managed_base_url(normalized):
            return None
        return normalized

    existing = _normalize_openai_base_url(cfg.get("llm.openai_base_url"))
    if mode_override in {"cloud", "compatible"}:
        mode = mode_override
    else:
        default_mode = "compatible" if (existing and not _is_openai_managed_base_url(existing)) else "cloud"
        mode = _prompt_openai_endpoint_mode(default_mode=default_mode)
    if mode != "compatible":
        return None
    default_endpoint = existing if (existing and not _is_openai_managed_base_url(existing)) else "http://localhost:11434/v1"
    console.print("\n  [cyan]OpenAI endpoint setup[/cyan]")
    console.print(
        "  [dim]Examples: OpenAI cloud, Ollama, Unsloth, oMLX, DS4, llama.cpp, LM Studio, vLLM, proxy gateways[/dim]"
    )

    try:
        entered = input(f"  Endpoint base URL [{default_endpoint}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    chosen = _normalize_openai_base_url(entered or default_endpoint)
    if not chosen or _is_openai_managed_base_url(chosen):
        return None
    return chosen
