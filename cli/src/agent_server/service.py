"""Application service for durable agent sessions and runs."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from agent.config import CONFIG_DIR
from agent_server.models import AgentSession, StartRunResponse
from agent_server.store import AgentStore

logger = logging.getLogger("agent_server")


def default_workspace_path(session_id: str) -> Path:
    """Canonical per-session workspace root used by the agent server and UI."""
    return (CONFIG_DIR / "workspaces" / session_id).resolve()


class SessionBusyError(RuntimeError):
    pass


class AgentService:
    """Owns active runs while delegating persistence to :class:`AgentStore`."""

    def __init__(self, store: AgentStore) -> None:
        self.store = store
        self._active_runs: dict[str, asyncio.Task[None]] = {}
        self._run_ids: dict[str, str] = {}

    def ensure_workspace(self, session_id: str) -> AgentSession:
        """Ensure the session has a writable workspace directory on disk."""
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        if session.workspace_path:
            workspace = Path(session.workspace_path).expanduser().resolve()
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "uploads").mkdir(parents=True, exist_ok=True)
            (workspace / "outputs").mkdir(parents=True, exist_ok=True)
            self._import_shared_fork_files(session_id, workspace)
            return session
        workspace = default_workspace_path(session_id)
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "uploads").mkdir(parents=True, exist_ok=True)
        (workspace / "outputs").mkdir(parents=True, exist_ok=True)
        self._import_shared_fork_files(session_id, workspace)
        updated = self.store.set_workspace_path(session_id, str(workspace))
        if updated is None:
            raise KeyError(session_id)
        return updated

    @staticmethod
    def _import_shared_fork_files(session_id: str, workspace: Path) -> None:
        """Best-effort: copy forked share files into the session workspace."""
        try:
            from agent.config import Config
            from agent.trajectory import Trajectory

            trajectory = Trajectory.load(session_id)
        except Exception:
            return
        if trajectory is None:
            return
        usage = trajectory.get_usage_data() if hasattr(trajectory, "get_usage_data") else {}
        share_id = str((usage or {}).get("imported_from_share_id") or "").strip()
        if not share_id:
            return

        existing = [
            path
            for path in workspace.rglob("*")
            if path.is_file() and path.name not in {".DS_Store"}
        ]
        if existing:
            return

        candidates: list[Path] = []
        try:
            cfg = Config.load()
            output_root = Path(
                str(cfg.get("sandbox.output_dir") or (Path.cwd() / "outputs"))
            ).expanduser().resolve()
            candidates.append(output_root / "shared_forks" / share_id)
        except Exception:
            pass
        candidates.append((Path.cwd() / "outputs" / "shared_forks" / share_id).resolve())

        import shutil

        for candidate in candidates:
            if not candidate.is_dir():
                continue
            for child in candidate.iterdir():
                destination = workspace / child.name
                try:
                    if child.is_dir():
                        shutil.copytree(child, destination, dirs_exist_ok=True)
                    else:
                        shutil.copy2(child, destination)
                except Exception:
                    continue
            return

    @staticmethod
    def _should_auto_title(title: str | None) -> bool:
        from agent_server.title import is_placeholder_title

        return is_placeholder_title(title)

    def auto_title_session(self, session_id: str, *, force: bool = False) -> AgentSession:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        if not force and not self._should_auto_title(session.title):
            return session

        from agent_server.title import generate_session_title

        messages = [
            {"role": message.role, "content": message.content}
            for message in self.store.list_messages(session_id)
        ]
        fallback = next(
            (
                message.content
                for message in self.store.list_messages(session_id)
                if message.role == "user" and str(message.content or "").strip()
            ),
            None,
        )
        title = generate_session_title(messages, fallback_query=fallback)
        if not title:
            return session
        updated = self.store.update_session(session_id, title=title)
        if updated is None:
            raise KeyError(session_id)
        return updated

    def create_session(
        self,
        *,
        title: str | None,
        workspace_path: str | None,
        project_id: str | None = None,
    ) -> AgentSession:
        normalized_workspace: str | None = None
        if workspace_path:
            workspace = Path(workspace_path).expanduser().resolve()
            if not workspace.is_dir():
                raise ValueError(f"Workspace directory does not exist: {workspace}")
            normalized_workspace = str(workspace)
        session = self.store.create_session(
            title=title,
            workspace_path=normalized_workspace,
            project_id=project_id,
        )
        if normalized_workspace is None:
            workspace = default_workspace_path(session.id)
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "uploads").mkdir(parents=True, exist_ok=True)
            (workspace / "outputs").mkdir(parents=True, exist_ok=True)
            session = self.store.set_workspace_path(session.id, str(workspace)) or session
        self.store.append_event(
            session_id=session.id,
            event_type="session.created",
            payload={"session": session.model_dump(mode="json", by_alias=True)},
        )
        return session

    def update_session(
        self,
        *,
        session_id: str,
        title: str | None,
        organize_label: str | None,
        update_organize_label: bool,
        project_id: str | None = None,
        update_project_id: bool = False,
    ) -> AgentSession:
        session = self.store.update_session(
            session_id,
            title=title,
            organize_label=organize_label,
            update_organize_label=update_organize_label,
            project_id=project_id,
            update_project_id=update_project_id,
        )
        if session is None:
            raise KeyError(session_id)
        self.store.append_event(
            session_id=session.id,
            event_type="session.updated",
            payload={"session": session.model_dump(mode="json", by_alias=True)},
        )
        return session

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

    async def _execute_run(
        self,
        *,
        session_id: str,
        run_id: str,
        content: str,
        workspace_path: str | None,
    ) -> None:
        try:
            def emit_runtime_event(event: str, **payload) -> None:
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
                else:
                    event_payload = dict(payload)
                self.store.append_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type=event_type,
                    payload=event_payload,
                )
                if event == "tool_start" and event_payload.get("name") == "write_todos":
                    arguments = event_payload.get("arguments")
                    raw_todos = arguments.get("todos") if isinstance(arguments, dict) else None
                    if isinstance(raw_todos, list):
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
                                    "activeForm": item.get("activeForm")
                                    or item.get("active_form"),
                                }
                            )
                        self.store.append_event(
                            session_id=session_id,
                            run_id=run_id,
                            event_type="todos.updated",
                            payload={"todos": todos},
                        )

            history = self.store.list_messages(session_id)
            from agent_server.mcp_service import McpService

            mcp_servers = McpService(self.store).resolve_runtime_servers()
            project_context = None
            current = self.store.get_session(session_id)
            if current and current.project_id:
                project = self.store.get_project(current.project_id)
                if project and project.agent_context:
                    project_context = project.agent_context
            summary = await asyncio.to_thread(
                self._run_existing_agent,
                content,
                workspace_path,
                emit_runtime_event,
                history,
                mcp_servers,
                project_context,
            )
            assistant_message = self.store.add_message(
                session_id=session_id,
                role="assistant",
                content=summary,
            )
            current_session = self.store.get_session(session_id)
            if current_session and self._should_auto_title(current_session.title):
                from agent_server.title import generate_session_title

                history_for_title = [
                    {"role": message.role, "content": message.content}
                    for message in self.store.list_messages(session_id)
                ]
                generated_title = generate_session_title(
                    history_for_title,
                    fallback_query=content,
                )
                if generated_title:
                    updated_session = self.store.update_session(
                        session_id,
                        title=generated_title,
                    )
                    if updated_session is not None:
                        self.store.append_event(
                            session_id=session_id,
                            run_id=run_id,
                            event_type="session.updated",
                            payload={
                                "session": updated_session.model_dump(
                                    mode="json",
                                    by_alias=True,
                                )
                            },
                        )
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type="assistant.message",
                payload={
                    "message": assistant_message.model_dump(mode="json", by_alias=True)
                },
            )
            self.store.set_session_status(session_id, "idle")
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type="run.completed",
                payload={"messageId": assistant_message.id},
            )
        except asyncio.CancelledError:
            self.store.set_session_status(session_id, "interrupted")
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type="run.interrupted",
                payload={"reason": "Run cancelled"},
            )
            raise
        except Exception:
            logger.exception("Agent execution failed", extra={"session_id": session_id, "run_id": run_id})
            self.store.set_session_status(session_id, "error")
            self.store.append_event(
                session_id=session_id,
                run_id=run_id,
                event_type="run.failed",
                payload={"error": "Agent run failed. Check the server logs for details."},
            )

    @staticmethod
    def _run_existing_agent(
        content: str,
        workspace_path: str | None,
        progress_callback,
        history,
        mcp_servers,
        project_context: str | None = None,
    ) -> str:
        """Temporary adapter until AgentRunner is split into AgentRuntime."""
        from agent.config import Config
        from agent.runner import AgentRunner
        from agent.session import Session
        from agent.trajectory import Trajectory

        config = Config.load()
        if workspace_path:
            # Keep sandbox plots/CSVs inside the session workspace so the UI
            # file tree can list agent-generated artifacts for this chat.
            output_dir = Path(workspace_path).expanduser().resolve() / "outputs"
            output_dir.mkdir(parents=True, exist_ok=True)
            config.set("sandbox.output_dir", str(output_dir))
        session = Session(config=config, verbose=False, mode="batch")
        trajectory = Trajectory(session_id=None)
        pending_user: str | None = None
        for message in history:
            if message.role == "user":
                pending_user = message.content
            elif message.role == "assistant" and pending_user is not None:
                trajectory.add_turn(pending_user, message.content)
                pending_user = None
        runner = AgentRunner(session, trajectory=trajectory, headless=True)
        context: dict = {"workspace_path": workspace_path} if workspace_path else {}
        if mcp_servers:
            context["mcp_servers"] = mcp_servers
        if project_context:
            context["project_context"] = project_context
        result = runner.run(content, context, progress_callback=progress_callback)
        return result.summary or "Done."

    async def shutdown(self) -> None:
        tasks = [task for task in self._active_runs.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
