"""Full production-readiness check suite (`sandwalk doctor` / `/doctor` / `/v1/doctor`)."""

from __future__ import annotations

from agent.config import Config
from agent.doctor.checks_boltz import _check_boltz_cli
from agent.doctor.checks_cli_tooling import _check_cli_tooling, _check_skills_loaded
from agent.doctor.checks_config import check_config_and_paths
from agent.doctor.checks_connectivity import _check_tool_health
from agent.doctor.checks_data import _check_data_availability, _check_downloads_dir
from agent.doctor.checks_environment import _check_environment
from agent.doctor.checks_governance import check_governance
from agent.doctor.checks_guardrails import check_tooling_and_guardrails
from agent.doctor.checks_mcp import _check_mcp_servers
from agent.doctor.checks_runtime import _check_python_runtime, _check_sandbox_backend
from agent.doctor.model_provider_probe import _check_model_providers
from agent.doctor.models import DoctorCheck, _normalize_check


def run_checks(config: Config | None = None, session=None) -> list[DoctorCheck]:
    """Run production-readiness checks and return structured results.

    Args:
        config: Optional Config instance. Loaded from disk if not provided.
        session: Optional Session instance. When provided, runtime tool health
            data (suppressed tools, failure counts) is included in the report.
    """
    import agent.doctor as _doctor

    cfg = config or Config.load()
    checks: list[DoctorCheck] = []

    # 1-4) Config file, LLM readiness, output/data directories.
    checks.extend(check_config_and_paths(cfg))

    # 5-9) Tool module health + policy guardrails.
    checks.extend(check_tooling_and_guardrails(cfg))

    # 9b-13) Quality gate, enterprise policy, substrate, schema, claude code.
    checks.extend(check_governance(cfg))

    # 14) Data availability — verify key datasets can be found
    checks.append(_check_data_availability(cfg))

    # 15) Downloads directory
    checks.append(_check_downloads_dir())

    # 16) API connectivity (lightweight HEAD probes) — patchable, call via package.
    checks.extend(_doctor._check_api_connectivity())

    # 16b) Configured model provider endpoints (token-free /models probes)
    checks.extend(_check_model_providers(cfg))

    # 17) Runtime tool health
    checks.append(_check_tool_health(session))

    # 18) Preflight validation config
    if cfg.get("agent.preflight_validation_enabled", True):
        checks.append(
            DoctorCheck(
                name="preflight_validation",
                status="ok",
                detail="Pre-query API key validation is enabled",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="preflight_validation",
                status="warn",
                detail="Pre-query API key validation is disabled",
            )
        )

    # 19) Boltz CLI + key readiness
    checks.append(_check_boltz_cli(cfg))

    # 20+) Runtime tooling, skills inventory, environment keys
    checks.append(_check_python_runtime())
    checks.extend(_check_cli_tooling())
    checks.append(_check_skills_loaded())
    checks.extend(_check_environment(cfg))
    checks.extend(_check_mcp_servers(cfg))
    checks.append(_check_sandbox_backend(cfg))

    return [_normalize_check(check) for check in checks]
