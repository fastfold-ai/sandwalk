"""Runtime progress-callback → stored session-event translation for a run."""

from __future__ import annotations

from typing import Any

from agent_server.store import AgentStore

_EVENT_TYPES = {
    "stream": "assistant.delta",
    "tool_start": "tool.started",
    "tool_end": "tool.completed",
    "usage": "run.usage",
    "activity": "run.progress",
}


def _event_payload(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    if event == "stream":
        return {"delta": str(payload.get("delta") or "")}
    if event == "tool_start":
        return {
            "name": str(payload.get("name") or "tool"),
            "arguments": payload.get("arguments") or {},
            "toolCallId": str(payload.get("tool_call_id") or ""),
        }
    if event == "tool_end":
        return {
            "name": str(payload.get("name") or "tool"),
            "output": payload.get("output"),
            "isError": bool(payload.get("is_error")),
            "durationSeconds": float(payload.get("duration_s") or 0.0),
            "toolCallId": str(payload.get("tool_call_id") or ""),
        }
    return dict(payload)


def _todos_from_write_todos_call(event_payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    arguments = event_payload.get("arguments")
    raw_todos = arguments.get("todos") if isinstance(arguments, dict) else None
    if not isinstance(raw_todos, list):
        return None
    todos = []
    for index, item in enumerate(raw_todos):
        if not isinstance(item, dict):
            continue
        content_value = str(item.get("content") or "").strip()
        if not content_value:
            continue
        todos.append(
            {
                "id": str(item.get("id") or f"todo-{index + 1}"),
                "content": content_value,
                "status": str(item.get("status") or "pending"),
                "activeForm": item.get("activeForm") or item.get("active_form"),
            }
        )
    return todos


def make_event_emitter(store: AgentStore, session_id: str, run_id: str):
    def emit_runtime_event(event: str, **payload: Any) -> None:
        event_type = _EVENT_TYPES.get(event)
        if event_type is None:
            return
        event_payload = _event_payload(event, payload)
        store.append_event(
            session_id=session_id,
            run_id=run_id,
            event_type=event_type,
            payload=event_payload,
        )
        if event == "tool_start" and event_payload.get("name") == "write_todos":
            todos = _todos_from_write_todos_call(event_payload)
            if todos is not None:
                store.append_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type="todos.updated",
                    payload={"todos": todos},
                )

    return emit_runtime_event
