"""Interactive compatible-model selection for the setup wizard."""

import typer

from cli.app import console
from cli.setup.discovery_fetch import _fetch_compatible_models_for_setup
from cli.setup.keys import _prompt_openai_compatible_api_key


def _prompt_compatible_model_for_setup(
    cfg,
    base_url: str,
    backend: str,
    api_key: str | None = None,
) -> str | tuple[str, str | None]:
    """Prompt for compatible model selection in setup flow."""
    default_model = str(cfg.get("llm.model") or "").strip() or "llama3.1"
    retry_key_override: str | None = None
    effective_key = str(api_key or "").strip() or None
    discovered = _fetch_compatible_models_for_setup(base_url, backend=backend, api_key=effective_key)

    def _result_with_key(model_id: str) -> str | tuple[str, str | None]:
        if retry_key_override:
            return model_id, retry_key_override
        return model_id

    while not discovered:
        console.print("  [cyan]Model discovery options[/cyan]")
        console.print("    [1] Retry discovery with a new API key")
        console.print("    [2] Enter model ID manually")
        console.print("    [3] Cancel setup")
        try:
            raw_action = input("  Select option [2]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if raw_action in {"3", "cancel", "c", "q"}:
            console.print("  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if raw_action in {"", "2", "manual", "m"}:
            break
        if raw_action not in {"1", "retry", "r"}:
            console.print("  [dim]Invalid selection; switching to manual entry.[/dim]")
            break
        retry_key = _prompt_openai_compatible_api_key(backend=backend)
        if not retry_key:
            console.print("  [dim]Retry skipped; keeping current key.[/dim]")
            continue
        retry_key_override = retry_key
        effective_key = retry_key
        discovered = _fetch_compatible_models_for_setup(base_url, backend=backend, api_key=effective_key)

    if discovered:
        console.print("  [cyan]Available models[/cyan]")
        for idx, name in enumerate(discovered, 1):
            console.print(f"    [{idx}] {name}")
        manual_idx = len(discovered) + 1
        console.print(f"    [{manual_idx}] Enter custom model name")
        try:
            raw_choice = input("  Select model (number): ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if raw_choice.isdigit():
            selected = int(raw_choice)
            if 1 <= selected <= len(discovered):
                return _result_with_key(discovered[selected - 1])
            if selected != manual_idx:
                console.print("  [dim]Invalid selection; switching to manual entry.[/dim]")
        elif raw_choice:
            console.print("  [dim]Invalid selection; switching to manual entry.[/dim]")

    try:
        model_input = input(f"  Model ID [{default_model}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    selected_model = model_input or default_model
    return _result_with_key(selected_model)
