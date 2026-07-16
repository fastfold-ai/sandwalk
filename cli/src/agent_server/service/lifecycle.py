"""Run submission, cancellation, and shutdown mixin for AgentService."""

from __future__ import annotations

import asyncio
import logging
import uuid

from agent_server.models import StartRunResponse

logger = logging.getLogger("agent_server")


class SessionBusyError(RuntimeError):
    pass


class _LifecycleMixin:
    def interrupt(self, session_id: str) -> bool:
        task = self._active_runs.get(session_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def delete_session(self, session_id: str) -> bool:
        task = self._active_runs.get(session_id)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return self.store.delete_session(session_id)

    def submit_message(self, *, session_id: str, content: str) -> StartRunResponse:
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

        user_message = self.store.add_message(session_id=session_id, role="user", content=text)
        run_id = str(uuid.uuid4())
        self.store.set_session_status(session_id, "running")
        self.store.append_event(
            session_id=session_id,
            run_id=run_id,
            event_type="run.started",
            payload={"messageId": user_message.id},
        )

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
