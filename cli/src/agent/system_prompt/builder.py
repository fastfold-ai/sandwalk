"""build_system_prompt: assembles the unified agent system prompt."""

from __future__ import annotations

import logging

from .knowledge_section import build_knowledge_sections
from .skills_section import build_skills_section
from .text_blocks import _IDENTITY, _SYNTHESIS_INSTRUCTIONS
from .tools_section import build_tools_section
from .workspace_section import build_workspace_section

logger = logging.getLogger("system_prompt")


def build_system_prompt(
    session,
    tool_names: list[str] | None = None,
    data_context: str | None = None,
    history: str | None = None,
    user_request: str | None = None,
    include_skills: bool = True,
    runtime: str = "sdk",
    tool_mode: str = "native",
    exclude_categories: set[str] | None = None,
    exclude_tools: set[str] | None = None,
    project_context: str | None = None,
    specialist_instructions: str | None = None,
    workspace_path: str | None = None,
    sandbox_backend: str | None = None,
) -> str:
    """Build the unified system prompt for the agent runner.

    Args:
        session: Active ct Session.
        tool_names: Names of tools available in the MCP server (for reference).
        data_context: Free-text description of available data files / directories.
        history: Prior conversation turns (for interactive multi-turn sessions).
        user_request: Current user request text used for skill relevance routing.
        include_skills: When True, embed an installed-skills catalog in the
            prompt (SDK path). The deepagents runtime loads skills natively via
            progressive disclosure, so it passes ``include_skills=False``.
        runtime: Either ``"sdk"`` or ``"deepagents"`` — selects runtime-specific
            execution notes.
        tool_mode: ``"native"`` (per-tool schemas) or ``"ptc"`` (Programmatic
            Tool Calling). In PTC mode a compact catalog of domain tools is
            embedded and the model calls them as Python inside ``run_python``.
        exclude_categories: Tool categories omitted from the runtime, so the PTC
            catalog matches the tools actually available.
        specialist_instructions: Optional specialist profile text appended after
            project context.
        workspace_path: Per-session workspace directory shown in the UI file tree.
        sandbox_backend: ``"builtin"`` or ``"modal"`` — adds Modal-specific skill
            vs compute guidance when Modal is selected.

    Returns:
        The complete system prompt string.
    """
    parts: list[str] = [_IDENTITY]

    parts.append(build_workspace_section(workspace_path, sandbox_backend))

    if project_context and str(project_context).strip():
        parts.append("\n## Project Context\n")
        parts.append(str(project_context).strip())

    if specialist_instructions and str(specialist_instructions).strip():
        parts.append("\n## Specialist Instructions\n")
        parts.append(str(specialist_instructions).strip())

    parts.append(
        build_tools_section(tool_mode, tool_names, exclude_categories, exclude_tools)
    )

    # Installed agent skills (fold, etc.) — injected before workflow guides.
    parts.append(
        build_skills_section(
            session,
            user_request,
            include_skills=include_skills,
            runtime=runtime,
            sandbox_backend=sandbox_backend,
        )
    )

    parts.append(build_knowledge_sections())
    parts.append(_SYNTHESIS_INSTRUCTIONS)

    if data_context:
        parts.append("\n## Data Context\n")
        parts.append(data_context)

    if history:
        parts.append("\n## Prior Conversation\n")
        parts.append(history)

    prompt = "\n".join(parts)
    logger.info(
        "Built system prompt: %d chars, %d sections",
        len(prompt),
        len(parts),
    )
    return prompt
