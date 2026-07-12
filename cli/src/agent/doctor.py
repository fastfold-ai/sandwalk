"""
Deployment readiness checks for fastfold.

Used by `fastfold doctor`, interactive `/doctor`, and the local agent `/v1/doctor` API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from rich.table import Table

from agent.config import CONFIG_FILE, Config
from tools import EXPERIMENTAL_CATEGORIES, ensure_loaded, tool_load_errors

logger = logging.getLogger("doctor")


@dataclass
class DoctorCheck:
    name: str
    status: str  # "ok" | "warn" | "error"
    detail: str
    category: str = "general"
    fix: Optional[str] = None


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
    "npx": "tooling",
    "node": "tooling",
    "git": "tooling",
    "skills_loaded": "skills",
    "environment": "environment",
    "fastfold_api_key": "environment",
    "mcp_tamarind": "mcp",
    "mcp_latch": "mcp",
    "mcp_neurosnap": "mcp",
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


def run_checks(config: Config | None = None, session=None) -> list[DoctorCheck]:
    """Run production-readiness checks and return structured results.

    Args:
        config: Optional Config instance. Loaded from disk if not provided.
        session: Optional Session instance. When provided, runtime tool health
            data (suppressed tools, failure counts) is included in the report.
    """
    cfg = config or Config.load()
    checks: list[DoctorCheck] = []

    # 1) Config file readability (best-effort: load already handled parse errors)
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

    # 2) LLM configuration readiness
    llm_issue = cfg.llm_preflight_issue()
    provider = cfg.get("llm.provider", "anthropic")
    model = cfg.get("llm.model")
    if llm_issue:
        checks.append(DoctorCheck(name="llm", status="error", detail=llm_issue))
    else:
        if os.environ.get("ANTHROPIC_FOUNDRY_API_KEY") or os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE"):
            detail = f"provider=anthropic (Azure Foundry), model={model}"
        else:
            detail = f"provider={provider}, model={model}"
        checks.append(
            DoctorCheck(name="llm", status="ok", detail=detail)
        )

    # 3) Output directory availability
    out_dir = Path(cfg.get("sandbox.output_dir", str(Path.cwd() / "outputs")))
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        checks.append(
            DoctorCheck(name="output_dir", status="ok", detail=f"Writable: {out_dir}")
        )
    except OSError as exc:
        checks.append(
            DoctorCheck(name="output_dir", status="error", detail=f"{out_dir}: {exc}")
        )

    # 4) Data base directory availability
    data_base = Path(cfg.get("data.base", str(Path.home() / ".fastfold-cli" / "data")))
    try:
        data_base.mkdir(parents=True, exist_ok=True)
        checks.append(
            DoctorCheck(name="data_base", status="ok", detail=f"Writable: {data_base}")
        )
    except OSError as exc:
        checks.append(
            DoctorCheck(name="data_base", status="warn", detail=f"{data_base}: {exc}")
        )

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
        cfg.get("knowledge.substrate_path", str(Path.home() / ".fastfold-cli" / "knowledge" / "substrate.json"))
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
        baseline = Path.home() / ".fastfold-cli" / "knowledge" / "schema_baselines.json"
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
                    detail="Schema monitor enabled but no baseline found. Run: fastfold knowledge schema-update",
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

    # 14) Data availability — verify key datasets can be found
    checks.append(_check_data_availability(cfg))

    # 15) Downloads directory
    checks.append(_check_downloads_dir())

    # 16) API connectivity (lightweight HEAD probes)
    checks.extend(_check_api_connectivity())

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

    return [_normalize_check(check) for check in checks]


def has_errors(checks: list[DoctorCheck]) -> bool:
    """Return True if any check has error status."""
    return any(c.status == "error" for c in checks)


def has_warnings(checks: list[DoctorCheck]) -> bool:
    """Return True if any check has warn status."""
    return any(c.status == "warn" for c in checks)


def to_table(checks: list[DoctorCheck]) -> Table:
    """Render doctor checks as a rich table."""
    table = Table(title="Fastfold Doctor")
    table.add_column("Category", style="dim")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    for check in checks:
        detail = check.detail
        if check.fix:
            detail = f"{detail} — fix: {check.fix}"
        table.add_row(
            check.category,
            check.name,
            _status_markup(check.status),
            detail,
        )

    return table


def to_report(
    checks: list[DoctorCheck] | None = None,
    *,
    session=None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Return a JSON-serializable doctor report for CLI/API/UI consumers."""
    resolved = checks if checks is not None else run_checks(config=config, session=session)
    errors = sum(1 for c in resolved if c.status == "error")
    warns = sum(1 for c in resolved if c.status == "warn")
    oks = sum(1 for c in resolved if c.status == "ok")
    return {
        "ok": errors == 0,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "ok": oks,
            "warn": warns,
            "error": errors,
            "total": len(resolved),
        },
        "checks": [
            {
                "name": c.name,
                "status": c.status,
                "detail": c.detail,
                "category": c.category,
                "fix": c.fix,
            }
            for c in resolved
        ],
    }


