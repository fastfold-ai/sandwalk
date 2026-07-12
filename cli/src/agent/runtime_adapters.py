"""
Provider runtime adapters for agent execution.

Defines a thin provider-agnostic interface used by AgentRunner so provider-
specific SDK/API logic can evolve independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class RuntimeEvent:
    """Normalized event emitted by a runtime adapter."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeExecutionOutput:
    """Provider-agnostic execution output consumed by AgentRunner."""

    full_text: list[str]
    tool_calls: list[dict[str, Any]]
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    pending_background_tasks: list[dict[str, Any]] = field(default_factory=list)
    completed_background_tasks: list[dict[str, Any]] = field(default_factory=list)
    trace_events: list[dict[str, Any]] = field(default_factory=list)


class RuntimeAdapter(Protocol):
    """Protocol for provider-specific execution adapters."""

    async def run(self) -> RuntimeExecutionOutput:
        """Execute one agent turn and return normalized output."""
        ...

