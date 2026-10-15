"""Export a Sandwalk transcript as a Markdown handoff file another CLI can read."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.external_agents.types import AGENT_LABELS, ExternalAgentKind

HANDOFF_DIR = ".sandwalk"


def handoff_markdown(*, title: str, messages: list[Any], source_url: str | None = None) -> str:
    """Render user/assistant messages as a compact Markdown transcript."""
    lines: list[str] = [f"# {title or 'Sandwalk session'}", ""]
    lines.append(
        "This is a transcript exported from Sandwalk. Continue the work from where it ends; "
        "do not repeat completed steps."
    )
    if source_url:
        lines.append(f"Original session: {source_url}")
    lines.append("")
    for message in messages:
        role = str(getattr(message, "role", "") or "")
        content = str(getattr(message, "content", "") or "").strip()
        if not content or role not in ("user", "assistant"):
            continue
        heading = "User" if role == "user" else "Assistant"
        lines.append(f"## {heading}")
        lines.append("")
        lines.append(content)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_handoff(workspace: str, session_id: str, markdown: str) -> Path:
    folder = Path(workspace).expanduser().resolve() / HANDOFF_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"handoff-{session_id[:8]}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def first_prompt_for(kind: ExternalAgentKind, handoff_path: Path, workspace: str) -> str:
    """The opening message typed into the launched CLI."""
    try:
        rel = handoff_path.relative_to(Path(workspace).expanduser().resolve())
        shown = str(rel)
    except ValueError:
        shown = str(handoff_path)
    return (
        f"Read {shown}. It is a Sandwalk transcript of work in this folder. "
        f"Pick up where it ends and tell me the next step."
    )


def launch_argv(kind: ExternalAgentKind, binary: str, *, prompt: str | None = None) -> list[str]:
    """Command line that opens the agent interactively, optionally with a first prompt."""
    if kind == "claude":
        return [binary, prompt] if prompt else [binary]
    if kind == "codex":
        return [binary, prompt] if prompt else [binary]
    if kind == "opencode":
        return [binary, "--prompt", prompt] if prompt else [binary]
    if kind == "fx":
        return [binary, prompt] if prompt else [binary]
    if kind == "hermes":
        # On a TTY, `chat -q` seeds an interactive session with that first turn.
        return [binary, "chat", "-q", prompt] if prompt else [binary]
    return [binary]


def label(kind: str) -> str:
    return AGENT_LABELS.get(kind, kind)
