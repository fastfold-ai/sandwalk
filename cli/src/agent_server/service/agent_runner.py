"""Adapter that drives the CLI's AgentRunner from a stored session's history."""

from __future__ import annotations

from pathlib import Path


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
) -> str:
    """Temporary adapter until AgentRunner is split into AgentRuntime."""
    from agent.config import Config
    from agent.runner import AgentRunner
    from agent.session import Session
    from agent.trajectory import Trajectory
    from agent_server.session_sandbox_service import effective_session_sandbox_backend

    config = Config.load()
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
    runner = AgentRunner(session, trajectory=trajectory, headless=True)
    context: dict = {"workspace_path": workspace_path} if workspace_path else {}
    if session_id:
        context["session_id"] = session_id
    effective_backend = effective_session_sandbox_backend(sandbox_backend, config=config)
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
    result = runner.run(content, context, progress_callback=progress_callback)
    return result.summary or "Done."