# ---------------------------------------------------------------------------
# Runtime health check helpers
# ---------------------------------------------------------------------------


# Key datasets and the file patterns used by loaders
_KEY_DATASETS = {
    "depmap": ("CRISPRGeneEffect.csv", ["", "depmap"]),
    "prism": ("prism_LFC_COLLAPSED.csv", ["", "prism"]),
    "l1000": ("l1000_landmark_only.parquet", ["", "l1000"]),
}


def _tool_version(command: str, *args: str) -> Optional[str]:
    path = shutil.which(command)
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
            stdin=subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001
        return path
    text = (result.stdout or result.stderr or "").strip().splitlines()
    return text[0].strip() if text else path


def _check_python_runtime() -> DoctorCheck:
    version = platform.python_version()
    impl = platform.python_implementation()
    detail = f"{impl} {version} ({sys.executable})"
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 10):
        return DoctorCheck(
            name="python_runtime",
            status="error",
            detail=detail,
            category="runtime",
            fix="Use Python 3.10+",
        )
    if (major, minor) < (3, 11):
        return DoctorCheck(
            name="python_runtime",
            status="warn",
            detail=detail,
            category="runtime",
            fix="Python 3.11+ is recommended",
        )
    return DoctorCheck(
        name="python_runtime",
        status="ok",
        detail=detail,
        category="runtime",
    )


def _check_cli_tooling() -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []

    node_version = _tool_version("node", "--version")
    if node_version:
        checks.append(
            DoctorCheck(
                name="node",
                status="ok",
                detail=node_version,
                category="tooling",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="node",
                status="warn",
                detail="node not found on PATH",
                category="tooling",
                fix="Install Node.js to enable npx-based skill installs",
            )
        )

    npx_version = _tool_version("npx", "--version")
    if npx_version:
        checks.append(
            DoctorCheck(
                name="npx",
                status="ok",
                detail=f"npx {npx_version}",
                category="tooling",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="npx",
                status="warn",
                detail="npx not found; skill installs fall back to git/archive",
                category="tooling",
                fix="Install Node.js (includes npx) for Skills.sh-compatible installs",
            )
        )

    git_version = _tool_version("git", "--version")
    if git_version:
        checks.append(
            DoctorCheck(
                name="git",
                status="ok",
                detail=git_version,
                category="tooling",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="git",
                status="error",
                detail="git not found on PATH",
                category="tooling",
                fix="Install git to clone skill repositories",
            )
        )

    return checks


def _check_skills_loaded() -> DoctorCheck:
    try:
        from agent.skills import list_skills
    except Exception as exc:  # noqa: BLE001
        return DoctorCheck(
            name="skills_loaded",
            status="warn",
            detail=f"Could not inspect skills: {exc}",
            category="skills",
        )

    skills = list_skills()
    if not skills:
        return DoctorCheck(
            name="skills_loaded",
            status="warn",
            detail="0 discovered",
            category="skills",
            fix="fastfold skills add fastfold-ai/skills",
        )

    enabled = sum(1 for skill in skills if skill.enabled)
    disabled = len(skills) - enabled
    missing_md = sum(
        1
        for skill in skills
        if skill.path is None or not Path(skill.path).exists()
    )
    detail = f"{len(skills)} total · {enabled} enabled · {disabled} disabled"
    if missing_md:
        return DoctorCheck(
            name="skills_loaded",
            status="warn",
            detail=f"{detail} · {missing_md} missing SKILL.md",
            category="skills",
            fix="Remove broken skills or reinstall from source",
        )
    return DoctorCheck(
        name="skills_loaded",
        status="ok",
        detail=detail,
        category="skills",
    )


