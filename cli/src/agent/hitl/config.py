"""Interrupt-on configuration for sensitive tool calls."""

from __future__ import annotations

from typing import Any

# Sanitized LangChain tool name for registry ``skills.manage``.
SKILLS_MANAGE_TOOL = "skills_manage"

# Sanitized LangChain tool name for registry ``slack.send_message``.
SLACK_SEND_TOOL = "slack_send_message"

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
        return _truthy(payload.get("install"), default=False)
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


def slack_target_is_trusted(target: str, session_id: str | None) -> bool:
    """Whether this session already owns the Slack thread it wants to reply to.

    A mention creates the session and records the thread mapping, so replying
    there is what the user asked for. Any *other* destination is the agent
    choosing to message somewhere new, which still needs a human.
    """
    handle = (target or "").strip()
    sid = (session_id or "").strip()
    if not handle or not sid:
        return False
    try:
        from agent_server.store import AgentStore
    except ImportError:
        return False
    store = AgentStore()
    try:
        return store.get_slack_mention_session(handle) == sid
    except Exception:
        return False
    finally:
        store.close()


def slack_send_when(request: Any) -> bool:
    """``InterruptOnConfig.when`` predicate for ``slack_send_message``."""
    tool_call = getattr(request, "tool_call", None)
    if not isinstance(tool_call, dict):
        tool_call = {}
    args = tool_call.get("args")
    if not isinstance(args, dict):
        args = {}

    from agent.hitl.context import get_hitl_context
    from agent.hitl.grants import has_grant

    ctx = get_hitl_context()
    session_id = ctx.session_id if ctx is not None else None
    target = str(args.get("target") or "").strip()

    if slack_target_is_trusted(target, session_id):
        return False
    return not has_grant(grant_key_for_slack_target(target))


def grant_key_for_slack_target(target: str | None) -> str | None:
    handle = (target or "").strip()
    if not handle:
        return None
    return f"{SLACK_SEND_TOOL}:{handle}"


def build_interrupt_on() -> dict[str, Any]:
    """Deep Agents ``interrupt_on`` mapping for first-party gated tools."""
    return {
        SKILLS_MANAGE_TOOL: {
            "allowed_decisions": ["approve", "edit", "reject"],
            "when": skills_manage_when,
            "description": (
                "Approve installing or removing an agent skill before it runs."
            ),
        },
        SLACK_SEND_TOOL: {
            "allowed_decisions": ["approve", "edit", "reject"],
            "when": slack_send_when,
            "description": "Approve sending this message to Slack.",
        },
    }
