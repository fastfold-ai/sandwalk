"""Middleware that applies Knowledge Level tool + system-prompt exclusions.

Deep Agents' ``_ToolExclusionMiddleware`` only removes tools from the model
request. ``TodoListMiddleware`` / ``SubAgentMiddleware`` still inject large
system-prompt blocks for ``write_todos`` and ``task`` even when those tools
are excluded — which is why Low can show ~3k in Context but ~7–8k billed
input_tokens.

This middleware runs in the user-middleware slot (after those injections) and:
1. Filters excluded tools from the request (same as ``_ToolExclusionMiddleware``)
2. Drops system content blocks that document excluded tools
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import SystemMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain.agents.middleware.types import (
        ExtendedModelResponse,
        ModelRequest,
        ModelResponse,
        ResponseT,
    )
    from langchain_core.messages import AIMessage
    from langchain_core.tools import BaseTool


def _tool_name(tool: BaseTool | dict[str, str]) -> str | None:
    if isinstance(tool, dict):
        name = tool.get("name")
        return name if isinstance(name, str) else None
    name = getattr(tool, "name", None)
    return name if isinstance(name, str) else None


def _drop_system_block(text: str, excluded: frozenset[str]) -> bool:
    """Return True when this system block is guidance for an excluded tool."""
    if not text:
        return False
    # Deep Agents / LangChain inject these as dedicated content blocks.
    if "write_todos" in excluded and "## `write_todos`" in text:
        return True
    if "task" in excluded and "## `task`" in text:
        return True
    return False


def _strip_excluded_system_sections(text: str, excluded: frozenset[str]) -> str:
    """Remove markdown sections for excluded tools from a flat system string."""
    if not text or not excluded:
        return text
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    skip_headers: list[str] = []
    if "write_todos" in excluded:
        skip_headers.append("## `write_todos`")
    if "task" in excluded:
        skip_headers.append("## `task`")
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("## "):
            skipping = any(stripped.startswith(h) for h in skip_headers)
        if not skipping:
            out.append(line)
    return "".join(out).strip()


def apply_knowledge_level_to_system_message(
    system_message: SystemMessage | None,
    excluded: frozenset[str],
) -> SystemMessage | None:
    """Drop system blocks / sections that document excluded Deep Agents tools."""
    if system_message is None or not excluded:
        return system_message
    content = system_message.content
    if isinstance(content, list):
        kept: list[Any] = []
        for block in content:
            if isinstance(block, dict):
                text = str(block.get("text") or "")
                if _drop_system_block(text, excluded):
                    continue
                kept.append(block)
            else:
                kept.append(block)
        if kept == content:
            return system_message
        return system_message.model_copy(update={"content": kept})
    if isinstance(content, str):
        stripped = _strip_excluded_system_sections(content, excluded)
        if stripped == content:
            return system_message
        return system_message.model_copy(update={"content": stripped})
    return system_message


class KnowledgeLevelMiddleware(AgentMiddleware[Any, Any, Any]):
    """Filter excluded Deep Agents tools and their system-prompt guidance."""

    def __init__(self, *, excluded: frozenset[str]) -> None:
        self._excluded = frozenset(excluded or ())

    def _filter_request(self, request: ModelRequest[Any]) -> ModelRequest[Any]:
        if not self._excluded:
            return request
        filtered = [t for t in request.tools if _tool_name(t) not in self._excluded]
        system_message = apply_knowledge_level_to_system_message(
            getattr(request, "system_message", None),
            self._excluded,
        )
        return request.override(tools=filtered, system_message=system_message)

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        return handler(self._filter_request(request))

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
        return await handler(self._filter_request(request))
