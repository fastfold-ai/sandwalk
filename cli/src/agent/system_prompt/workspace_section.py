"""Session-workspace + compute-environment prompt section."""

from __future__ import annotations

from .text_blocks import _compute_environment_section


def build_workspace_section(
    workspace_path: str | None,
    sandbox_backend: str | None,
) -> str:
    """Build the '## Session Workspace' block plus compute environment policy."""
    parts: list[str] = []
    workspace = str(workspace_path or "").strip()
    modal_on = str(sandbox_backend or "").strip().lower() == "modal"
    if workspace:
        parts.append("\n## Session Workspace\n")
        if modal_on:
            parts.append(
                f"- **Host path (Files panel):** `{workspace}`\n"
                "- **Modal path:** `/workspace` (same tree after sync — use this in "
                "`execute`)\n"
                "- Save **all** downloads, writes, exports, plots, and generated files "
                f"under the session tree (prefer `{workspace}/artifacts/` on host or "
                "`/workspace/artifacts/` in Modal).\n"
                "- Prefer literal absolute host paths in `shell_run` / host tools; "
                "prefer `/workspace/...` inside Modal `execute`.\n"
            )
        else:
            parts.append(
                f"- **Path:** `{workspace}`\n"
                "- This is the dedicated folder for **this chat** (Files panel / file tree).\n"
                "- Save **all** downloads, writes, exports, plots, and generated files under "
                f"this path (prefer `{workspace}/artifacts/` or `{workspace}/outputs/`).\n"
                "- Use this **absolute** path in tool commands. Do not ask where to save; "
                "do not browse `/`, `$HOME`, or `/tmp`. Prefer the literal path over "
                "`$SANDWALK_SESSION_WORKSPACE/...` (an empty var expands to `/artifacts/...`).\n"
            )

    parts.append(_compute_environment_section(sandbox_backend, workspace_path))
    return "".join(parts)
