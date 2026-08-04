"""Helpers backing the startup banner: skill counts, tips, and news lines."""

import random

from cli.constants import _FASTFOLD_CORE_SKILL_NAMES
from ui.terminal import SLASH_COMMANDS

# Short aliases for a few Anthropic/OpenAI catalog ids (banner + compose parity).
_BANNER_MODEL_ALIASES = {
    "claude-sonnet-4-5-20250929": "Sonnet 4.5",
    "claude-haiku-4-5-20251001": "Haiku 4.5",
    "claude-opus-4-6": "Opus 4.6",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o Mini",
}


def _banner_model_display_name(cfg) -> str | None:
    """Friendly model label for the banner (not the raw API id)."""
    model_raw = str(cfg.get("llm.model") or "").strip()
    if not model_raw:
        return None
    if model_raw in _BANNER_MODEL_ALIASES:
        return _BANNER_MODEL_ALIASES[model_raw]
    provider = str(cfg.get("llm.provider") or "").strip().lower() or None
    try:
        from agent.model_catalog import catalog_label_for_model, format_discovered_model_label

        labeled = catalog_label_for_model(model_raw, provider=provider)
        if labeled:
            return labeled
        return format_discovered_model_label(model_raw)
    except Exception:
        return model_raw


def _banner_provider_label(cfg) -> str | None:
    """Provider label shown muted after the model name (compose meta style)."""
    provider = str(cfg.get("llm.provider") or "").strip().lower()
    if not provider:
        return None
    if provider == "anthropic":
        return "Anthropic"
    if provider == "openai":
        # Local / OpenAI-compatible profiles surface the backend name instead.
        try:
            if hasattr(cfg, "get_openai_profile"):
                profile = cfg.get_openai_profile()
            else:
                profile = None
        except Exception:
            profile = None
        backend = ""
        if isinstance(profile, dict):
            backend = str(profile.get("backend") or "").strip().lower()
        if backend and backend != "openai":
            names = {
                "ollama": "Ollama",
                "unsloth": "Unsloth",
                "omlx": "oMLX",
                "ds4": "DS4",
                "llama_cpp": "llama.cpp",
                "lm_studio": "LM Studio",
            }
            return names.get(backend, "Compatible")
        return "OpenAI"
    try:
        from agent.config import OPENAI_COMPATIBLE_PROVIDERS

        meta = OPENAI_COMPATIBLE_PROVIDERS.get(provider) or {}
        label = str(meta.get("label") or "").strip()
        return label or provider
    except Exception:
        return provider


def banner_model_provider_markup(cfg) -> str | None:
    """Rich markup: ``Kimi K3 OpenCode Zen`` (model + muted provider)."""
    model_name = _banner_model_display_name(cfg)
    if not model_name:
        return None
    provider_label = _banner_provider_label(cfg)
    # Match compose meta: model darker gray, provider softer gray, space-separated.
    parts = [f"[#555555]{model_name}[/]"]
    if provider_label:
        parts.append(f"[#8a8f98]{provider_label}[/]")
    try:
        from agent.model_catalog import config_selected_effort_label

        effort_label = config_selected_effort_label(cfg)
    except Exception:
        effort_label = None
    if effort_label:
        parts.append(f"[#8a8f98]· {effort_label}[/]")
    return " ".join(parts)


def _installed_claude_skill_names() -> list[str]:
    """Return installed skill names across all tiers (global, project, bundled)."""
    from agent.skills import installed_skill_names

    return installed_skill_names()


def _count_installed_claude_skills() -> int:
    """Count installed agent skills."""
    return len(_installed_claude_skill_names())


def _has_fastfold_skills_installed() -> bool:
    """Return True when at least one official Fastfold skill is installed."""
    from agent.skills import user_installed_skill_names

    installed = set(user_installed_skill_names())
    return bool(installed.intersection(_FASTFOLD_CORE_SKILL_NAMES))


def _get_cached_skills_update_safe() -> dict | None:
    """Local-only cached skills-update check for the banner (never raises)."""
    try:
        from agent.skills import get_cached_skills_update

        return get_cached_skills_update()
    except Exception:
        return None


def _start_skills_update_check() -> None:
    """Refresh the skills-update cache in a daemon thread (no boot-path network)."""
    import threading

    def _worker():
        try:
            from agent.skills import refresh_skills_update_cache

            refresh_skills_update_cache()
        except Exception:
            pass

    try:
        threading.Thread(target=_worker, daemon=True).start()
    except Exception:
        pass


def _get_loaded_tool_count_hint() -> int:
    """Return loaded tool count when already available, else a static hint."""
    from cli.constants import _BANNER_TOOL_COUNT_HINT

    try:
        from tools import registry

        count = len(registry.list_tools())
        if count > 0:
            return count
    except Exception:
        pass
    return _BANNER_TOOL_COUNT_HINT


def _random_command_tip_markup() -> str:
    """Return a random slash-command tip from actual terminal commands."""
    if not SLASH_COMMANDS:
        return "[dim]Tip: use slash commands in interactive mode.[/dim]"

    command, description = random.choice(list(SLASH_COMMANDS.items()))
    return f"[dim]Tip: try [/][bold #D4148E]{command}[/][dim] — {description}[/dim]"


_BOLTZ_NEWS_USE_CASES = (
    "structure and binding",
    "protein design",
    "protein screening",
    "small-molecule design",
    "small-molecule screening",
    "ADME prediction",
)


def _random_news_item_markup() -> str:
    """Return a rotating Boltz API news/action line."""
    installed = set(_installed_claude_skill_names())
    use_case = random.choice(_BOLTZ_NEWS_USE_CASES)
    if "boltz" in installed:
        return (
            "[bold #25C19F]Boltz API skill now available![/] "
            f"[#7A7A7A]· Try: Show me Boltz API examples for {use_case}[/]"
        )
    return (
        "[bold #25C19F]Boltz API skill now available[/] "
        f"[#7A7A7A]· Try: Show me Boltz API examples for {use_case}[/]"
    )