def _check_mcp_servers(cfg: Config) -> list[DoctorCheck]:
    """Probe enabled catalog MCP servers (Connect → toggle on)."""
    checks: list[DoctorCheck] = []
    try:
        from agent.mcp_catalog import MCP_CATALOG
        from agent_server.mcp_service import (
            credentials_configured,
            probe_mcp_server,
            resolve_auth_headers,
        )
        from agent_server.store import AgentStore
    except Exception as exc:  # noqa: BLE001
        checks.append(
            DoctorCheck(
                name="mcp_catalog",
                status="warn",
                detail=f"MCP catalog unavailable: {exc}",
                category="mcp",
            )
        )
        return checks

    try:
        store = AgentStore()
        enabled = {
            s.catalog_id: s
            for s in store.list_mcp_servers(enabled_only=True)
            if getattr(s, "catalog_id", None)
        }
    except Exception as exc:  # noqa: BLE001
        checks.append(
            DoctorCheck(
                name="mcp_store",
                status="warn",
                detail=f"Could not load MCP servers: {exc}",
                category="mcp",
                fix="Restart `fastfold serve`",
            )
        )
        return checks

    for entry in MCP_CATALOG:
        check_name = f"mcp_{entry.id}"
        server = enabled.get(entry.id)
        if server is None:
            # Suggested default off — skip unless credentials exist (stale/misconfig)
            if credentials_configured(entry, cfg):
                checks.append(
                    DoctorCheck(
                        name=check_name,
                        status="warn",
                        detail=f"{entry.name} credentials saved but MCP is disabled",
                        category="mcp",
                        fix=f"Enable on Dashboard → MCP, or Connect again",
                    )
                )
            continue

        headers = resolve_auth_headers(entry, cfg)
        if not headers:
            checks.append(
                DoctorCheck(
                    name=check_name,
                    status="error",
                    detail=f"{entry.name} is enabled but not authenticated",
                    category="mcp",
                    fix="Dashboard → MCP → Connect (OAuth or API key)",
                )
            )
            continue

        result = probe_mcp_server(url=entry.url, headers=headers, timeout=25.0)
        # Neurosnap accepts Bearer or X-API-KEY — retry alternate if primary fails.
        if not result["ok"] and entry.id == "neurosnap":
            from agent_server.mcp_service import _cfg_secret

            api_key = _cfg_secret(cfg, entry.api_key_config_key, entry.api_key_env_var)
            if api_key:
                for alt in (
                    {"X-API-KEY": api_key},
                    {"Authorization": f"Bearer {api_key}"},
                ):
                    if alt == headers:
                        continue
                    alt_result = probe_mcp_server(
                        url=entry.url, headers=alt, timeout=25.0
                    )
                    if alt_result.get("ok"):
                        result = alt_result
                        break

        if result["ok"]:
            try:
                from agent_server.mcp_service import save_tool_count

                save_tool_count(entry.id, int(result.get("toolCount") or 0))
            except Exception:  # noqa: BLE001
                pass
            checks.append(
                DoctorCheck(
                    name=check_name,
                    status="ok",
                    detail=f"{entry.name}: {result['toolCount']} tools",
                    category="mcp",
                )
            )
        else:
            try:
                from agent_server.mcp_service import clear_tool_count, save_status_message

                clear_tool_count(entry.id)
                save_status_message(
                    entry.id, str(result.get("message") or "Connection failed")
                )
            except Exception:  # noqa: BLE001
                pass
            checks.append(
                DoctorCheck(
                    name=check_name,
                    status="error",
                    detail=f"{entry.name}: {result['message']}",
                    category="mcp",
                    fix="Reconnect on Dashboard → MCP or check API key under Integrations",
                )
            )

    # Also note custom enabled remote MCP servers (no catalog_id)
    try:
        customs = [
            s
            for s in store.list_mcp_servers(enabled_only=True)
            if not getattr(s, "catalog_id", None) and s.url
        ]
        for server in customs[:5]:
            result = probe_mcp_server(url=server.url, headers=None, timeout=15.0)
            status = "ok" if result["ok"] else "warn"
            checks.append(
                DoctorCheck(
                    name=f"mcp_custom_{server.id[:8]}",
                    status=status,
                    detail=f"{server.name}: {result['message']}",
                    category="mcp",
                )
            )
    except Exception:  # noqa: BLE001
        pass

    return checks


