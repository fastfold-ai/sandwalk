"""Progress-event forwarding for AgentLoop.run (terminal callback + AgentStore)."""

import logging

logger = logging.getLogger("loop")


class LoopProgressMixin:
    """Owns translation of runner progress events into AgentStore events."""

    def _emit_store_progress(
        self,
        *,
        session_id: str,
        run_id: str,
        event: str = "activity",
        progress_callback=None,
        **payload,
    ) -> None:
        """Forward progress to the terminal and dual-write tool events for the UI."""
        if progress_callback is not None:
            try:
                progress_callback(event, **payload)
            except TypeError:
                # Legacy callbacks may only accept a status string.
                text = payload.get("text") or payload.get("activity") or event
                try:
                    progress_callback(str(text))
                except Exception:
                    pass
            except Exception:
                logger.debug("CLI progress callback failed", exc_info=True)

        event_type = {
            "stream": "assistant.delta",
            "tool_start": "tool.started",
            "tool_end": "tool.completed",
            "usage": "run.usage",
            "activity": "run.progress",
        }.get(event)
        if event_type is None:
            return
        if event == "stream":
            event_payload = {"delta": str(payload.get("delta") or "")}
        elif event == "tool_start":
            event_payload = {
                "name": str(payload.get("name") or "tool"),
                "arguments": payload.get("arguments") or {},
                "toolCallId": str(payload.get("tool_call_id") or ""),
            }
        elif event == "tool_end":
            event_payload = {
                "name": str(payload.get("name") or "tool"),
                "output": payload.get("output"),
                "isError": bool(payload.get("is_error")),
                "durationSeconds": float(payload.get("duration_s") or 0.0),
                "toolCallId": str(payload.get("tool_call_id") or ""),
            }
        elif event == "usage":
            from agent_server.usage_service.parse import (
                active_model_id,
                active_provider,
                parse_usage_tokens,
            )

            tokens = parse_usage_tokens(payload)
            model_id = active_model_id()
            provider = active_provider()
            event_payload = {
                "inputTokens": tokens["input_tokens"],
                "outputTokens": tokens["output_tokens"],
                "cacheReadInputTokens": tokens["cache_read_tokens"],
                "cacheCreationInputTokens": tokens["cache_creation_tokens"],
                "input_tokens": tokens["input_tokens"],
                "output_tokens": tokens["output_tokens"],
                "cache_read_input_tokens": tokens["cache_read_tokens"],
                "cache_creation_input_tokens": tokens["cache_creation_tokens"],
            }
            if model_id:
                event_payload["modelId"] = model_id
                event_payload["model_id"] = model_id
            if provider:
                event_payload["provider"] = provider
        else:
            event_payload = {
                "text": str(payload.get("text") or payload.get("activity") or "")
            }
        try:
            stored = self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type=event_type,
                payload=event_payload,
            )
            if event == "usage":
                from agent_server.usage_service.parse import (
                    day_key_from_timestamp,
                    parse_usage_tokens,
                    surface_for_session,
                )

                tokens = parse_usage_tokens(event_payload)
                model_id = (
                    str(
                        event_payload.get("model_id")
                        or event_payload.get("modelId")
                        or ""
                    ).strip()
                    or None
                )
                provider = (
                    str(event_payload.get("provider") or "").strip().lower() or None
                )
                session = self.store.get_session(session_id)
                self.store.upsert_usage_run(
                    run_id=run_id,
                    session_id=session_id,
                    day=day_key_from_timestamp(
                        getattr(stored, "timestamp", None)
                    ),
                    surface=surface_for_session(session),
                    model_id=model_id,
                    provider=provider,
                    input_tokens=tokens["input_tokens"],
                    output_tokens=tokens["output_tokens"],
                    cache_read_tokens=tokens["cache_read_tokens"],
                    cache_creation_tokens=tokens["cache_creation_tokens"],
                )
            if event == "tool_start":
                from agent_server.service.plan_events import (
                    plan_created_payload_from_tool_call,
                )

                plan_payload = plan_created_payload_from_tool_call(
                    name=str(event_payload.get("name") or ""),
                    arguments=event_payload.get("arguments"),
                )
                if plan_payload is not None:
                    self.store.append_event(
                        session_id=session_id,
                        run_id=run_id,
                        event_type="plan.created",
                        payload=plan_payload,
                    )
        except Exception:
            logger.debug(
                "Failed to dual-write CLI progress event",
                exc_info=True,
                extra={"session_id": session_id, "event": event},
            )
