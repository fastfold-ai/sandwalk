"""Mirror configured credentials into ``os.environ`` for subprocess tools/skills."""

from __future__ import annotations

import os

from .api_keys import API_KEYS

# Extra config → process-env mirrors (tools/skills that read env, not only API_KEYS).
_EXTRA_ENV_FROM_CONFIG: dict[str, str] = {
    "OPENAI_BASE_URL": "llm.openai_base_url",
    "CT_DATA_DIR": "data.base",
    "CT_LLM_PROVIDER": "llm.provider",
    "CT_LLM_MODEL": "llm.model",
    "CT_DATA_ENDPOINT": "api.data_endpoint",
    "CLUE_API_KEY": "api.clue_key",
}


def _config_secret_for_env(config: object, config_key: str) -> str:
    """Resolve a config value for export into ``os.environ`` (no env read-back)."""
    if config_key == "llm.anthropic_api_key":
        return str(
            config._normalized_secret(
                config.get("llm.anthropic_api_key") or config.get("llm.api_key")
            )
            or ""
        ).strip()
    if config_key == "llm.openai_api_key":
        profiles = config.get("llm.openai_profiles") or {}
        cloud = profiles.get("openai_cloud") if isinstance(profiles, dict) else None
        cloud_key = (cloud or {}).get("api_key") if isinstance(cloud, dict) else None
        return str(
            config._normalized_secret(config.get("llm.openai_api_key") or cloud_key) or ""
        ).strip()
    if config_key == "llm.openai_base_url":
        # Prefer profile / config URL without reading OPENAI_BASE_URL (avoid loops).
        profile = None
        try:
            profile = config.get_openai_profile()
        except Exception:
            profile = None
        backend = str((profile or {}).get("backend") or "").strip().lower()
        if backend and backend != "openai":
            profile_url = config._normalize_openai_base_url((profile or {}).get("base_url"))
            if profile_url:
                return str(profile_url).strip()
        value = config._normalize_openai_base_url(config.get("llm.openai_base_url"))
        if value and not config._is_openai_managed_base_url(value):
            return str(value).strip()
        return ""
    raw = config.get(config_key)
    if hasattr(config, "_normalized_secret"):
        return str(config._normalized_secret(raw) or "").strip()
    return str(raw or "").strip()


def sync_sandwalk_path_env(*, force: bool = True) -> list[str]:
    """Export stable Sandwalk path env vars for skills/agents (no hardcoded homes)."""
    from .constants import CONFIG_DIR

    config_dir = str(CONFIG_DIR.expanduser().resolve())
    skills_dir = str((CONFIG_DIR / "skills").expanduser().resolve())
    applied: list[str] = []
    for name, value in (
        ("SANDWALK_CONFIG_DIR", config_dir),
        ("SANDWALK_SKILLS_DIR", skills_dir),
    ):
        current = str(os.environ.get(name) or "").strip()
        if force or not current:
            os.environ[name] = value
            applied.append(name)
    return applied


def sync_process_env_from_config(
    config: object | None = None,
    *,
    only_missing: bool = True,
    config_keys: list[str] | None = None,
) -> list[str]:
    """Mirror configured credentials into ``os.environ`` for subprocess tools/skills.

    Matches CLI ``Session`` behavior so the web agent-server (Mac app / local-web)
    exposes the same keys that an interactive CLI session would. Existing process
    env values win when ``only_missing`` is True (default).

    Always refreshes ``SANDWALK_CONFIG_DIR`` and ``SANDWALK_SKILLS_DIR``.

    Returns the list of environment variable names that were written.
    """
    from . import Config

    cfg = config or Config.load()
    allowed = set(config_keys) if config_keys is not None else None
    applied: list[str] = []

    # Local LLM keys live on profiles only — never re-export a global compatible key.
    if "OPENAI_COMPATIBLE_API_KEY" in os.environ:
        os.environ.pop("OPENAI_COMPATIBLE_API_KEY", None)
        applied.append("OPENAI_COMPATIBLE_API_KEY(cleared)")

    for config_key, info in API_KEYS.items():
        if allowed is not None and config_key not in allowed:
            continue
        env_names = _env_names_for_info(info)
        if not env_names:
            continue
        value = _config_secret_for_env(cfg, config_key)
        if not value:
            continue
        for env_name in env_names:
            if only_missing and str(os.environ.get(env_name) or "").strip():
                continue
            os.environ[env_name] = value
            applied.append(env_name)

    for env_name, config_key in _EXTRA_ENV_FROM_CONFIG.items():
        if allowed is not None and config_key not in allowed:
            continue
        value = _config_secret_for_env(cfg, config_key)
        if not value:
            continue
        if only_missing and str(os.environ.get(env_name) or "").strip():
            continue
        os.environ[env_name] = value
        applied.append(env_name)

    applied.extend(sync_sandwalk_path_env(force=True))
    return applied


