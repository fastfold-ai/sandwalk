"""Gather configured model-provider probe targets (cloud keys + local endpoints)."""

from __future__ import annotations

import os

from agent.config import Config
from agent.doctor.models import DoctorCheck

# (provider_id, label, models_url, headers, is_local)
ProviderTarget = tuple[str, str, str, dict[str, str], bool]


def gather_local_profile_checks(cfg: Config) -> list[DoctorCheck]:
    """Probe local OpenAI-compatible profiles (Ollama/LM Studio/etc.) directly."""
    checks: list[DoctorCheck] = []
    try:
        local_profiles = cfg.openai_profiles(include_cloud=False)
    except Exception:
        local_profiles = {}
    for profile_id, profile in local_profiles.items():
        base_url = str(profile.get("base_url") or "").strip()
        if not base_url:
            continue
        label = str(profile.get("label") or profile_id)
        try:
            from agent.model_discovery import probe_compatible_profile

            probe = probe_compatible_profile(
                base_url=base_url,
                backend=str(profile.get("backend") or "other"),
                api_key=str(profile.get("api_key") or "").strip() or None,
            )
        except Exception as exc:  # pragma: no cover - defensive
            probe = {"health": "error", "models": [], "error": str(exc)}
        health = str(probe.get("health") or "error")
        model_count = len(probe.get("models") or [])
        if health == "healthy":
            checks.append(
                DoctorCheck(
                    name=f"Model endpoint · {label}",
                    status="ok",
                    detail=f"Local endpoint reachable ({model_count} models)",
                    category="llm",
                )
            )
        elif health == "no_models":
            checks.append(
                DoctorCheck(
                    name=f"Model endpoint · {label}",
                    status="warn",
                    detail="Local endpoint reachable but returned no models",
                    category="llm",
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    name=f"Model endpoint · {label}",
                    status="warn",
                    detail=f"Local endpoint: {probe.get('error') or 'unreachable'}",
                    category="llm",
                    fix="Start the local server or update it in Dashboard → Models → Local LLM",
                )
            )
    return checks


def gather_cloud_provider_targets(cfg: Config) -> list[ProviderTarget]:
    """Build the list of cloud/OpenAI-compatible provider endpoints to probe."""
    from agent.config import OPENAI_COMPATIBLE_PROVIDERS

    targets: list[ProviderTarget] = []

    anthropic_key = cfg.llm_api_key("anthropic")
    if anthropic_key:
        targets.append(
            (
                "anthropic",
                "Anthropic",
                "https://api.anthropic.com/v1/models",
                {"x-api-key": anthropic_key, "anthropic-version": "2023-06-01"},
                False,
            )
        )

    openai_key = cfg._normalized_secret(
        cfg.get("llm.openai_api_key")
    ) or cfg._normalized_secret(os.environ.get("OPENAI_API_KEY"))
    if openai_key:
        targets.append(
            (
                "openai",
                "OpenAI",
                "https://api.openai.com/v1/models",
                {"Authorization": f"Bearer {openai_key}"},
                False,
            )
        )

    for prov, meta in OPENAI_COMPATIBLE_PROVIDERS.items():
        key = cfg.llm_api_key(prov)
        if not key:
            continue
        models_url = str(meta["base_url"]).rstrip("/") + "/models"
        targets.append(
            (prov, meta["label"], models_url, {"Authorization": f"Bearer {key}"}, False)
        )

    return targets