def _env_present(*names: str) -> bool:
    return any(bool(str(os.environ.get(name) or "").strip()) for name in names)


def _api_key_configured(cfg: Config, config_key: str) -> bool:
    """True when a key is set in config and/or its mapped env var (same sources as `fastfold keys`)."""
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
        return bool(
            Config._normalized_secret(
                os.environ.get("OPENAI_COMPATIBLE_API_KEY")
                or cfg.get("llm.openai_compatible_api_key")
            )
        )

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
            fix=None if count > 0 else "Run `fastfold keys` and set keys via config or env",
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
                fix="fastfold keys  # then config set / export the provider key",
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
                fix="fastfold config set api.fastfold_cloud_key <key>",
            )
        )

    return checks


def _check_data_availability(cfg: Config) -> DoctorCheck:
    """Check whether key datasets can be found on disk."""
    data_base = Path(cfg.get("data.base", str(Path.home() / ".fastfold-cli" / "data")))
    search_dirs = [data_base]
    # Also check ct-data sister project
    ct_data = Path.home() / "Projects" / "CellType" / "ct-data"
    if ct_data.exists():
        search_dirs.append(ct_data)

    found = []
    missing = []
    for name, (filename, subdirs) in _KEY_DATASETS.items():
        located = False
        stem = Path(filename).stem
        for base_dir in search_dirs:
            for sub in subdirs:
                d = base_dir / sub if sub else base_dir
                if (d / filename).exists():
                    located = True
                    break
                parquet = d / f"{stem}.parquet"
                if parquet.exists():
                    located = True
                    break
            if located:
                break
        if located:
            found.append(name)
        else:
            missing.append(name)

    if not missing:
        return DoctorCheck(
            name="data_availability",
            status="ok",
            detail=f"Key datasets found: {', '.join(sorted(found))}",
        )
    if found:
        return DoctorCheck(
            name="data_availability",
            status="warn",
            detail=f"Missing datasets: {', '.join(sorted(missing))} (found: {', '.join(sorted(found))}). Run: fastfold data pull <name>",
        )
    return DoctorCheck(
        name="data_availability",
        status="warn",
        detail=f"No key datasets found ({', '.join(sorted(missing))}). Run: fastfold data pull depmap",
    )


def _check_downloads_dir() -> DoctorCheck:
    """Verify ~/.fastfold-cli/downloads/ exists and is writable."""
    downloads = Path.home() / ".fastfold-cli" / "downloads"
    try:
        downloads.mkdir(parents=True, exist_ok=True)
        return DoctorCheck(
            name="downloads_dir",
            status="ok",
            detail=f"Writable: {downloads}",
        )
    except OSError as exc:
        return DoctorCheck(
            name="downloads_dir",
            status="warn",
            detail=f"{downloads}: {exc}",
        )


