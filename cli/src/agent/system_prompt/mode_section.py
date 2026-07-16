"""Agent mode vs plan mode system-prompt section."""

from __future__ import annotations

from pathlib import Path

_PLAN_MODE_INSTRUCTIONS = """\
## Active Mode: Plan mode

You are in **Plan mode**. Do **not** execute the research campaign or run heavy
workflows. Focus on authoring a plan the user can review.

Required actions each turn that produces a plan:
1. Create or update a markdown file under `{workspace}/plans/<descriptive-slug>.md`
   (use `files.create_file` / `files.edit_file` or equivalent write tools).
2. Call the built-in ``write_todos`` tool with the executable checklist for that plan.
3. Reply in normal chat asking whether the plan looks good or needs edits.
   There is **no** approve/reject gate — the user switches to **Agent mode**
   (or clicks Build) when they want execution.

Required markdown shape for every plan file:
1. `# Title`
2. Short overview paragraph
3. Numbered or bulleted steps
4. A **required** Mermaid flowchart of the full plan, e.g.:

```mermaid
flowchart TD
    start([User Query]) --> s1[Step one]
    s1 --> s2[Step two]
    s2 --> done([Done])
```

5. Optional risks / tools / skills notes

Do not execute the plan while Plan mode is on.
"""

_AGENT_MODE_INSTRUCTIONS = """\
## Active Mode: Agent mode

You are in **Agent mode** (normal execution). Use tools to answer the user and
carry out work. If the workspace has files under `plans/`, prefer reading the
named or latest plan when the user asks to build, execute, or run a plan.
"""


def list_recent_plan_files(workspace_path: str | None, *, limit: int = 5) -> list[str]:
    """Return newest ``plans/*.md`` paths relative to the workspace (posix)."""
    root = str(workspace_path or "").strip()
    if not root:
        return []
    plans_dir = Path(root) / "plans"
    if not plans_dir.is_dir():
        return []
    files = [p for p in plans_dir.glob("*.md") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[str] = []
    for path in files[: max(0, limit)]:
        try:
            out.append(path.relative_to(root).as_posix())
        except ValueError:
            out.append(f"plans/{path.name}")
    return out


def build_mode_section(
    *,
    plan_mode: bool,
    workspace_path: str | None = None,
) -> str:
    """Build the Agent vs Plan mode block for the system prompt."""
    workspace = str(workspace_path or "").strip() or "<session-workspace>"
    if plan_mode:
        return _PLAN_MODE_INSTRUCTIONS.format(workspace=workspace).rstrip() + "\n"

    parts = [_AGENT_MODE_INSTRUCTIONS.rstrip(), ""]
    recent = list_recent_plan_files(workspace_path)
    if recent:
        parts.append("Pending plan files in this workspace (newest first):")
        for rel in recent:
            parts.append(f"- `{rel}`")
        parts.append("")
    return "\n".join(parts)
