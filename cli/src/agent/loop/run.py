"""AgentLoop.run: executes a query and records it in the trajectory."""

import logging
import uuid

from agent.loop.clarification import Clarification, ClarificationNeeded

logger = logging.getLogger("loop")


class LoopRunMixin:
    """Owns the top-level run() entry point and title-generation helpers."""

    def run(self, query: str, context: dict | None = None,
            progress_callback=None):
        """Execute a query and record it in the trajectory."""
        run_context = dict(context or {})
        if not str(run_context.get("workspace_path") or "").strip():
            workspace = self.ensure_workspace_path()
            if workspace:
                run_context["workspace_path"] = workspace

        session_id = str(self.trajectory.session_id or "").strip()
        run_id = str(uuid.uuid4())
        user_message_id: str | None = None
        if session_id:
            try:
                title = (
                    (self.trajectory.title or "").strip()
                    or query.strip()[:80]
                    or "New research session"
                )
                self.store.ensure_session(session_id, title=title)
                user_message = self.store.add_message(
                    session_id=session_id,
                    role="user",
                    content=query,
                )
                user_message_id = user_message.id
                self.store.set_session_status(session_id, "running")
                self.store.append_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type="run.started",
                    payload={"messageId": user_message.id},
                )
            except Exception:
                logger.exception(
                    "Failed to mark CLI run started in shared AgentStore",
                    extra={"session_id": session_id},
                )

        def store_progress(event="activity", **payload):
            if not session_id:
                if progress_callback is not None:
                    try:
                        progress_callback(event, **payload)
                    except Exception:
                        pass
                return
            self._emit_store_progress(
                session_id=session_id,
                run_id=run_id,
                event=event,
                progress_callback=progress_callback,
                **payload,
            )

        try:
            result = self._runner.run(
                query, run_context, progress_callback=store_progress
            )
        except Exception:
            if session_id:
                try:
                    self.store.set_session_status(session_id, "failed")
                    self.store.append_event(
                        session_id=session_id,
                        run_id=run_id,
                        event_type="run.failed",
                        payload={"reason": "CLI run raised"},
                    )
                except Exception:
                    pass
            # Drop CLI busy toolbar even when the run fails after UI output.
            try:
                store_progress("turn_complete")
            except Exception:
                pass
            raise

        # Usage footer / final text are already on screen. Clear the CLI scanner
        # before title LLM + store dual-write (can take seconds).
        try:
            store_progress("turn_complete")
        except Exception:
            pass

        # Check for clarification request in result
        if result and result.raw_results:
            clar_data = result.raw_results.get("clarification")
            if isinstance(clar_data, dict) and clar_data.get("clarification_needed"):
                if session_id:
                    try:
                        self.store.set_session_status(session_id, "idle")
                        self.store.append_event(
                            session_id=session_id,
                            run_id=run_id,
                            event_type="run.interrupted",
                            payload={"reason": "clarification_needed"},
                        )
                    except Exception:
                        pass
                raise ClarificationNeeded(Clarification(
                    question=clar_data.get("question", "Could you clarify?"),
                    missing=clar_data.get("missing", []),
                    suggestions=clar_data.get("suggestions", []),
                ))

        # Record turn in trajectory
        if result:
            self.trajectory.add_turn(
                query=query,
                answer=result.summary or "",
                plan=result.plan,
            )
            if not self.trajectory.title or self._is_placeholder_title(
                self.trajectory.title
            ):
                # Headless/server runs: never block completion on a title LLM
                # call — agent_server retitles asynchronously via title_source.
                if self.headless:
                    from agent_server.title import fallback_title_from_query

                    self.trajectory.title = (
                        fallback_title_from_query(query) or "New research session"
                    )
                else:
                    self.trajectory.title = self._generate_title(
                        query, result.summary or ""
                    )
            self.trajectory.model = self.session.current_model
            self.trajectory.save()
            try:
                self._persist_turn_to_store(
                    query,
                    result.summary or "",
                    run_id=run_id if session_id else None,
                    user_message_id=user_message_id,
                )
            except Exception:
                logger.exception(
                    "Failed to dual-write CLI turn into shared AgentStore",
                    extra={"session_id": self.trajectory.session_id},
                )

        return result

    @staticmethod
    def _is_placeholder_title(title: str | None) -> bool:
        from agent_server.title import is_placeholder_title

        return is_placeholder_title(title)

    def _generate_title(self, query: str, answer: str) -> str:
        from agent_server.title import fallback_title_from_query, generate_session_title

        messages = [
            {"role": "user", "content": query},
            {"role": "assistant", "content": answer},
        ]
        result = generate_session_title(messages, fallback_query=query)
        return result.title or (
            fallback_title_from_query(query) or "New research session"
        )