# APIs to probe with HEAD requests (short timeout, best-effort)
_API_PROBES = [
    ("PubMed eutils", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi"),
    ("Enrichr", "https://maayanlab.cloud/Enrichr/"),
    ("GDC API", "https://api.gdc.cancer.gov/status"),
]


def _check_model_providers(cfg: Config) -> list[DoctorCheck]:
    """Health-check configured model provider endpoints without spending tokens.

    Uses each provider's model-list endpoint (``GET /models`` for OpenAI-style
    providers, ``GET /v1/models`` for Anthropic). Listing models validates both
    reachability and the API key, and never runs a completion — so it costs no
    tokens.
    """
    checks: list[DoctorCheck] = []
    try:
        import httpx
    except ImportError:
        return [
            DoctorCheck(
                name="model_providers",
                status="warn",
                detail="httpx not installed — skipping model endpoint checks",
                category="llm",
            )
        ]

    from agent.config import OPENAI_COMPATIBLE_PROVIDERS

    # (provider_id, label, models_url, headers, is_local)
    targets: list[tuple[str, str, str, dict[str, str], bool]] = []

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

    # Local OpenAI-compatible profiles (Ollama/LM Studio/etc.).
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

    if not targets and not checks:
        return [
            DoctorCheck(
                name="Model endpoints",
                status="warn",
                detail="No model provider API keys or local endpoints configured",
                category="llm",
            )
        ]

    for prov, label, url, headers, _is_local in targets:
        try:
            resp = httpx.get(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; FastFoldAgent/1.0; "
                        "+https://github.com/fastfold-ai/fastfold-agent-cli)"
                    ),
                    **headers,
                },
                timeout=6,
                follow_redirects=True,
            )
            code = resp.status_code
            body_text = ""
            try:
                body_text = (resp.text or "").strip()
            except Exception:
                body_text = ""
            body_lower = body_text.lower()
            # xAI (and some OpenAI-compatible APIs) return HTTP 400 for bad keys
            # instead of 401/403. Keep those as warnings (not hard failures).
            auth_hint_400 = code == 400 and any(
                marker in body_lower
                for marker in (
                    "incorrect api key",
                    "invalid api key",
                    "invalid_api_key",
                    "unauthorized",
                    "authentication",
                    "api key provided",
                )
            )
            if code == 200:
                count = 0
                try:
                    payload = resp.json()
                    data = (
                        payload.get("data")
                        if isinstance(payload, dict)
                        else None
                    ) or (
                        payload.get("models") if isinstance(payload, dict) else None
                    )
                    count = len(data) if isinstance(data, list) else 0
                except Exception:
                    count = 0
                detail = "Reachable, key valid" + (
                    f" ({count} models)" if count else ""
                )
                checks.append(
                    DoctorCheck(
                        name=f"Model endpoint · {label}",
                        status="ok",
                        detail=detail,
                        category="llm",
                    )
                )
            elif code in (401, 403):
                checks.append(
                    DoctorCheck(
                        name=f"Model endpoint · {label}",
                        status="error",
                        detail=f"Authentication failed (HTTP {code}) — check the API key",
                        category="llm",
                        fix="Update the key in Dashboard → Integrations / Models",
                    )
                )
            elif auth_hint_400:
                checks.append(
                    DoctorCheck(
                        name=f"Model endpoint · {label}",
                        status="warn",
                        detail="HTTP 400: Incorrect API key — update the key to restore this provider",
                        category="llm",
                        fix="Update the key in Dashboard → Integrations / Models",
                    )
                )
            else:
                detail = f"Unexpected response (HTTP {code})"
                # Prefer a short provider error message when available.
                try:
                    payload = resp.json()
                    if isinstance(payload, dict):
                        msg = str(
                            payload.get("error")
                            or payload.get("message")
                            or ""
                        ).strip()
                        if isinstance(payload.get("error"), dict):
                            msg = str(
                                payload["error"].get("message")
                                or payload["error"].get("error")
                                or msg
                            ).strip()
                        if msg:
                            detail = f"HTTP {code}: {msg[:160]}"
                except Exception:
                    pass
                checks.append(
                    DoctorCheck(
                        name=f"Model endpoint · {label}",
                        status="warn",
                        detail=detail,
                        category="llm",
                    )
                )
        except Exception as exc:
            checks.append(
                DoctorCheck(
                    name=f"Model endpoint · {label}",
                    status="warn",
                    detail=f"Endpoint unreachable ({exc})",
                    category="llm",
                )
            )

    return checks


