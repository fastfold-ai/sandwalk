"""Adapter that drives the CLI's AgentRunner from a stored session's history."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


def run_existing_agent(
    content: str,
    workspace_path: str | None,
    progress_callback,
    history,
    mcp_servers,
    project_context: str | None = None,
    specialist_instructions: str | None = None,
    allowed_skill_names: list[str] | None = None,
    session_id: str | None = None,
    sandbox_backend: str | None = None,
    allowed_tool_names: list[str] | None = None,
    on_runner_ready: Callable[[Any], None] | None = None,
    on_runner_done: Callable[[], None] | None = None,
    provider: str | None = None,
    model: str | None = None,
    openai_profile_id: str | None = None,
    capy_mode: bool = False,
) -> str:
    """Temporary adapter until AgentRunner is split into AgentRuntime."""
    from agent.config import Config
    from agent.runner import AgentRunner
    from agent.session import Session
    from agent.trajectory import Trajectory
    from agent_server.session_sandbox_service import effective_session_sandbox_backend

    config = Config.load()
    # Per-chat model override (in-memory only — never mark dirty / save).
    session_provider = (provider or "").strip()
    session_model = (model or "").strip()
    session_profile = (openai_profile_id or "").strip()
    if session_provider:
        config._data["llm.provider"] = session_provider
    if session_model:
        config._data["llm.model"] = session_model
    if session_profile:
        try:
            config.set_openai_active_profile(session_profile)
        except Exception:  # noqa: BLE001
            pass
    try:
        profile = config.get_openai_profile()
    except Exception:  # noqa: BLE001
        profile = None
    if isinstance(profile, dict) and str(profile.get("backend") or "").strip().lower() == "llama":
        from agent_server.llama_runtime import wait_until_serving

        wait_until_serving()
    # Throwaway in-memory config for this run — never persist overrides.
    config._dirty_keys.clear()
    if workspace_path:
        # Keep sandbox plots/CSVs inside the session workspace so the UI
        # file tree can list agent-generated artifacts for this chat.
        output_dir = Path(workspace_path).expanduser().resolve() / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        config.set("sandbox.output_dir", str(output_dir))
    session = Session(config=config, verbose=False, mode="batch")
    trajectory = Trajectory(session_id=session_id)
    pending_user: str | None = None
    for message in history:
        if message.role == "user":
            pending_user = message.content
        elif message.role == "assistant" and pending_user is not None:
            trajectory.add_turn(pending_user, message.content)
            pending_user = None
    from agent.mcp_server.tool_handler import tool_session_var

    token = tool_session_var.set(session)
    runner = AgentRunner(session, trajectory=trajectory, headless=True)
    if on_runner_ready is not None:
        on_runner_ready(runner)
    try:
        context: dict = {"workspace_path": workspace_path} if workspace_path else {}
        if session_id:
            context["session_id"] = session_id
        effective_backend = effective_session_sandbox_backend(
            sandbox_backend, config=config
        )
        context["sandbox_backend"] = effective_backend
        if mcp_servers:
            context["mcp_servers"] = mcp_servers
        if project_context:
            context["project_context"] = project_context
        if specialist_instructions:
            context["specialist_instructions"] = specialist_instructions
        if allowed_skill_names is not None:
            context["allowed_skill_names"] = allowed_skill_names
        if allowed_tool_names is not None:
            context["allowed_tool_names"] = allowed_tool_names
        if capy_mode:
            context["capy_mode"] = True
            context["mcp_servers"] = []
        result = runner.run(content, context, progress_callback=progress_callback)
        return result.summary or "Done."
    finally:
        tool_session_var.reset(token)
        if on_runner_done is not None:
            on_runner_done()
