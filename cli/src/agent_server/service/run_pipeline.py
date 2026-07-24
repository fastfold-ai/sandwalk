"""Full run pipeline: gather context, drive the agent, persist results."""

from __future__ import annotations

import asyncio
import logging
import threading
import time

from agent_server.service.agent_runner import run_existing_agent
from agent_server.service.context import build_run_context
from agent_server.service.emit_events import make_event_emitter

logger = logging.getLogger("agent_server")


class _RunPipelineMixin:
    async def _execute_run(
        self,
        *,
        session_id: str,
        run_id: str,
        content: str,
        workspace_path: str | None,
    ) -> None:
        try:
            emit_runtime_event = make_event_emitter(self.store, session_id, run_id)
            history = self.store.list_messages(session_id)
            run_context = build_run_context(self.store, session_id)
            run_started_at = time.monotonic()
            summary = await asyncio.to_thread(
                run_existing_agent,
                content,
                workspace_path,
                emit_runtime_event,
                history,
                run_context.mcp_servers,
                run_context.project_context,
                run_context.specialist_instructions,
                run_context.allowed_skill_names,
                session_id,
                run_context.sandbox_backend,
                run_context.allowed_tool_names,
            )
            agent_done_at = time.monotonic()
            last_stream_at = getattr(emit_runtime_event, "last_stream_at", None)
            logger.info(
                "[perf] run %s: agent thread %.2fs; tail after last token %s",
                run_id[:8],
                agent_done_at - run_started_at,
                f"{agent_done_at - last_stream_at:.2f}s"
                if last_stream_at
                else "n/a",
            )
            self._finish_run(session_id, run_id, summary, content)
            logger.info(
                "[perf] run %s: completion events +%.3fs after agent return",
                run_id[:8],
                time.monotonic() - agent_done_at,
            )
        except asyncio.CancelledError:
            try:
                from agent.hitl import get_approval_broker

                get_approval_broker().cancel(session_id, reason="Run cancelled")
            except Exception:  # noqa: BLE001
                pass
            self.store.set_session_status(session_id, "interrupted")
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type="run.interrupted",
                payload={"reason": "Run cancelled"},
            )
            raise
        except InterruptedError as exc:
            self.store.set_session_status(session_id, "interrupted")
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type="run.interrupted",
                payload={"reason": str(exc) or "Run interrupted"},
            )
        except Exception:
            logger.exception(
                "Agent execution failed", extra={"session_id": session_id, "run_id": run_id}
            )
            self.store.set_session_status(session_id, "error")
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type="run.failed",
                payload={"error": "Agent run failed. Check the server logs for details."},
            )

    def _finish_run(self, session_id: str, run_id: str, summary: str, content: str) -> None:
        assistant_message = self.store.add_message(
            session_id=session_id,
            role="assistant",
            content=summary,
        )
        self.store.append_event(
            session_id=session_id,
            run_id=run_id,
            event_type="assistant.message",
            payload={"message": assistant_message.model_dump(mode="json", by_alias=True)},
        )
        self.store.set_session_status(session_id, "idle")
        self.store.append_event(
            session_id=session_id,
            run_id=run_id,
            event_type="run.completed",
            payload={"messageId": assistant_message.id},
        )
        # Title generation is an LLM roundtrip. Run it AFTER completion events
        # and off the event loop — inline it froze the UI (and every request,
        # including the SSE stream) for seconds after streaming finished.
        current_session = self.store.get_session(session_id)
        if current_session and self._should_auto_title(current_session.title):
            threading.Thread(
                target=self._retitle_after_run,
                args=(session_id, run_id, content),
                name=f"retitle-{session_id[:8]}",
                daemon=True,
            ).start()

    def _retitle_after_run(self, session_id: str, run_id: str, content: str) -> None:
        try:
            from agent_server.title import generate_session_title

            history_for_title = [
                {"role": message.role, "content": message.content}
                for message in self.store.list_messages(session_id)
            ]
            generated_title = generate_session_title(
                history_for_title, fallback_query=content
            )
            if not generated_title:
                return
            updated_session = self.store.update_session(session_id, title=generated_title)
            if updated_session is not None:
                self.store.append_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type="session.updated",
                    payload={
                        "session": updated_session.model_dump(mode="json", by_alias=True)
                    },
                )
        except Exception:  # noqa: BLE001 — titling is best-effort, never fail a run
            logger.debug("Session retitle failed", exc_info=True)
