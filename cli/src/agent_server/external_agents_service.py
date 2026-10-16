"""Import, launch, and hand off between Sandwalk and other coding-agent CLIs.

Pure functions over the store / service / PTY manager so the HTTP routes and
the Capy tools share one implementation.
"""

from __future__ import annotations

import shlex
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agent import external_agents
from agent.external_agents.handoff import (
    first_prompt_for,
    handoff_markdown,
    launch_argv,
    write_handoff,
)
from agent.external_agents.types import AGENT_LABELS, ExternalAgentKind, ExternalTurn
from agent_server.models import AgentSession


class ExternalAgentError(ValueError):
    """User-facing failure (unknown kind, CLI not installed, session missing)."""


def _require_kind(kind: str) -> ExternalAgentKind:
    normalized = external_agents.normalize_kind(kind)
    if normalized is None:
        raise ExternalAgentError(f"Unknown agent: {kind!r}. Use claude, codex, opencode, fx, or hermes.")
    return normalized


def _require_binary(kind: ExternalAgentKind) -> str:
    path = external_agents.binary_for(kind)
    if not path:
        raise ExternalAgentError(f"{AGENT_LABELS[kind]} is not installed (no `{kind}` on PATH).")
    return path


def _existing_dir(path: str | None) -> str | None:
    if not path:
        return None
    candidate = Path(path).expanduser()
    if candidate.is_dir():
        return str(candidate.resolve())
    return None


def _home_dir() -> Path:
    """Resolved home directory; a seam so tests can point it at a temp dir."""
    return Path.home().resolve()


def _project_dir(path: str | None) -> str | None:
    """Like ``_existing_dir`` but refuses the home directory and filesystem root.

    CLI sessions are often started from ``~``. Making that the chat's
    workspace turns the Files panel into a crawl of the whole home folder.
    Returning None lets ``create_session`` allocate Sandwalk's own
    per-session workspace instead.
    """
    resolved = _existing_dir(path)
    if resolved is None:
        return None
    if Path(resolved) in {_home_dir(), Path("/")}:
        return None
    return resolved


# --- import -----------------------------------------------------------------


def _seed_messages(store: Any, session_id: str, turns: list[ExternalTurn]) -> int:
    """Write turns as Sandwalk messages, keeping order even without timestamps."""
    last = datetime.now(tz=UTC) - timedelta(seconds=len(turns) + 1)
    written = 0
    pending_tools: list[str] = []

    def flush_tools(at: datetime) -> None:
        nonlocal written
        if not pending_tools:
            return
        body = "\n".join(f"- {line}" for line in pending_tools)
        store.add_message(
            session_id=session_id,
            role="assistant",
            content=f"_Tools used:_\n{body}",
            created_at=at,
        )
        pending_tools.clear()
        written += 1

    for turn in turns:
        at = turn.at or (last + timedelta(milliseconds=1))
        if at <= last:
            at = last + timedelta(milliseconds=1)
        last = at
        if turn.role == "tool":
            pending_tools.append(turn.text)
            continue
        flush_tools(at - timedelta(microseconds=500))
        store.add_message(session_id=session_id, role=turn.role, content=turn.text, created_at=at)
        written += 1
    flush_tools(last + timedelta(milliseconds=1))
    return written


def import_session(
    *,
    service: Any,
    store: Any,
    kind: str,
    session_id: str,
    project_id: str | None = None,
    workspace_path: str | None = None,
    client_surface: str | None = "ui",
) -> AgentSession:
    """Create a Sandwalk session seeded with another CLI's transcript."""
    normalized = _require_kind(kind)
    external = external_agents.read_session(normalized, session_id)
    if external is None or not external.turns:
        raise ExternalAgentError(f"{AGENT_LABELS[normalized]} session not found or empty: {session_id}")
    # An explicit workspace from the caller wins; the CLI's own cwd is used
    # only when it looks like a project folder (not ~ or /).
    workspace = _existing_dir(workspace_path) or _project_dir(external.summary.cwd)
    label = AGENT_LABELS[normalized]
    # Prefix the tool so a one-word prompt ("hi") is findable among other chats.
    title = f"{label} · {external.summary.title}".strip(" ·")
    created = service.create_session(
        title=title,
        workspace_path=workspace,
        project_id=project_id,
        source=normalized,
        source_label=f"{label} · {external.summary.id[:8]}",
        client_surface=client_surface,
    )
    _seed_messages(store, created.id, external.turns)
    # Imported history is a settled title, not a placeholder to auto-rename.
    settled = store.update_session(created.id, title=title, title_source="user")
    return settled or store.get_session(created.id) or created


