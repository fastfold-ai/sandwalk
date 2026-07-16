"""Fast onboarding doctor (core checks) and error/warning summary helpers."""

from __future__ import annotations

from agent.config import CONFIG_FILE, OPENAI_COMPATIBLE_PROVIDERS, Config
from agent.doctor.checks_runtime import _check_python_runtime, _check_sandbox_backend
from agent.doctor.models import DoctorCheck, _normalize_check


def _configured_llm_summary(cfg: Config) -> DoctorCheck:
    """Report which LLM providers/profiles have credentials configured."""
    labels: list[str] = []

    cloud_order = ("anthropic", "openai", "google", "xai", "nvidia", "opencode")
    for provider in cloud_order:
        if not cfg.llm_api_key(provider):
            continue
        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            label = OPENAI_COMPATIBLE_PROVIDERS[provider].get("label") or provider
        elif provider == "anthropic":
            label = "Anthropic"
        elif provider == "openai":
            label = "OpenAI"
        else:
            label = provider
        labels.append(str(label))

    try:
        local_profiles = cfg.openai_profiles(include_cloud=False)
    except Exception:  # noqa: BLE001 — best-effort inventory
        local_profiles = {}
    for profile in local_profiles.values():
        if not isinstance(profile, dict):
            continue
        base_url = str(profile.get("base_url") or "").strip()
        if not base_url:
            continue
        label = str(profile.get("label") or profile.get("backend") or "Local").strip()
        if label and label not in labels:
            labels.append(label)

    if labels:
        return DoctorCheck(
            name="llm",
            status="ok",
            detail=", ".join(labels),
            category="llm",
        )

    issue = cfg.llm_preflight_issue()
    return DoctorCheck(
        name="llm",
        status="error",
        detail=issue
        or "No LLM API keys or local endpoints configured. Add one in Models.",
        category="llm",
        fix="Dashboard → Models, or complete the Model onboarding step",
    )


def run_checks_core(config: Config | None = None) -> list[DoctorCheck]:
    """Fast onboarding doctor: core runtime + configured LLM providers."""
    cfg = config or Config.load()
    checks: list[DoctorCheck] = []

    if CONFIG_FILE.exists():
        checks.append(
            DoctorCheck(
                name="config_file",
                status="ok",
                detail=f"Using {CONFIG_FILE}",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="config_file",
                status="warn",
                detail=f"No config file yet at {CONFIG_FILE} (defaults/env vars are used)",
            )
        )

    checks.append(_configured_llm_summary(cfg))
    checks.append(_check_python_runtime())
    checks.append(_check_sandbox_backend(cfg))

    return [_normalize_check(check) for check in checks]


def has_errors(checks: list[DoctorCheck]) -> bool:
    """Return True if any check has error status."""
    return any(c.status == "error" for c in checks)


def has_warnings(checks: list[DoctorCheck]) -> bool:
    """Return True if any check has warn status."""
    return any(c.status == "warn" for c in checks)
