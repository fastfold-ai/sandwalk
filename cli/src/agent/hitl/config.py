"""Interrupt-on configuration for sensitive tool calls."""

from __future__ import annotations

from typing import Any

# Sanitized LangChain tool name for registry ``skills.manage``.
SKILLS_MANAGE_TOOL = "skills_manage"

_SENSITIVE_ACTIONS = frozenset({"install", "add", "remove", "uninstall"})


def _truthy(value: Any, default: bool = True) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def skills_manage_needs_approval(args: dict[str, Any] | None) -> bool:
    """Return True when skills.manage args should pause for HITL."""
    payload = args if isinstance(args, dict) else {}
    action = str(payload.get("action") or "list").strip().lower()
    if action in _SENSITIVE_ACTIONS:
        return True
    if action == "create":
        return _truthy(payload.get("install"), default=True)
    return False


def skills_manage_when(request: Any) -> bool:
    """``InterruptOnConfig.when`` predicate for ``skills_manage``."""
    tool_call = getattr(request, "tool_call", None)
    if not isinstance(tool_call, dict):
        tool_call = {}
    args = tool_call.get("args")
    if not isinstance(args, dict):
        args = {}
    if not skills_manage_needs_approval(args):
        return False
    from agent.hitl.grants import grant_key_for_skills_kwargs, has_grant

    return not has_grant(grant_key_for_skills_kwargs(args))


def build_interrupt_on() -> dict[str, Any]:
    """Deep Agents ``interrupt_on`` mapping for first-party gated tools."""
    return {
        SKILLS_MANAGE_TOOL: {
            "allowed_decisions": ["approve", "edit", "reject"],
            "when": skills_manage_when,
            "description": (
                "Approve installing or removing an agent skill before it runs."
            ),
        }
    }
