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
            event_payload = {
                "inputTokens": payload.get("input_tokens"),
                "outputTokens": payload.get("output_tokens"),
                "cacheReadInputTokens": payload.get("cache_read_input_tokens"),
            }
        else:
            event_payload = {
                "text": str(payload.get("text") or payload.get("activity") or "")
            }
        try:
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type=event_type,
                payload=event_payload,
            )
        except Exception:
            logger.debug(
                "Failed to dual-write CLI progress event",
                exc_info=True,
                extra={"session_id": session_id, "event": event},
            )
