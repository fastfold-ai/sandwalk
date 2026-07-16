"""API key presence checks (config + env var) and the environment summary."""

from __future__ import annotations

import os

from agent.config import Config
from agent.doctor.models import DoctorCheck


def _env_present(*names: str) -> bool:
    return any(bool(str(os.environ.get(name) or "").strip()) for name in names)


def _api_key_configured(cfg: Config, config_key: str) -> bool:
    """True when a key is set in config and/or its mapped env var (same sources as `sandwalk keys`)."""
    from agent.config import API_KEYS

    info = API_KEYS.get(config_key) or {}
    env_var = str(info.get("env_var") or "").strip()

    if config_key == "llm.anthropic_api_key":
        return bool(cfg.llm_api_key("anthropic"))
    if config_key == "llm.openai_api_key":
        return bool(
            Config._normalized_secret(
                os.environ.get("OPENAI_API_KEY")
                or cfg.get("llm.openai_api_key")
                or (cfg.openai_profiles(include_cloud=True).get("openai_cloud") or {}).get(
                    "api_key"
                )
            )
        )
    if config_key == "llm.openai_compatible_api_key":
        profiles = cfg.openai_profiles(include_cloud=True)
        for profile in profiles.values():
            backend = str(profile.get("backend") or "").strip().lower()
            if backend == "openai":
                continue
            if Config._normalized_secret(profile.get("api_key")):
                return True
        return False

    return bool(
        Config._normalized_secret(
            cfg.get(config_key) or (os.environ.get(env_var) if env_var else None)
        )
    )


def _check_environment(cfg: Config) -> list[DoctorCheck]:
    from agent.config import API_KEYS

    checks: list[DoctorCheck] = []
    configured = [
        str(info.get("name") or key)
        for key, info in API_KEYS.items()
        if _api_key_configured(cfg, key)
    ]
    total = len(API_KEYS)
    count = len(configured)
    checks.append(
        DoctorCheck(
            name="environment",
            status="ok" if count > 0 else "warn",
            detail=f"{count} of {total} keys configured",
            category="environment",
            fix=None if count > 0 else "Run `sandwalk keys` and set keys via config or env",
        )
    )

    # Provider key readiness — honor config + env the same way as llm_api_key / keys.
    provider = str(cfg.get("llm.provider", "anthropic") or "anthropic").strip().lower()
    provider_key = cfg.llm_api_key(provider)
    if provider_key:
        checks.append(
            DoctorCheck(
                name="llm_env",
                status="ok",
                detail=f"provider={provider} key configured",
                category="environment",
            )
        )
    elif cfg.llm_preflight_issue():
        # Surface only when the active provider truly cannot run.
        checks.append(
            DoctorCheck(
                name="llm_env",
                status="error",
                detail=cfg.llm_preflight_issue() or f"provider={provider} key missing",
                category="environment",
                fix="sandwalk keys  # then config set / export the provider key",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="llm_env",
                status="ok",
                detail=f"provider={provider} does not require an API key in this setup",
                category="environment",
            )
        )

    if _api_key_configured(cfg, "api.fastfold_cloud_key"):
        checks.append(
            DoctorCheck(
                name="fastfold_api_key",
                status="ok",
                detail="Fastfold Cloud key configured (api.fastfold_cloud_key / FASTFOLD_API_KEY)",
                category="environment",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="fastfold_api_key",
                status="warn",
                detail="Fastfold Cloud key not set",
                category="environment",
                fix="sandwalk config set api.fastfold_cloud_key <key>",
            )
        )

    return checks