def listed_integration_env_vars(config: object | None = None) -> list[str]:
    """Return sorted env var *names* that Integrations/config currently populate.

    Values are never returned — only names the agent can ``printenv`` / rely on.
    """
    sync_process_env_from_config(config)
    names: list[str] = []
    for info in API_KEYS.values():
        for env_name in _env_names_for_info(info):
            if str(os.environ.get(env_name) or "").strip():
                names.append(env_name)
    for env_name in _EXTRA_ENV_FROM_CONFIG:
        if str(os.environ.get(env_name) or "").strip():
            names.append(env_name)
    return sorted(set(names))


def unset_process_env_for_config_keys(config_keys: list[str]) -> list[str]:
    """Remove process env vars that map to the given config keys (integration remove)."""
    removed: list[str] = []
    env_names_by_config: dict[str, list[str]] = {
        config_key: _env_names_for_info(info)
        for config_key, info in API_KEYS.items()
    }
    for env_name, config_key in _EXTRA_ENV_FROM_CONFIG.items():
        names = env_names_by_config.setdefault(config_key, [])
        if env_name not in names:
            names.append(env_name)
    for config_key in config_keys:
        for env_name in env_names_by_config.get(config_key) or []:
            if env_name in os.environ:
                os.environ.pop(env_name, None)
                removed.append(env_name)
    return removed


def _env_names_for_info(info: dict) -> list[str]:
    """Primary env var plus optional aliases (comma/space separated)."""
    names: list[str] = []
    primary = str(info.get("env_var") or "").strip()
    if primary:
        names.append(primary)
    aliases = str(info.get("env_var_aliases") or "").strip()
    if aliases:
        for part in aliases.replace(",", " ").split():
            token = part.strip()
            if token and token not in names:
                names.append(token)
    return names


def env_var_mappings(api_keys: dict) -> dict[str, str]:
    """Build the env-var → config-key mapping used by ``Config.load()``."""
    mappings: dict[str, str] = {}
    for key, info in api_keys.items():
        for env_name in _env_names_for_info(info):
            mappings[env_name] = key
    mappings.update(
        {
            "ANTHROPIC_API_KEY": "llm.anthropic_api_key",
            "OPENAI_API_KEY": "llm.openai_api_key",
            "XAI_API_KEY": "llm.xai_api_key",
            "GEMINI_API_KEY": "llm.google_api_key",
            "MOONSHOT_API_KEY": "llm.moonshot_api_key",
            "OPENROUTER_API_KEY": "llm.openrouter_api_key",
            "CEREBRAS_API_KEY": "llm.cerebras_api_key",
            "GROQ_API_KEY": "llm.groq_api_key",
            "FIREWORKS_API_KEY": "llm.fireworks_api_key",
            "OPENCODE_API_KEY": "llm.opencode_api_key",
            "QWEN_API_KEY": "llm.qwen_api_key",
            "DASHSCOPE_API_KEY": "llm.qwen_api_key",
            "OPENAI_BASE_URL": "llm.openai_base_url",
            "CT_DATA_DIR": "data.base",
            "CT_LLM_PROVIDER": "llm.provider",
            "CT_LLM_MODEL": "llm.model",
            "IBM_RXN_API_KEY": "api.ibm_rxn_key",
            "LENS_API_KEY": "api.lens_key",
            "FASTFOLD_API_KEY": "api.fastfold_cloud_key",
            "BOLTZ_API_KEY": "api.boltz_api_key",
            "SENDGRID_API_KEY": "notification.sendgrid_api_key",
            "LAMBDA_API_KEY": "compute.lambda_api_key",
            "RUNPOD_API_KEY": "compute.runpod_api_key",
            "CT_DATA_ENDPOINT": "api.data_endpoint",
            "CLUE_API_KEY": "api.clue_key",
        }
    )
    return mappings


def apply_env_overrides(data: dict, mappings: dict[str, str]) -> None:
    """Apply process-env overrides onto a freshly loaded config dict, in place."""
    for env_var, config_key in mappings.items():
        val = os.environ.get(env_var)
        if val and config_key not in data:
            data[config_key] = val
