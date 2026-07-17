"""Plain-text provider selection fallback (no interactive checklist available)."""

import typer

from cli.app import console


def _prompt_setup_providers_text(options: list[str]) -> list[str]:
    """Plain-text fallback for `sandwalk setup` when the interactive checklist
    (questionary) cannot run — e.g. piped stdin, CI, or limited terminals.
    Users type provider names or short codes: "anthropic,xai" or "a,x".
    """
    alias_map = {
        "a": "anthropic",
        "anthropic": "anthropic",
        "o": "openai",
        "openai": "openai",
        "x": "xai",
        "xai": "xai",
        "grok": "xai",
        "g": "google",
        "google": "google",
        "gemini": "google",
        "m": "moonshot",
        "moonshot": "moonshot",
        "kimi": "moonshot",
        "n": "nvidia",
        "nvidia": "nvidia",
        "nemotron": "nvidia",
        "oc": "opencode",
        "opencode": "opencode",
        "opencode-go": "opencode",
        "go": "opencode",
        "k": "openai_compatible",
        "compatible": "openai_compatible",
        "openai-compatible": "openai_compatible",
        "openai_compatible": "openai_compatible",
        "all": "all",
        "both": "all",
    }

    while True:
        console.print("  [cyan]Select provider(s) to configure[/cyan]")
        console.print(
            "  [dim]Options:[/dim] anthropic (a), openai (o), xai (x), google (g), "
            "kimi/moonshot (m), nvidia (n), opencode (oc), openai_compatible (k), all"
        )
        try:
            raw = input("  Providers: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()

        if not raw:
            console.print("  [yellow]Select at least one provider.[/yellow]")
            continue

        tokens = [t for t in raw.replace(",", " ").split() if t]
        selected: set[str] = set()
        bad: list[str] = []
        for token in tokens:
            mapped = alias_map.get(token)
            if mapped == "all":
                selected.update(options)
            elif mapped in options:
                selected.add(mapped)
            else:
                bad.append(token)

        if bad:
            console.print(f"  [yellow]Invalid selection:[/yellow] {' '.join(bad)}")
            continue
        if not selected:
            console.print("  [yellow]Select at least one provider.[/yellow]")
            continue
        return [p for p in options if p in selected]
