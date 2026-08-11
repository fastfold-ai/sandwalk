"""Gather configured model-provider probe targets (cloud keys + local endpoints)."""

from __future__ import annotations

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
    """Deprecated: cloud auth probes use ``probe_llm_api_key`` (1-token chat).

    Kept for import compatibility; always returns an empty list.
    """
    _ = cfg
    return []
