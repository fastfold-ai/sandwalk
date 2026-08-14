"""Runtime progress-callback → stored session-event translation for a run."""

from __future__ import annotations

from typing import Any

from agent_server.service.plan_events import plan_created_payload_from_tool_call
from agent_server.store import AgentStore
from agent_server.usage_service.parse import (
    active_model_id,
    active_provider,
    day_key_from_timestamp,
    parse_usage_tokens,
    surface_for_session,
)

_EVENT_TYPES = {
    "stream": "assistant.delta",
    "tool_start": "tool.started",
    "tool_end": "tool.completed",
    "usage": "run.usage",
    "activity": "run.progress",
    "approval_required": "run.awaiting_approval",
    "approval_resolved": "run.approval_resolved",
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
    if event == "approval_required":
        review_configs = []
        for raw in payload.get("review_configs") or []:
            if not isinstance(raw, dict):
                continue
            review_configs.append(
                {
                    "actionName": str(
                        raw.get("actionName") or raw.get("action_name") or ""
                    ),
                    "allowedDecisions": list(
                        raw.get("allowedDecisions")
                        or raw.get("allowed_decisions")
                        or []
                    ),
                    "description": raw.get("description"),
                }
            )
        return {
            "interruptId": str(payload.get("interrupt_id") or ""),
            "actionRequests": list(payload.get("action_requests") or []),
            "reviewConfigs": review_configs,
        }
    if event == "approval_resolved":
        return {
            "interruptId": str(payload.get("interrupt_id") or ""),
            "decisions": list(payload.get("decisions") or []),
        }
    if event == "usage":
        tokens = parse_usage_tokens(payload)
        model_id = active_model_id()
        provider = active_provider()
        out = {
            "input_tokens": tokens["input_tokens"],
            "output_tokens": tokens["output_tokens"],
            "cache_read_input_tokens": tokens["cache_read_tokens"],
            "cache_creation_input_tokens": tokens["cache_creation_tokens"],
            "inputTokens": tokens["input_tokens"],
            "outputTokens": tokens["output_tokens"],
            "cacheReadInputTokens": tokens["cache_read_tokens"],
            "cacheCreationInputTokens": tokens["cache_creation_tokens"],
        }
        if model_id:
            out["model_id"] = model_id
            out["modelId"] = model_id
        if provider:
            out["provider"] = provider
        for key in (
            "tokens_per_second",
            "prompt_tokens_per_second",
            "prompt_eval_seconds",
            "generation_seconds",
            "time_to_first_token",
            "estimated",
        ):
            if key in payload and payload[key] is not None:
                out[key] = payload[key]
        return out
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
    seed = store.get_session(session_id)
    is_bench = getattr(seed, "source", None) == "bench"

    def emit_runtime_event(event: str, **payload: Any) -> None:
        event_type = _EVENT_TYPES.get(event)
        if event_type is None:
            return
        if event == "stream":
            # Perf probe: run pipeline reports tail latency after last token.
            import time

            emit_runtime_event.last_stream_at = time.monotonic()
            # Bench sessions never stream in the chat UI — skip per-token
            # SQLite reads/writes (dominant cost under multi-worker benches).
            if is_bench:
                return
        # High-frequency progress noise; final message/tools/usage still persist.
        if is_bench and event == "activity":
            return
        session = seed
        if not is_bench:
            # After Stop, status flips to interrupted/idle/error. Drop zombie
            # emissions from a still-running worker thread so the UI stays quiet.
            session = store.get_session(session_id)
            if session is not None and session.status not in {
                "running",
                "awaiting_approval",
            }:
                return
        event_payload = _event_payload(event, payload)
        if event == "approval_required":
            # Keep runId on the wire for the UI even though payload omits it.
            event_payload = {**event_payload, "runId": run_id}
            store.set_session_status(session_id, "awaiting_approval")
        elif event == "approval_resolved":
            store.set_session_status(session_id, "running")
        stored = store.append_event(
            session_id=session_id,
            run_id=run_id,
            event_type=event_type,
            payload=event_payload,
            notify=not is_bench,
        )
        if event == "usage":
            tokens = parse_usage_tokens(event_payload)
            model_id = (
                str(event_payload.get("model_id") or event_payload.get("modelId") or "")
                .strip()
                or None
            )
            provider = (
                str(event_payload.get("provider") or "").strip().lower() or None
            )
            day = day_key_from_timestamp(
                getattr(stored, "timestamp", None) if stored is not None else None
            )
            store.upsert_usage_run(
                run_id=run_id,
                session_id=session_id,
                day=day,
                surface=surface_for_session(session),
                model_id=model_id,
                provider=provider,
                input_tokens=tokens["input_tokens"],
                output_tokens=tokens["output_tokens"],
                cache_read_tokens=tokens["cache_read_tokens"],
                cache_creation_tokens=tokens["cache_creation_tokens"],
            )
        if is_bench:
            return
        if event == "tool_start" and event_payload.get("name") == "write_todos":
            todos = _todos_from_write_todos_call(event_payload)
            if todos is not None:
                store.append_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type="todos.updated",
                    payload={"todos": todos},
                )
        if event == "tool_start":
            plan_payload = plan_created_payload_from_tool_call(
                name=str(event_payload.get("name") or ""),
                arguments=event_payload.get("arguments"),
            )
            if plan_payload is not None:
                store.append_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type="plan.created",
                    payload=plan_payload,
                )

    emit_runtime_event.last_stream_at = None
    return emit_runtime_event
