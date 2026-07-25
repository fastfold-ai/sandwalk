"""Knowledge Level policy: how much always-on prompt / Deep Agents surface to load.

``high`` is today's full behavior. ``medium`` / ``low`` shrink the system prompt
and Deep Agents builtin tool schemas. Skills index, domain tools, and MCP stay
available at every level so agents can still run skills and normal work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

KnowledgeLevel = Literal["low", "medium", "high"]
PtcCatalogMode = Literal["full", "compact", "stub"]

VALID_KNOWLEDGE_LEVELS: frozenset[str] = frozenset({"low", "medium", "high"})
DEFAULT_KNOWLEDGE_LEVEL: KnowledgeLevel = "high"


@dataclass(frozen=True)
class KnowledgeFlags:
    level: KnowledgeLevel
    omit_workflow_index: bool
    # high = full identity; medium = hard compress; low = bare
    identity: Literal["full", "compact", "bare"]
    omit_synthesis: bool
    short_synthesis: bool
    ptc_catalog: PtcCatalogMode
    excluded_deepagents_tools: frozenset[str]
    include_domain_subagents: bool


# Medium targets ~5k: drop planning/shell builtins + task/subagents (PTC +
# skills still cover everyday work). High keeps task/domain-expert.
_MEDIUM_EXCLUDED = frozenset({"write_todos", "execute", "task"})
# Low targets ~2.5–3k: same as medium plus less-used filesystem search tools.
# Keep ls/read_file/write_file so skills (read SKILL.md) and artifacts work.
_LOW_EXCLUDED = frozenset(
    {"write_todos", "execute", "task", "edit_file", "glob", "grep"}
)


def resolve_knowledge_level(config: Any | None = None) -> KnowledgeLevel:
    """Return a valid knowledge level from config (default ``high``)."""
    raw = ""
    if config is not None:
        try:
            raw = str(config.get("agent.knowledge_level") or "").strip().lower()
        except Exception:  # noqa: BLE001
            raw = ""
    if raw in VALID_KNOWLEDGE_LEVELS:
        return raw  # type: ignore[return-value]
    return DEFAULT_KNOWLEDGE_LEVEL


def knowledge_flags(level: KnowledgeLevel | str | None = None, *, config: Any | None = None) -> KnowledgeFlags:
    """Flags consumed by system-prompt builders and deepagents assembly."""
    resolved: KnowledgeLevel
    if level is None:
        resolved = resolve_knowledge_level(config)
    elif str(level).strip().lower() in VALID_KNOWLEDGE_LEVELS:
        resolved = str(level).strip().lower()  # type: ignore[assignment]
    else:
        resolved = DEFAULT_KNOWLEDGE_LEVEL

    if resolved == "high":
        return KnowledgeFlags(
            level="high",
            omit_workflow_index=False,
            identity="full",
            omit_synthesis=False,
            short_synthesis=False,
            ptc_catalog="full",
            excluded_deepagents_tools=frozenset(),
            include_domain_subagents=True,
        )
    if resolved == "medium":
        return KnowledgeFlags(
            level="medium",
            omit_workflow_index=True,
            identity="compact",
            omit_synthesis=False,
            short_synthesis=True,
            ptc_catalog="stub",
            excluded_deepagents_tools=_MEDIUM_EXCLUDED,
            include_domain_subagents=False,
        )
    return KnowledgeFlags(
        level="low",
        omit_workflow_index=True,
        identity="bare",
        omit_synthesis=True,
        short_synthesis=False,
        ptc_catalog="stub",
        excluded_deepagents_tools=_LOW_EXCLUDED,
        include_domain_subagents=False,
    )