# --- launch -----------------------------------------------------------------


def startup_command(kind: ExternalAgentKind, *, prompt: str | None = None, resume_id: str | None = None) -> str:
    binary = _require_binary(kind)
    if resume_id:
        if kind == "claude":
            argv = [binary, "--resume", resume_id]
        elif kind == "codex":
            argv = [binary, "resume", resume_id]
        elif kind == "opencode":
            argv = [binary, "-s", resume_id]
        elif kind == "hermes":
            argv = [binary, "--resume", resume_id]
        else:
            argv = [binary, "resume", resume_id]
    else:
        argv = launch_argv(kind, binary, prompt=prompt)
    return shlex.join(argv)


async def launch_terminal(
    *,
    store: Any,
    pty_manager: Any,
    kind: str,
    workspace_path: str | None,
    project_id: str | None = None,
    origin_chat_id: str | None = None,
    prompt: str | None = None,
    resume_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Open a terminal tab running the agent CLI in ``workspace_path``."""
    normalized = _require_kind(kind)
    command = startup_command(normalized, prompt=prompt, resume_id=resume_id)
    cwd = _existing_dir(workspace_path) or str(Path.home())
    terminal = store.create_terminal(
        title=title or AGENT_LABELS[normalized],
        project_id=project_id,
        workspace_path=cwd,
        shell=None,
        origin_chat_id=origin_chat_id,
        slot_key=None,
    )
    info = await pty_manager.create(session_id=terminal.id, cwd=cwd, title=terminal.title, startup=command)
    return {
        "terminal": terminal.model_dump(mode="json", by_alias=True),
        "pty": info.to_dict(),
        "command": command,
        "kind": normalized,
    }


# --- handoff ----------------------------------------------------------------


def export_handoff(
    *, service: Any, store: Any, session_id: str, kind: str, native: bool = False
) -> dict[str, Any]:
    """Prepare a Sandwalk session for another CLI.

    Default: write a Markdown handoff file and return the opening prompt.
    ``native`` (Claude Code / Codex only): also write the CLI's own session
    file so it can ``resume`` with the transcript as real history. The
    Markdown file is still written, so a CLI update that rejects the native
    file leaves the user with a working fallback.
    """
    from agent.external_agents.writers import NATIVE_WRITERS, write_native_session

    normalized = _require_kind(kind)
    session = service.ensure_workspace(session_id)
    if not session.workspace_path:
        raise ExternalAgentError("Session has no workspace folder to hand off from.")
    messages = store.list_messages(session_id)
    markdown = handoff_markdown(title=session.title, messages=messages)
    path = write_handoff(session.workspace_path, session_id, markdown)
    prompt = first_prompt_for(normalized, path, session.workspace_path)
    result: dict[str, Any] = {
        "kind": normalized,
        "path": str(path),
        "prompt": prompt,
        "workspacePath": session.workspace_path,
        "messages": sum(1 for m in messages if m.role in ("user", "assistant")),
        "native": False,
    }
    if native:
        if normalized not in NATIVE_WRITERS:
            raise ExternalAgentError(
                f"{AGENT_LABELS[normalized]} has no native session import; use the handoff file."
            )
        try:
            resume_id, native_path = write_native_session(
                normalized, cwd=session.workspace_path, title=session.title, messages=messages
            )
        except ValueError as exc:
            raise ExternalAgentError(str(exc)) from exc
        result.update({"native": True, "resumeId": resume_id, "nativePath": str(native_path)})
    return result


def list_installed() -> list[dict[str, Any]]:
    return external_agents.installed_agents()


def list_external(kind: str | None, cwd: str | None, limit: int) -> list[dict[str, Any]]:
    if kind:
        _require_kind(kind)
    return [row.to_dict() for row in external_agents.list_sessions(kind, cwd=cwd, limit=limit)]