def _check_api_connectivity() -> list[DoctorCheck]:
    """Quick HEAD/GET probe against key public APIs."""
    checks = []
    try:
        import httpx
    except ImportError:
        checks.append(
            DoctorCheck(
                name="api_connectivity",
                status="warn",
                detail="httpx not installed — skipping API connectivity probes",
            )
        )
        return checks

    reachable = []
    unreachable = []
    for label, url in _API_PROBES:
        try:
            resp = httpx.head(url, timeout=5, follow_redirects=True)
            if resp.status_code < 500:
                reachable.append(label)
            else:
                unreachable.append(f"{label} (HTTP {resp.status_code})")
        except Exception:
            unreachable.append(label)

    if not unreachable:
        checks.append(
            DoctorCheck(
                name="api_connectivity",
                status="ok",
                detail=f"All probes passed: {', '.join(reachable)}",
            )
        )
    elif reachable:
        checks.append(
            DoctorCheck(
                name="api_connectivity",
                status="warn",
                detail=f"Unreachable: {', '.join(unreachable)} (reachable: {', '.join(reachable)})",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="api_connectivity",
                status="warn",
                detail=f"All API probes failed: {', '.join(unreachable)}. Check network connectivity.",
            )
        )
    return checks


def _check_tool_health(session) -> DoctorCheck:
    """Report runtime tool suppression state from session."""
    if session is None:
        return DoctorCheck(
            name="tool_health",
            status="warn",
            detail="No active session context; run /doctor in interactive mode for runtime tool-health diagnostics",
        )

    suppressed = set()
    failure_counts: dict[str, int] = {}
    if hasattr(session, "tool_health_suppressed_tools"):
        suppressed = session.tool_health_suppressed_tools()
    if hasattr(session, "_tool_health_failures"):
        failure_counts = {
            name: len(timestamps)
            for name, timestamps in session._tool_health_failures.items()
            if timestamps
        }

    if not suppressed and not failure_counts:
        return DoctorCheck(
            name="tool_health",
            status="ok",
            detail="No tool failures or suppressions in this session",
        )

    parts = []
    if suppressed:
        parts.append(f"Suppressed: {', '.join(sorted(suppressed))}")
    if failure_counts:
        failing = [f"{n}({c})" for n, c in sorted(failure_counts.items()) if n not in suppressed]
        if failing:
            parts.append(f"Recent failures: {', '.join(failing)}")

    return DoctorCheck(
        name="tool_health",
        status="warn",
        detail="; ".join(parts),
    )


def _locate_boltz_cli_path() -> Path | None:
    """Locate the boltz-api executable across common install locations."""
    candidates: list[str] = []
    in_path = shutil.which("boltz-api")
    if in_path:
        candidates.append(in_path)
    candidates.extend(
        [
            str(Path.home() / ".local" / "bin" / "boltz-api"),
            str(Path.home() / ".boltz" / "bin" / "boltz-api"),
        ]
    )
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file() and os.access(str(path), os.X_OK):
            return path
    return None


def _boltz_cli_version(path: Path) -> str:
    """Return boltz-api version text (best effort)."""
    try:
        proc = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        return "unknown version"
    output = (proc.stdout or proc.stderr or "").strip()
    if not output:
        return "unknown version"
    return output.splitlines()[0].strip()


def _check_boltz_cli(cfg: Config) -> DoctorCheck:
    """Report Boltz integration readiness (key + CLI)."""
    boltz_key = str(cfg.get("api.boltz_api_key") or os.environ.get("BOLTZ_API_KEY") or "").strip()
    cli_path = _locate_boltz_cli_path()

    if cli_path is None and not boltz_key:
        return DoctorCheck(
            name="boltz_cli",
            status="ok",
            detail="Boltz integration not configured (optional).",
        )

    if cli_path is None and boltz_key:
        return DoctorCheck(
            name="boltz_cli",
            status="warn",
            detail=(
                "BOLTZ_API_KEY is configured but `boltz-api` CLI is missing. "
                "Install with: curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
            ),
        )

    version = _boltz_cli_version(cli_path)
    if boltz_key:
        return DoctorCheck(
            name="boltz_cli",
            status="ok",
            detail=f"boltz-api ready at {cli_path} ({version}); BOLTZ_API_KEY configured.",
        )
    return DoctorCheck(
        name="boltz_cli",
        status="warn",
        detail=(
            f"boltz-api found at {cli_path} ({version}) but BOLTZ_API_KEY is not configured. "
            "Set with: fastfold config set api.boltz_api_key <key> or /keys set-boltz"
        ),
    )
