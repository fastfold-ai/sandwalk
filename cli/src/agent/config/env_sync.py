"""Mirror configured credentials into ``os.environ`` for subprocess tools/skills."""

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


def _config_secret_for_env(config: "object", config_key: str) -> str:
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
    return str(config.get(config_key) or "").strip()


def sync_process_env_from_config(
    config: "object | None" = None,
    *,
    only_missing: bool = True,
    config_keys: list[str] | None = None,
) -> list[str]:
    """Mirror configured credentials into ``os.environ`` for subprocess tools/skills.

    Matches CLI ``Session`` behavior so the web agent-server (Mac app / local-web)
    exposes the same keys that an interactive CLI session would. Existing process
    env values win when ``only_missing`` is True (default).

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
        env_name = str(info.get("env_var") or "").strip()
        if not env_name:
            continue
        value = _config_secret_for_env(cfg, config_key)
        if not value:
            continue
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

    return applied


def unset_process_env_for_config_keys(config_keys: list[str]) -> list[str]:
    """Remove process env vars that map to the given config keys (integration remove)."""
    removed: list[str] = []
    env_by_config = {
        config_key: str(info.get("env_var") or "").strip()
        for config_key, info in API_KEYS.items()
    }
    for env_name, config_key in _EXTRA_ENV_FROM_CONFIG.items():
        env_by_config.setdefault(config_key, env_name)
    for config_key in config_keys:
        env_name = env_by_config.get(config_key)
        if not env_name:
            continue
        if env_name in os.environ:
            os.environ.pop(env_name, None)
            removed.append(env_name)
    return removed


def env_var_mappings(api_keys: dict) -> dict[str, str]:
    """Build the env-var → config-key mapping used by ``Config.load()``."""
    mappings = {str(info["env_var"]): key for key, info in api_keys.items()}
    mappings.update(
        {
            "ANTHROPIC_API_KEY": "llm.anthropic_api_key",
            "OPENAI_API_KEY": "llm.openai_api_key",
            "XAI_API_KEY": "llm.xai_api_key",
            "GEMINI_API_KEY": "llm.google_api_key",
            "OPENCODE_API_KEY": "llm.opencode_api_key",
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
