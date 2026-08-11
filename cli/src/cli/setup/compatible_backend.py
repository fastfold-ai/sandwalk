"""Backend inference for OpenAI-compatible setup (endpoint/key heuristics)."""

import typer

from cli.app import console
from cli.setup.openai_endpoint import (
    _compatible_default_endpoint,
    _compatible_install_url,
    _is_openai_managed_base_url,
    _normalize_compatible_backend_name,
    _normalize_openai_base_url,
)


def _infer_openai_compatible_backend(base_url: str | None, key: str | None = None) -> str:
    """Infer compatible backend type from endpoint/key hints."""
    endpoint = str(base_url or "").strip().lower()
    secret = str(key or "").strip().lower()
    if secret.startswith("sk-unsloth-") or "8888" in endpoint:
        return "unsloth"
    if (
        secret.startswith("dsv4-")
        or secret.startswith("sk-ds4-")
        or "deepseek-v4" in endpoint
        or "deepseek4" in endpoint
        or "ds4" in endpoint
    ):
        return "ds4"
    if "1234" in endpoint or "lmstudio" in endpoint or "lm-studio" in endpoint:
        return "lm_studio"
    if (
        "8080" in endpoint
        or "llama.cpp" in endpoint
        or "llama-cpp" in endpoint
        or "llamacpp" in endpoint
    ):
        return "llama_cpp"
    if secret.startswith("sk-omlx-") or "omlx" in endpoint:
        return "omlx"
    if "11434" in endpoint or "ollama" in endpoint:
        return "ollama"
    if "8000" in endpoint:
        return "omlx"
    return "other"


def _prompt_openai_compatible_backend(default_backend: str = "ollama") -> str:
    """Prompt backend type for OpenAI-compatible setup."""
    normalized_default = _normalize_compatible_backend_name(default_backend)
    if normalized_default not in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}:
        normalized_default = "ollama"

    console.print("\n  [cyan]Endpoint type[/cyan]")
    console.print(f"    [1] Ollama (/api/tags) - {_compatible_install_url('ollama')}")
    console.print(f"    [2] Unsloth (/v1/models, auth) - {_compatible_install_url('unsloth')}")
    console.print(f"    [3] oMLX (/v1/models, auth) - {_compatible_install_url('omlx')}")
    console.print(f"    [4] DS4 (DeepSeek v4, /v1/models) - {_compatible_install_url('ds4')}")
    console.print(f"    [5] llama.cpp (/v1/models) - {_compatible_install_url('llama_cpp')}")
    console.print(f"    [6] LM Studio (/v1/models) - {_compatible_install_url('lm_studio')}")
    console.print("    [7] Other OpenAI-compatible (/v1/models then /api/tags)")
    default_num = {
        "ollama": "1",
        "unsloth": "2",
        "omlx": "3",
        "ds4": "4",
        "llama_cpp": "5",
        "lm_studio": "6",
        "other": "7",
    }[normalized_default]
    try:
        raw = input(f"  Select endpoint type [{default_num}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    if not raw:
        return normalized_default
    if raw in {"1", "ollama", "o"}:
        return "ollama"
    if raw in {"2", "unsloth", "u"}:
        return "unsloth"
    if raw in {"3", "omlx", "m"}:
        return "omlx"
    if raw in {"4", "ds4", "deepseek", "deepseek-v4"}:
        return "ds4"
    if raw in {"5", "llama.cpp", "llama_cpp", "llama-cpp", "llamacpp"}:
        return "llama_cpp"
    if raw in {"6", "lmstudio", "lm_studio", "lm-studio", "lm studio"}:
        return "lm_studio"
    if raw in {"7", "other", "custom", "k"}:
        return "other"
    console.print("  [dim]Invalid selection; using generic compatible mode.[/dim]")
    return "other"


def _resolve_openai_compatible_endpoint(
    cfg,
    cli_base_url: str | None = None,
    cli_backend: str | None = None,
) -> tuple[str, str]:
    """Resolve compatible endpoint URL and backend type for setup."""
    existing = _normalize_openai_base_url(cfg.get("llm.openai_base_url"))
    active = cfg.get_openai_profile()
    existing_key = (active or {}).get("api_key") if active and str(active.get("backend") or "").lower() != "openai" else None
    if not existing_key:
        existing_key = None
    configured_backend = _normalize_compatible_backend_name(
        str(cfg.get("llm.openai_compatible_backend") or "").strip().lower()
    )
    inferred_backend = _infer_openai_compatible_backend(existing, existing_key)
    default_backend = (
        configured_backend
        if configured_backend in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}
        else inferred_backend
    )
    selected_backend = _normalize_compatible_backend_name(cli_backend)
    if selected_backend not in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}:
        selected_backend = _prompt_openai_compatible_backend(default_backend=default_backend)

    if cli_base_url is not None:
        chosen = _normalize_openai_base_url(cli_base_url)
        if not chosen:
            chosen = _compatible_default_endpoint(selected_backend)
        if _is_openai_managed_base_url(chosen):
            console.print("  [yellow]OpenAI cloud URL detected; using compatible default endpoint instead.[/yellow]")
            chosen = _compatible_default_endpoint(selected_backend)
        return chosen, selected_backend

    if selected_backend != "other":
        default_endpoint = _compatible_default_endpoint(selected_backend)
    else:
        default_endpoint = existing if (existing and not _is_openai_managed_base_url(existing)) else "http://localhost:11434/v1"

    console.print("\n  [cyan]OpenAI endpoint setup[/cyan]")
    console.print(
        "  [dim]Examples: Ollama, Unsloth, oMLX, DS4, llama.cpp, LM Studio, vLLM, proxy gateways[/dim]"
    )
    try:
        entered = input(f"  Endpoint base URL [{default_endpoint}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    chosen = _normalize_openai_base_url(entered or default_endpoint)
    if not chosen or _is_openai_managed_base_url(chosen):
        chosen = default_endpoint
    return chosen, selected_backend
