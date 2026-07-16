"""Detect plan markdown writes and build plan.created payloads."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

_WRITE_TOOL_NAMES = {
    "files.create_file",
    "files.edit_file",
    "write_file",
    "edit_file",
    "create_file",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def extract_plan_path_from_args(arguments: Any) -> str | None:
    args = _as_dict(arguments)
    for key in ("path", "file_path", "filePath", "filename"):
        raw = str(args.get(key) or "").strip()
        if raw:
            return raw
    return None


def is_plans_markdown_path(path: str | None) -> bool:
    if not path:
        return False
    normalized = path.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if "plans" not in parts:
        return False
    return normalized.lower().endswith(".md")


def workspace_relative_plans_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    marker = "/plans/"
    idx = normalized.lower().rfind(marker)
    if idx >= 0:
        return "plans/" + normalized[idx + len(marker) :]
    name = PurePosixPath(normalized).name
    return f"plans/{name}" if name else normalized


def title_and_summary_from_markdown(content: str, *, fallback_title: str) -> tuple[str, str]:
    title = fallback_title
    summary = ""
    lines = str(content or "").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        heading = re.match(r"^#\s+(.+)$", stripped)
        if heading:
            title = heading.group(1).strip() or title
            continue
        if stripped.startswith("#"):
            continue
        if not summary:
            summary = stripped
            break
    if len(summary) > 280:
        summary = summary[:277].rstrip() + "..."
    return title, summary


def title_from_path(path: str) -> str:
    stem = PurePosixPath(path.replace("\\", "/")).stem
    words = re.split(r"[-_]+", stem)
    titled = " ".join(w for w in words if w)
    return titled.strip() or "Plan"


def plan_created_payload_from_tool_call(
    *,
    name: str,
    arguments: Any,
    output: Any = None,
) -> dict[str, str] | None:
    """Return plan.created payload when a write tool targets plans/*.md."""
    tool_name = str(name or "").strip()
    if tool_name not in _WRITE_TOOL_NAMES and not tool_name.endswith(
        (".create_file", ".edit_file", ".write_file")
    ):
        # Still allow generic names that clearly look like writes.
        if "write" not in tool_name.lower() and "create_file" not in tool_name.lower():
            path_hint = extract_plan_path_from_args(arguments)
            if not is_plans_markdown_path(path_hint):
                return None

    path = extract_plan_path_from_args(arguments)
    if not path:
        out = _as_dict(output)
        path = str(out.get("path") or "").strip() or None
    if not is_plans_markdown_path(path):
        return None

    assert path is not None
    rel = workspace_relative_plans_path(path)
    args = _as_dict(arguments)
    content = str(args.get("content") or args.get("new_string") or args.get("file_text") or "")
    if not content and isinstance(output, dict):
        content = str(output.get("content") or "")
    title, summary = title_and_summary_from_markdown(
        content, fallback_title=title_from_path(rel)
    )
    return {"path": rel, "title": title, "summary": summary}
