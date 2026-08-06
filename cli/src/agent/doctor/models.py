"""DoctorCheck record type, category mapping, and normalization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DoctorCheck:
    name: str
    status: str  # "ok" | "warn" | "error"
    detail: str
    category: str = "general"
    fix: str | None = None


_CATEGORY_BY_NAME: dict[str, str] = {
    "config_file": "config",
    "llm": "llm",
    "llm_env": "environment",
    "output_dir": "paths",
    "data_base": "paths",
    "downloads_dir": "paths",
    "knowledge_substrate": "paths",
    "tool_modules": "tools",
    "tool_health": "tools",
    "experimental_tools": "policy",
    "grounding_guard": "policy",
    "runtime_profile": "policy",
    "synthesis_style": "policy",
    "quality_gate": "policy",
    "enterprise_policy": "policy",
    "claude_code_policy": "policy",
    "preflight_validation": "policy",
    "schema_monitor": "policy",
    "data_availability": "data",
    "api_connectivity": "network",
    "boltz_cli": "tooling",
    "python_runtime": "runtime",
    "sandbox_backend": "runtime",
    "npx": "tooling",
    "node": "tooling",
    "git": "tooling",
    "skills_loaded": "skills",
    "environment": "environment",
    "fastfold_api_key": "environment",
    "mcp_tamarind": "mcp",
    "mcp_latch": "mcp",
    "mcp_neurosnap": "mcp",
    "mcp_paperclip": "mcp",
    "mcp_exa": "mcp",
    "mcp_linear": "mcp",
}


def _status_markup(status: str) -> str:
    if status == "ok":
        return "[green]ok[/green]"
    if status == "warn":
        return "[yellow]warn[/yellow]"
    return "[red]error[/red]"


def _normalize_check(check: DoctorCheck) -> DoctorCheck:
    category = (
        check.category
        if check.category != "general"
        else _CATEGORY_BY_NAME.get(check.name, "general")
    )
    if category == check.category:
        return check
    return DoctorCheck(
        name=check.name,
        status=check.status,
        detail=check.detail,
        category=category,
        fix=check.fix,
    )
