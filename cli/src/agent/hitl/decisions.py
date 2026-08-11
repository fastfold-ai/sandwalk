"""Build and validate Deep Agents HITL resume decisions."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

DecisionType = Literal["approve", "edit", "reject", "respond"]


class EditedAction(TypedDict):
    name: str
    args: dict[str, Any]


class Decision(TypedDict, total=False):
    type: DecisionType
    message: str
    edited_action: EditedAction
    # "remaining" = also auto-approve matching tools for the rest of this run
    scope: str


def build_approve(*, scope: str | None = None) -> Decision:
    decision: Decision = {"type": "approve"}
    text = (scope or "").strip().lower()
    if text in {"remaining", "all", "run"}:
        decision["scope"] = "remaining"
    return decision


def build_reject(message: str | None = None) -> Decision:
    decision: Decision = {"type": "reject"}
    text = (message or "").strip()
    if text:
        decision["message"] = text
    else:
        decision["message"] = (
            "User rejected this action. Do not retry the same tool call "
            "unless the user explicitly asks."
        )
    return decision


def build_edit(*, name: str, args: dict[str, Any]) -> Decision:
    return {
        "type": "edit",
        "edited_action": {"name": name, "args": dict(args or {})},
    }


def build_respond(message: str) -> Decision:
    return {"type": "respond", "message": (message or "").strip() or "(no message)"}


def _allowed_for_action(
    action: dict[str, Any],
    review_configs: list[dict[str, Any]],
) -> list[str]:
    name = str(action.get("name") or "")
    for cfg in review_configs:
        if str(cfg.get("action_name") or "") == name:
            allowed = cfg.get("allowed_decisions") or []
            return [str(item) for item in allowed]
    return ["approve", "edit", "reject", "respond"]


def validate_decisions(
    decisions: list[dict[str, Any]],
    *,
    action_requests: list[dict[str, Any]],
    review_configs: list[dict[str, Any]] | None = None,
) -> list[Decision]:
    """Validate count/order/types and normalize to Decision dicts."""
    actions = list(action_requests or [])
    configs = list(review_configs or [])
    if len(decisions) != len(actions):
        raise ValueError(
            f"Expected {len(actions)} decision(s), got {len(decisions)}."
        )
    out: list[Decision] = []
    for index, (raw, action) in enumerate(zip(decisions, actions, strict=True)):
        if not isinstance(raw, dict):
            raise ValueError(f"Decision {index} must be an object.")
        dtype = str(raw.get("type") or "").strip().lower()
        allowed = _allowed_for_action(action, configs)
        if dtype not in allowed:
            raise ValueError(
                f"Decision {index} type '{dtype}' not allowed "
                f"(allowed: {', '.join(allowed)})."
            )
        if dtype == "approve":
            out.append(build_approve(scope=str(raw.get("scope") or "") or None))
            continue
        if dtype == "reject":
            out.append(build_reject(str(raw.get("message") or "") or None))
            continue
        if dtype == "respond":
            out.append(build_respond(str(raw.get("message") or "")))
            continue
        if dtype == "edit":
            edited = raw.get("edited_action")
            if not isinstance(edited, dict):
                raise ValueError(f"Decision {index} edit requires edited_action.")
            name = str(edited.get("name") or action.get("name") or "").strip()
            args = edited.get("args")
            if not name:
                raise ValueError(f"Decision {index} edit requires edited_action.name.")
            if not isinstance(args, dict):
                raise ValueError(f"Decision {index} edit requires edited_action.args object.")
            out.append(build_edit(name=name, args=args))
            continue
        raise ValueError(f"Unsupported decision type '{dtype}'.")
    return out


def extract_interrupt_payload(agent: Any, run_config: dict[str, Any]) -> dict[str, Any] | None:
    """Return HITL interrupt value ``{action_requests, review_configs}`` if paused."""
    get_state = getattr(agent, "get_state", None)
    if not callable(get_state):
        return None
    try:
        state = get_state(run_config)
    except Exception:  # noqa: BLE001
        return None

    interrupts = list(getattr(state, "interrupts", None) or ())
    if not interrupts:
        for task in getattr(state, "tasks", None) or ():
            task_interrupts = list(getattr(task, "interrupts", None) or ())
            if task_interrupts:
                interrupts = task_interrupts
                break
    if not interrupts:
        return None

    value = getattr(interrupts[0], "value", None)
    if not isinstance(value, dict):
        return None
    actions = value.get("action_requests")
    if not isinstance(actions, list) or not actions:
        return None
    return {
        "action_requests": actions,
        "review_configs": list(value.get("review_configs") or []),
        "raw": value,
    }
