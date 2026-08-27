"""Provider selection for the setup wizard (which providers to configure)."""

import sys

import typer

from cli.app import console
from cli.constants import SETUP_PROVIDER_ORDER
from cli.setup.providers_text_prompt import _prompt_setup_providers_text


def _parse_provider_list(raw: str) -> list[str]:
    """Parse provider list from CLI option, preserving canonical order."""
    alias_map = {
        "anthropic": "anthropic",
        "openai": "openai",
        "xai": "xai",
        "grok": "xai",
        "google": "google",
        "gemini": "google",
        "moonshot": "moonshot",
        "kimi": "moonshot",
        "nvidia": "nvidia",
        "nemotron": "nvidia",
        "opencode": "opencode",
        "opencode-go": "opencode",
        "opencode_go": "opencode",
        "go": "opencode",
        "deepseek": "deepseek",
        "minimax": "minimax",
        "mistral": "mistral",
        "qwen": "qwen",
        "dashscope": "qwen",
        "alibaba": "qwen",
        "together": "together",
        "together-ai": "together",
        "together_ai": "together",
        "openrouter": "openrouter",
        "open-router": "openrouter",
        "cerebras": "cerebras",
        "groq": "groq",
        "fireworks": "fireworks",
        "fireworks-ai": "fireworks",
        "bedrock": "bedrock",
        "aws": "bedrock",
        "amazon": "bedrock",
        "openai_compatible": "openai_compatible",
        "openai-compatible": "openai_compatible",
        "compatible": "openai_compatible",
    }
    requested = set()
    for part in str(raw or "").split(","):
        token = part.strip().lower()
        if not token:
            continue
        requested.add(alias_map.get(token, token))
    selected = [p for p in SETUP_PROVIDER_ORDER if p in requested]
    if not selected:
        valid = ", ".join(SETUP_PROVIDER_ORDER)
        console.print(f"[red]Invalid --provider value '{raw}'. Valid providers: {valid}[/red]")
        raise typer.Exit(code=2)
    return selected


def _prompt_setup_providers(default_provider: str) -> list[str]:
    """Interactive provider selector (arrow keys + space toggles)."""
    options = list(SETUP_PROVIDER_ORDER)
    labels = {
        "anthropic": "Anthropic",
        "openai": "OpenAI",
        "xai": "xAI (Grok)",
        "google": "Google Gemini",
        "moonshot": "Kimi",
        "nvidia": "NVIDIA",
        "opencode": "OpenCode Zen",
        "deepseek": "DeepSeek",
        "minimax": "MiniMax",
        "mistral": "Mistral",
        "qwen": "Qwen Cloud",
        "together": "Together AI",
        "openrouter": "OpenRouter",
        "cerebras": "Cerebras",
        "groq": "Groq",
        "fireworks": "Fireworks AI",
        "bedrock": "Amazon Bedrock (IAM)",
        "openai_compatible": "OpenAI-compatible custom endpoint",
    }
    _ = default_provider

    # Preferred UX in real terminals: questionary inline checklist.
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
                    "separator": "fg:#6c6c6c",
                    "disabled": "fg:#858585",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )

            choices = [
                questionary.Choice(
                    title=f"{labels.get(prov, prov.title())}",
                    value=prov,
                    checked=False,
                )
                for prov in options
            ]
            selected = questionary.checkbox(
                "Select provider(s) to configure",
                choices=choices,
                instruction="(↑/↓ move, space toggle, enter confirm)",
                validate=lambda answer: True if answer else "Select at least one provider.",
                style=selector_style,
                qmark="❯",
                pointer="▸",
            ).ask()
            if selected is None:
                console.print("  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
            normalized = {str(v).strip().lower() for v in selected}
            return [p for p in options if p in normalized]
        except typer.Exit:
            raise
        except Exception:
            # Fall back to text input when terminal capabilities are limited.
            pass

    # Plain-text fallback for `sandwalk setup` when the interactive checklist
    # (questionary) cannot run — e.g. piped stdin, CI, or limited terminals.
    return _prompt_setup_providers_text(options)


def _setup_provider_runtime_id(provider_id: str) -> str:
    """Map setup provider id to runtime llm.provider."""
    return "openai" if provider_id == "openai_compatible" else provider_id
