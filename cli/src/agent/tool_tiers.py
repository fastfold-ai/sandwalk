"""Core vs extra tool tiers for Dashboard defaults and specialist allowlists.

Registry ``CORE_TOOL_NAMES`` stay always enabled (cannot be hidden via Tools UI).

Runtime-only tools (``run_python``, ``search_tools``, deepagents builtins) are
not in the registry and are always available — they are not listed here.
"""

from __future__ import annotations

from collections.abc import Iterable

# Registry tool IDs that stay enabled by default so the agent can run skills,
# sandbox workflows, and common ID lookups without the full ~190-tool surface.
CORE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "shell.run",
        "environment.install_package",
        "environment.list_packages",
        "skills.manage",
        "files.list_directory",
        "files.read_file",
        "files.write_report",
        "files.write_csv",
        "literature.pubmed_search",
        "data_api.uniprot_lookup",
        "data_api.opentargets_search",
        "ops.automation_manage",
        "ssh.hosts",
        "ssh.exec",
        "ssh.sync",
        "ssh.slurm_status",
        "ssh.bootstrap_remote",
    }
)

CORE_TOOLS_DEFAULTS_META_KEY = "core_tools_defaults_applied"
CORE_TOOLS_DEFAULTS_CONFIG_KEY = "agent.core_tools_defaults_applied"


def tool_tier(tool_id: str) -> str:
    """Return ``core`` or ``extra`` for a registry tool id."""
    name = str(tool_id or "").strip()
    return "core" if (name in CORE_TOOL_NAMES or name.startswith("memory.")) else "extra"


def is_core_tool(tool_id: str) -> bool:
    return tool_tier(tool_id) == "core"


def default_hidden_tool_ids(all_tool_ids: Iterable[str]) -> list[str]:
    """Return non-core registry tool ids that should be hidden by default."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in all_tool_ids:
        name = str(raw or "").strip()
        if not name or name in seen or name in CORE_TOOL_NAMES or name.startswith("memory."):
            continue
        seen.add(name)
        out.append(name)
    return sorted(out)


def apply_core_tool_defaults(config) -> list[str]:
    """One-shot: hide all non-core registry tools (merge into existing hidden).

    Returns the resulting ``agent.hidden_tools`` list. Idempotent via
    ``agent.core_tools_defaults_applied`` on the config (not store meta), so
    temporary AgentStore instances cannot re-apply against the user config.
    """
    from tools import ensure_loaded, registry

    if config.get(CORE_TOOLS_DEFAULTS_CONFIG_KEY):
        return list(config.hidden_tools())

    ensure_loaded()
    existing = set(config.hidden_tools())
    for tool_id in default_hidden_tool_ids(t.name for t in registry.list_tools()):
        existing.add(tool_id)
    next_list = sorted(existing)
    config.set("agent.hidden_tools", next_list)
    config.set(CORE_TOOLS_DEFAULTS_CONFIG_KEY, True)
    config.save()
    return next_list
