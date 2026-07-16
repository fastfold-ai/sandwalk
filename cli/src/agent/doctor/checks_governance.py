"""Quality gate, enterprise policy, knowledge substrate, and Claude Code checks."""

from __future__ import annotations

from pathlib import Path

from agent.config import CONFIG_DIR, Config
from agent.doctor.models import DoctorCheck


def check_governance(cfg: Config) -> list[DoctorCheck]:
    """Checks 9b-13: quality gate, enterprise policy, substrate, schema, claude code."""
    checks: list[DoctorCheck] = []

    # 9) Quality gate policy
    if cfg.get("agent.quality_gate_enabled", True):
        strict = bool(cfg.get("agent.quality_gate_strict", False))
        checks.append(
            DoctorCheck(
                name="quality_gate",
                status="ok" if strict else "warn",
                detail=(
                    "Strict quality gate enabled (must pass citation/actionability checks)"
                    if strict
                    else "Quality gate is warn-only (strict mode disabled)"
                ),
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="quality_gate",
                status="warn",
                detail="Quality gate is disabled",
            )
        )

    # 10) Enterprise policy layer
    enforce_policy = bool(cfg.get("enterprise.enforce_policy", False))
    checks.append(
        DoctorCheck(
            name="enterprise_policy",
            status="ok" if enforce_policy else "warn",
            detail=(
                "Policy enforcement enabled"
                if enforce_policy
                else "Policy enforcement disabled (research mode)"
            ),
        )
    )

    # 11) Knowledge substrate path
    substrate_path = Path(
        cfg.get("knowledge.substrate_path", str(CONFIG_DIR / "knowledge" / "substrate.json"))
    )
    try:
        substrate_path.parent.mkdir(parents=True, exist_ok=True)
        checks.append(
            DoctorCheck(
                name="knowledge_substrate",
                status="ok",
                detail=f"Writable substrate path: {substrate_path}",
            )
        )
    except OSError as exc:
        checks.append(
            DoctorCheck(
                name="knowledge_substrate",
                status="warn",
                detail=f"Could not prepare substrate path {substrate_path}: {exc}",
            )
        )

    # 12) Schema monitor readiness
    if cfg.get("knowledge.schema_monitor_enabled", False):
        baseline = CONFIG_DIR / "knowledge" / "schema_baselines.json"
        if baseline.exists():
            checks.append(
                DoctorCheck(
                    name="schema_monitor",
                    status="ok",
                    detail=f"Baseline present: {baseline}",
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    name="schema_monitor",
                    status="warn",
                    detail="Schema monitor enabled but no baseline found. Run: sandwalk knowledge schema-update",
                )
            )
    else:
        checks.append(
            DoctorCheck(
                name="schema_monitor",
                status="warn",
                detail="Schema monitor disabled",
            )
        )

    # 13) Claude Code delegation policy
    if cfg.get("agent.enable_claude_code_tool", False):
        checks.append(
            DoctorCheck(
                name="claude_code_policy",
                status="warn",
                detail="claude.code is enabled for autonomous use (high privilege)",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="claude_code_policy",
                status="ok",
                detail="claude.code is disabled by default (opt-in)",
            )
        )

    return checks
