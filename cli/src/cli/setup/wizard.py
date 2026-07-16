"""`sandwalk setup` — interactive wizard orchestrator."""
# ruff: noqa: I001 — hand-packed imports (kept compact to fit the line-count cap)

import typer
from rich.panel import Panel

from cli.app import app, console
from cli.setup.boltz_install import _prompt_install_boltz_stack
from cli.setup.cloud_keys import _prompt_boltz_api_key, _prompt_fastfold_cloud_api_key
from cli.setup.datasets_prompt import _prompt_install_datasets
from cli.setup.mcp_prompt import _prompt_setup_mcps
from cli.setup.openai_endpoint import _normalize_compatible_backend_name
from cli.setup.sandbox_prompt import _prompt_setup_sandbox
from cli.setup.skills_prompt import _prompt_install_skills
from cli.setup.wizard_flow import _setup_check_foundry_shortcut, _setup_resolve_providers_and_keys
from cli.setup.wizard_persist import _setup_persist_provider_choice, _setup_print_provider_summary
from cli.setup.wizard_steps import _clean_setup_option_defaults, _setup_finish, _setup_run_health_check


@app.command("setup")
def setup_cmd(
    api_key: str | None = typer.Option(
        None, "--api-key", help="Anthropic API key (non-interactive mode)"
    ),
    openai_api_key: str | None = typer.Option(
        None, "--openai-api-key", help="OpenAI API key (non-interactive mode)"
    ),
    openai_base_url: str | None = typer.Option(
        None,
        "--openai-base-url",
        help="OpenAI-compatible base URL (e.g. http://localhost:11434/v1)",
    ),
    openai_compatible_backend: str | None = typer.Option(
        None,
        "--openai-compatible-backend",
        help="Compatible backend type: ollama, unsloth, omlx, ds4, llama_cpp, lm_studio, or other",
    ),
    profile_label: str | None = typer.Option(
        None,
        "--profile-label",
        help="Label for the OpenAI-compatible profile to create/update",
    ),
    profile_template: str | None = typer.Option(
        None,
        "--profile-template",
        help="OpenAI-compatible template: ollama, unsloth, omlx, ds4, llama_cpp, lm_studio, or other",
    ),
    profile_endpoint: str | None = typer.Option(
        None,
        "--profile-endpoint",
        help="Profile endpoint URL (alias of --openai-base-url for compatible setup)",
    ),
    profile_key: str | None = typer.Option(
        None,
        "--profile-key",
        help="API key for the selected OpenAI-compatible profile",
    ),
    profile_default_model: str | None = typer.Option(
        None,
        "--profile-default-model",
        help="Default model id to store in the selected compatible profile",
    ),
    set_default_profile: bool = typer.Option(
        False,
        "--set-default-profile",
        help="Set the selected OpenAI-compatible profile as default",
    ),
    fastfold_api_key: str | None = typer.Option(
        None, "--fastfold-api-key", help="Fastfold AI Cloud API key (non-interactive mode)"
    ),
    boltz_api_key: str | None = typer.Option(
        None, "--boltz-api-key", help="Boltz API key (non-interactive mode)"
    ),
    provider: str | None = typer.Option(
        None, "--provider", help="LLM provider(s): anthropic, openai, openai_compatible"
    ),
    skills: str | None = typer.Option(
        None, "--skills", help="Comma-separated skill names/sources to install non-interactively"
    ),
    skip_skills: bool = typer.Option(
        False, "--skip-skills", help="Skip the agent-skills install step"
    ),
    datasets: str | None = typer.Option(
        None,
        "--datasets",
        help="Comma-separated datasets to download non-interactively (e.g. 'depmap,msigdb' or 'all')",
    ),
    skip_datasets: bool = typer.Option(
        False, "--skip-datasets", help="Skip the dataset download step"
    ),
    mcp: str | None = typer.Option(
        None,
        "--mcp",
        help="Comma-separated MCP catalog ids to connect non-interactively",
    ),
    skip_mcp: bool = typer.Option(
        False, "--skip-mcp", help="Skip the MCP connect step"
    ),
    sandbox_backend: str | None = typer.Option(
        None,
        "--sandbox-backend",
        help="Sandbox backend for setup: builtin or modal",
    ),
    skip_sandbox: bool = typer.Option(
        False, "--skip-sandbox", help="Skip the sandbox setup step"
    ),
):
    """Interactive setup wizard — configure sandwalk for first use."""
    from agent.config import Config

    cleaned = _clean_setup_option_defaults({
        "api_key": api_key, "openai_api_key": openai_api_key, "openai_base_url": openai_base_url,
        "openai_compatible_backend": openai_compatible_backend, "profile_label": profile_label,
        "profile_template": profile_template, "profile_endpoint": profile_endpoint, "profile_key": profile_key,
        "profile_default_model": profile_default_model, "set_default_profile": set_default_profile,
        "fastfold_api_key": fastfold_api_key, "boltz_api_key": boltz_api_key, "provider": provider,
        "skills": skills, "skip_skills": skip_skills, "datasets": datasets, "skip_datasets": skip_datasets,
        "mcp": mcp, "skip_mcp": skip_mcp, "sandbox_backend": sandbox_backend, "skip_sandbox": skip_sandbox,
    })

    if cleaned["profile_endpoint"] and not cleaned["openai_base_url"]:
        cleaned["openai_base_url"] = cleaned["profile_endpoint"]
    if cleaned["profile_template"] and not cleaned["openai_compatible_backend"]:
        cleaned["openai_compatible_backend"] = cleaned["profile_template"]
    cleaned["openai_compatible_backend"] = (
        _normalize_compatible_backend_name(cleaned["openai_compatible_backend"]) or None
    )

    cfg = Config.load()
    default_provider = str(cleaned["provider"] or cfg.get("llm.provider", "openai") or "openai").strip().lower()
    if default_provider not in {"anthropic", "openai", "openai_compatible"}:
        default_provider = "openai"
    cleaned["default_provider"] = default_provider

    if _setup_check_foundry_shortcut(cfg, default_provider):
        return

    console.print()
    console.print(
        Panel(
            "[bold]This wizard will help you configure Fastfold Agent CLI.[/bold]\n"
            "Press Ctrl+C at any time to cancel.",
            title="[cyan]Fastfold Setup Wizard[/cyan]",
            border_style="#00bcd4",
        )
    )
    console.print()

    selection = _setup_resolve_providers_and_keys(cfg, cleaned)

    cleaned["cloud_key"] = _prompt_fastfold_cloud_api_key(cfg, cleaned["fastfold_api_key"])
    cleaned["boltz_key"] = _prompt_boltz_api_key(cfg, cleaned["boltz_api_key"])

    _setup_persist_provider_choice(cfg, selection, cleaned)
    _setup_print_provider_summary(selection["selected_providers"], cleaned["cloud_key"], cleaned["boltz_key"])

    # MCP + skills (combined conceptual step), then datasets, then sandbox last.
    _prompt_setup_mcps(mcp_arg=cleaned["mcp"], skip=cleaned["skip_mcp"])
    _prompt_install_skills(skills_arg=cleaned["skills"], skip=cleaned["skip_skills"])
    _prompt_install_boltz_stack(cleaned["boltz_key"])
    _prompt_install_datasets(datasets_arg=cleaned["datasets"], skip=cleaned["skip_datasets"])
    _prompt_setup_sandbox(cfg, backend_arg=cleaned["sandbox_backend"], skip=cleaned["skip_sandbox"])

    _setup_run_health_check()
    _setup_finish(cfg)
