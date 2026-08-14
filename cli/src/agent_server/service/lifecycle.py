"""Run submission, cancellation, and shutdown mixin for AgentService."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import uuid

from agent_server.models import MessageSource, StartRunResponse

logger = logging.getLogger("agent_server")


class SessionBusyError(RuntimeError):
    pass


class _LifecycleMixin:
    def interrupt(self, session_id: str) -> bool:
        """Cancel an active run and/or clear orphaned ``running`` status.

        Past plan-mode approval hangs and crashed workers can leave sessions
        marked ``running`` with no live task. Stop must still unstick them.
        Also wakes any HITL approval waiter so headless runs do not zombie.
        """
        try:
            from agent.hitl import clear_session_grants, get_approval_broker

            get_approval_broker().cancel(session_id, reason="Run interrupted")
            clear_session_grants(session_id)
        except Exception:  # noqa: BLE001
            logger.debug("HITL broker cancel failed", exc_info=True)

        # Stop the worker thread first — cancelling the asyncio Task alone does
        # not stop ``asyncio.to_thread``; the agent keeps streaming otherwise.
        runner = self._active_runners.get(session_id)
        if runner is not None:
            request_interrupt = getattr(runner, "request_interrupt", None)
            if callable(request_interrupt):
                try:
                    request_interrupt(force=True)
                except Exception:  # noqa: BLE001
                    logger.debug(
                        "runner.request_interrupt failed",
                        exc_info=True,
                        extra={"session_id": session_id},
                    )

        task = self._active_runs.get(session_id)
        cancelled = False
        if task is not None and not task.done():
            task.cancel()
            cancelled = True

        session = self.store.get_session(session_id)
        if session is None:
            return cancelled

        if session.status not in {"running", "awaiting_approval"}:
            return cancelled

        # Always clear stuck running status so Stop is reliable even when the
        # worker is gone or CancelledError never surfaces from a hung thread.
        # Status flip also gates emit_runtime_event so zombie threads go quiet.
        self.store.set_session_status(session_id, "interrupted")
        if not cancelled:
            run_id = self._run_ids.get(session_id)
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type="run.interrupted",
                payload={"reason": "Run interrupted"},
            )
        return True

    def submit_approvals(
        self,
        session_id: str,
        *,
        decisions: list[dict],
        interrupt_id: str | None = None,
    ) -> dict:
        """Resolve a pending HITL interrupt for a headless (desktop) run."""
        from agent.hitl import get_approval_broker

        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        broker = get_approval_broker()
        pending = broker.get_pending(session_id)
        if pending is None:
            raise LookupError("No pending approval for this session.")
        broker.submit(
            session_id,
            decisions,
            interrupt_id=interrupt_id,
        )
        return {
            "accepted": True,
            "interrupt_id": pending.get("interrupt_id"),
        }

    async def delete_session(self, session_id: str) -> bool:
        task = self._active_runs.get(session_id)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        deleted = self.store.delete_session(session_id)
        if deleted:
            # Notify the global session bus so subscribers can prune the
            # chat from their cache without polling. Lazy import keeps the
            # service layer free of a hard bus dependency at import time.
            try:
                from agent_server.session_event_bus import (  # noqa: PLC0415
                    SessionEventType,
                    session_event_bus,
                )

                session_event_bus.publish(
                    SessionEventType.SESSION_DELETED,
                    {"sessionId": session_id},
                )
            except Exception:  # noqa: BLE001
                pass
        return deleted

    def submit_message(
        self,
        *,
        session_id: str,
        content: str,
        source: MessageSource | None = None,
    ) -> StartRunResponse:
        active = self._active_runs.get(session_id)
        if active is not None and not active.done():
            raise SessionBusyError("This session already has an active run.")

        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)

        text = content.strip()
        if not text:
            raise ValueError("Message content cannot be empty.")

        session = self.ensure_workspace(session_id)

        user_message = self.store.add_message(
            session_id=session_id, role="user", content=text, source=source
        )
        run_id = str(uuid.uuid4())
        self.store.set_session_status(session_id, "running")
        self.store.append_event(
            session_id=session_id,
            run_id=run_id,
            event_type="run.started",
            payload={"messageId": user_message.id},
        )

        # Bench / Slack worker threads have no running loop — schedule onto
        # the uvicorn loop bound at app startup (sandbox_event_bus).
        def _start_task() -> None:
            task = asyncio.create_task(
                self._execute_run(
                    session_id=session_id,
                    run_id=run_id,
                    content=text,
                    workspace_path=session.workspace_path,
                ),
                name=f"fastfold-run-{run_id}",
            )
            self._active_runs[session_id] = task
            self._run_ids[session_id] = run_id
            task.add_done_callback(lambda done: self._clear_run(session_id, done))

        try:
            asyncio.get_running_loop()
            _start_task()
        except RuntimeError:
            from agent_server.sandbox_events import sandbox_event_bus

            loop = getattr(sandbox_event_bus, "_loop", None)
            if loop is None or not loop.is_running():
                raise RuntimeError("no running event loop") from None
            done: concurrent.futures.Future[None] = concurrent.futures.Future()

            def _on_loop() -> None:
                try:
                    _start_task()
                    done.set_result(None)
                except Exception as exc:  # noqa: BLE001
                    done.set_exception(exc)

            loop.call_soon_threadsafe(_on_loop)
            done.result(timeout=30)
        return StartRunResponse(run_id=run_id)

    def _clear_run(self, session_id: str, task: asyncio.Task[None]) -> None:
        if self._active_runs.get(session_id) is task:
            self._active_runs.pop(session_id, None)
            self._run_ids.pop(session_id, None)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Unhandled agent run failure", extra={"session_id": session_id})

    async def shutdown(self) -> None:
        tasks = [task for task in self._active_runs.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
