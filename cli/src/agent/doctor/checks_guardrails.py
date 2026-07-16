"""Tool-module load health and agent policy guardrail checks."""

from __future__ import annotations

from agent.config import Config
from agent.doctor.models import DoctorCheck
from tools import EXPERIMENTAL_CATEGORIES, ensure_loaded, tool_load_errors


def check_tooling_and_guardrails(cfg: Config) -> list[DoctorCheck]:
    """Checks 5-9: tool modules, experimental tools, grounding, profile, style."""
    checks: list[DoctorCheck] = []

    # 5) Tool module import health
    ensure_loaded()
    load_errors = tool_load_errors()
    if load_errors:
        sample = ", ".join(sorted(load_errors.keys())[:8])
        extra = "" if len(load_errors) <= 8 else f" (+{len(load_errors) - 8} more)"
        checks.append(
            DoctorCheck(
                name="tool_modules",
                status="warn",
                detail=f"{len(load_errors)} module(s) failed to load: {sample}{extra}",
            )
        )
    else:
        checks.append(
            DoctorCheck(name="tool_modules", status="ok", detail="All tool modules loaded")
        )

    # 6) Experimental categories planning status
    if cfg.get("agent.enable_experimental_tools", False):
        checks.append(
            DoctorCheck(
                name="experimental_tools",
                status="warn",
                detail=(
                    f"Experimental categories enabled for planning: "
                    f"{', '.join(sorted(EXPERIMENTAL_CATEGORIES))}"
                ),
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="experimental_tools",
                status="ok",
                detail=(
                    f"Experimental categories hidden from planning by default: "
                    f"{', '.join(sorted(EXPERIMENTAL_CATEGORIES))}"
                ),
            )
        )

    # 7) Grounding guardrail status
    if cfg.get("agent.enforce_grounded_synthesis", True):
        checks.append(
            DoctorCheck(
                name="grounding_guard",
                status="ok",
                detail="Grounded synthesis enforcement is enabled",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="grounding_guard",
                status="warn",
                detail="Grounded synthesis enforcement is disabled",
            )
        )

    # 8) Runtime profile
    profile = str(cfg.get("agent.profile", "research"))
    if profile not in {"research", "pharma", "enterprise"}:
        checks.append(
            DoctorCheck(
                name="runtime_profile",
                status="warn",
                detail=f"Unknown agent.profile '{profile}'",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="runtime_profile",
                status="ok",
                detail=f"{profile}",
            )
        )

    synthesis_style = str(cfg.get("agent.synthesis_style", "standard")).strip().lower()
    if synthesis_style not in {"standard", "pharma"}:
        checks.append(
            DoctorCheck(
                name="synthesis_style",
                status="warn",
                detail=f"Unknown agent.synthesis_style '{synthesis_style}'",
            )
        )
    elif profile == "pharma" and synthesis_style != "pharma":
        checks.append(
            DoctorCheck(
                name="synthesis_style",
                status="warn",
                detail="agent.profile=pharma but synthesis style is not pharma",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="synthesis_style",
                status="ok",
                detail=synthesis_style,
            )
        )

    return checks
