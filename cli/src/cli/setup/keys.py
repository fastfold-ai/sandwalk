"""Provider API key prompts used by the setup wizard."""

import sys

import typer

from cli.app import console
from cli.setup.openai_endpoint import _normalize_compatible_backend_name


def _prompt_api_key() -> str:
    """Prompt user for API key with masked input."""
    console.print(
        "  Get your key at: [link=https://console.anthropic.com/settings/keys]https://console.anthropic.com/settings/keys[/link]"
    )
    console.print()
    try:
        key = _prompt_masked_secret("  Enter your Anthropic API key: ")
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key.strip()


def _prompt_provider_api_key(label: str, signup_url: str) -> str:
    """Prompt for a first-party provider API key (xAI / Google Gemini)."""
    console.print(f"  Get your key at: [link={signup_url}]{signup_url}[/link]")
    console.print()
    try:
        key = _prompt_masked_secret(f"  Enter your {label} API key: ")
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key.strip()


def _prompt_openai_api_key() -> str:
    """Prompt user for OpenAI API key with masked input."""
    console.print(
        "  Get your key at: [link=https://platform.openai.com/api-keys]https://platform.openai.com/api-keys[/link]"
    )
    console.print()
    try:
        key = _prompt_masked_secret("  Enter your OpenAI API key: ")
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key.strip()


def _prompt_openai_compatible_api_key(backend: str = "other") -> str:
    """Prompt for OpenAI-compatible API key with backend-aware hints."""
    backend_type = _normalize_compatible_backend_name(backend)
    if backend_type == "unsloth":
        console.print(
            "  Unsloth Studio: [link=http://localhost:8888]http://localhost:8888[/link]"
        )
        console.print("  [dim]Use your Unsloth key (often starts with sk-unsloth-).[/dim]")
    elif backend_type == "ollama":
        console.print(
            "  [dim]Ollama often accepts placeholder keys (for example: ollama).[/dim]"
        )
    elif backend_type == "omlx":
        console.print(
            "  oMLX endpoint: [link=http://localhost:8000]http://localhost:8000[/link]"
        )
        console.print("  [dim]Use your oMLX key if your endpoint requires auth.[/dim]")
    elif backend_type == "ds4":
        console.print(
            "  DS4 endpoint: [link=http://localhost:8000]http://localhost:8000[/link]"
        )
        console.print("  [dim]Use your DS4 token if your server requires auth.[/dim]")
    elif backend_type == "llama_cpp":
        console.print(
            "  llama.cpp endpoint: [link=http://localhost:8080]http://localhost:8080[/link]"
        )
        console.print("  [dim]llama.cpp servers often run without auth, but API keys are supported.[/dim]")
    elif backend_type == "lm_studio":
        console.print(
            "  LM Studio endpoint: [link=http://localhost:1234]http://localhost:1234[/link]"
        )
        console.print("  [dim]LM Studio OpenAI-compatible server usually uses /v1 models discovery.[/dim]")
    else:
        console.print(
            "  [dim]Using a custom OpenAI-compatible endpoint key.[/dim]"
        )
    console.print()
    try:
        key = _prompt_masked_secret("  Enter your OpenAI-compatible API key: ")
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key.strip()


def _prompt_openai_api_key_with_default(default_key: str = "ollama") -> str:
    """Prompt for OpenAI-compatible API key with a default fallback."""
    console.print(
        "  [dim]OpenAI-compatible endpoint detected.[/dim] "
        f"Press Enter to use default key: [green]{default_key}[/green]"
    )
    console.print()
    try:
        key = _prompt_masked_secret(f"  Enter API key [{default_key}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key or default_key


def _prompt_masked_secret(message: str) -> str:
    """Prompt for secrets with visible masked characters while typing."""
    # Prefer questionary in interactive terminals (shows mask while typing).
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            secret_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )
            value = questionary.password(
                message.strip(),
                instruction="(input is masked)",
                qmark="❯",
                style=secret_style,
            ).ask()
            if value is None:
                raise KeyboardInterrupt
            return str(value)
        except (EOFError, KeyboardInterrupt):
            raise
        except Exception:
            pass

    # Fallback for non-interactive terminals.
    import getpass

    return getpass.getpass(message)
