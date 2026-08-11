"""Deep Agents middleware system-prompt text for prompt-budget parity.

These strings are injected at request time by TodoList / Filesystem /
SubAgent middleware. Knowledge Level strips write_todos / task blocks when
those tools are excluded; the filesystem guidance remains (scaffolding).
"""

from __future__ import annotations

from collections.abc import Iterable


def middleware_system_prompt_text(
    *,
    excluded_tools: Iterable[str] | None = None,
) -> str:
    """Return middleware system text that remains after Knowledge Level filtering."""
    excluded = {str(name) for name in (excluded_tools or ()) if str(name)}
    parts: list[str] = []

    if "write_todos" not in excluded:
        from langchain.agents.middleware.todo import WRITE_TODOS_SYSTEM_PROMPT

        parts.append(str(WRITE_TODOS_SYSTEM_PROMPT or "").strip())

    from deepagents.middleware.filesystem import FILESYSTEM_SYSTEM_PROMPT

    parts.append(str(FILESYSTEM_SYSTEM_PROMPT or "").strip())

    if "task" not in excluded:
        # Default SubAgentMiddleware system_prompt (task tool guidance).
        import inspect

        from deepagents.middleware.subagents import SubAgentMiddleware

        default = inspect.signature(SubAgentMiddleware.__init__).parameters[
            "system_prompt"
        ].default
        if isinstance(default, str) and default.strip():
            parts.append(default.strip())

    return "\n\n".join(p for p in parts if p)
