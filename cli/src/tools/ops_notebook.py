"""ops.notebook_*: notebook entry tools (project memory). Split from tools/ops.py."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from tools import registry
from tools.ops_common import _notebook_path, _now_iso, _parse_int


def _normalize_tags(tags: Any) -> list[str]:
    """Normalize tags from string/list input to unique lowercase tokens."""
    if tags is None:
        return []

    raw: list[str]
    if isinstance(tags, str):
        raw = [x.strip() for x in tags.split(",")]
    elif isinstance(tags, list):
        raw = [str(x).strip() for x in tags]
    else:
        raw = [str(tags).strip()]

    cleaned: list[str] = []
    seen = set()
    for tag in raw:
        if not tag:
            continue
        token = re.sub(r"\s+", "-", tag.lower())
        token = re.sub(r"[^a-z0-9._:-]", "", token)
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)

    return cleaned[:20]


def _load_notebook_entries(_session=None) -> tuple[list[dict], int, str | None]:
    """Load notebook entries from JSONL, skipping malformed lines."""
    path = _notebook_path(_session)
    if not path.exists():
        return [], 0, None

    entries: list[dict] = []
    skipped = 0
    try:
        with open(path, encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    skipped += 1
                    continue
                if isinstance(obj, dict):
                    entries.append(obj)
                else:
                    skipped += 1
    except Exception as exc:
        return [], 0, f"Failed to read notebook: {exc}"

    return entries, skipped, None


def _save_notebook_entries(entries: list[dict], _session=None) -> tuple[Path, str | None]:
    """Persist notebook entries to JSONL."""
    path = _notebook_path(_session)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry) + "\n")
        return path, None
    except Exception as exc:
        return path, f"Failed to persist notebook: {exc}"


@registry.register(
    name="ops.notebook_add",
    description="Append a structured notebook entry for project memory",
    category="ops",
    parameters={
        "title": "Short notebook entry title",
        "content": "Entry body text (markdown/plain text)",
        "tags": "Optional list of tags or comma-separated tags",
        "linked_query": "Optional source query/command that produced the insight",
    },
    usage_guide=(
        "Use after an important finding, decision, or caveat so future runs can reuse context. "
        "Prefer concise entries with tags for retrieval."
    ),
)
def notebook_add(
    title: str,
    content: str,
    tags: list[str] | str | None = None,
    linked_query: str | None = None,
    _session=None,
    **kwargs,
) -> dict:
    """Append a notebook entry to local JSONL storage."""
    title = (title or "").strip()
    content = (content or "").strip()
    if not title:
        return {"summary": "Notebook title is required.", "error": "missing_title"}
    if not content:
        return {"summary": "Notebook content is required.", "error": "missing_content"}

    entry = {
        "id": uuid4().hex[:12],
        "created_at": _now_iso(),
        "title": title,
        "content": content,
        "tags": _normalize_tags(tags),
        "linked_query": (linked_query or "").strip() or None,
    }

    path = _notebook_path(_session)
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except Exception as exc:
        return {"summary": f"Failed to save notebook entry: {exc}", "error": "write_failed"}

    return {
        "summary": f"Notebook entry saved ({entry['id']}) with {len(entry['tags'])} tags.",
        "entry": entry,
        "path": str(path),
    }


@registry.register(
    name="ops.notebook_search",
    description="Search notebook entries by keyword and/or tag",
    category="ops",
    parameters={
        "query": "Keyword query matched against title/content/linked_query",
        "tag": "Optional single tag filter",
        "limit": "Maximum entries to return (default 20, max 100)",
    },
    usage_guide=(
        "Use before planning to recover prior findings, assumptions, and unresolved risks. "
        "Combine with tags to narrow to specific projects."
    ),
)
def notebook_search(
    query: str = "",
    tag: str = "",
    limit: int = 20,
    _session=None,
    **kwargs,
) -> dict:
    """Search notebook JSONL entries."""
    limit = max(1, min(int(limit), 100))
    q = (query or "").strip().lower()
    tag_tokens = _normalize_tags([tag]) if tag else []
    tag_norm = tag_tokens[0] if tag_tokens else ""
    if tag and not tag_norm:
        return {
            "summary": "Invalid tag filter.",
            "error": "invalid_tag",
        }

    path = _notebook_path(_session)
    if not path.exists():
        return {
            "summary": f"Notebook is empty: {path}",
            "matches": [],
            "count": 0,
            "path": str(path),
        }

    matches = []
    bad_lines = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                bad_lines += 1
                continue
            if not isinstance(entry, dict):
                bad_lines += 1
                continue

            if tag_norm and tag_norm not in entry.get("tags", []):
                continue

            haystack = " ".join(
                [
                    str(entry.get("title", "")),
                    str(entry.get("content", "")),
                    str(entry.get("linked_query", "")),
                ]
            ).lower()
            if q and q not in haystack:
                continue

            preview = str(entry.get("content", "")).replace("\n", " ").strip()
            if len(preview) > 180:
                preview = preview[:177] + "..."

            matches.append(
                {
                    "id": entry.get("id"),
                    "created_at": entry.get("created_at"),
                    "title": entry.get("title"),
                    "tags": entry.get("tags", []),
                    "preview": preview,
                    "linked_query": entry.get("linked_query"),
                }
            )

    matches.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    matches = matches[:limit]

    qualifier = []
    if q:
        qualifier.append(f"query='{query}'")
    if tag_norm:
        qualifier.append(f"tag='{tag_norm}'")
    suffix = f" ({', '.join(qualifier)})" if qualifier else ""

    summary = f"Found {len(matches)} notebook entries{suffix}."
    if bad_lines:
        summary += f" Skipped {bad_lines} malformed lines."

    return {
        "summary": summary,
        "matches": matches,
        "count": len(matches),
        "path": str(path),
        "skipped_malformed_lines": bad_lines,
    }


@registry.register(
    name="ops.notebook_get",
    description="Fetch a notebook entry by ID",
    category="ops",
    parameters={"entry_id": "Notebook entry ID"},
    usage_guide="Use when you need the full text of one saved notebook entry.",
)
def notebook_get(entry_id: str, _session=None, **kwargs) -> dict:
    """Get a notebook entry by ID."""
    needle = (entry_id or "").strip()
    if not needle:
        return {"summary": "entry_id is required.", "error": "missing_entry_id"}

    entries, skipped, error = _load_notebook_entries(_session)
    if error:
        return {"summary": error, "error": "notebook_error"}

    for entry in entries:
        if str(entry.get("id", "")).strip() == needle:
            out = dict(entry)
            out["summary"] = f"Notebook entry {needle} loaded."
            if skipped:
                out["summary"] += f" Skipped {skipped} malformed lines while loading."
            out["path"] = str(_notebook_path(_session))
            return out

    return {"summary": f"Notebook entry not found: {needle}", "error": "not_found"}


@registry.register(
    name="ops.notebook_list",
    description="List recent notebook entries",
    category="ops",
    parameters={
        "limit": "Maximum entries to return (default 20, max 200)",
        "tag": "Optional tag filter",
    },
    usage_guide="Use for a quick overview of recent project notes.",
)
def notebook_list(limit: int = 20, tag: str = "", _session=None, **kwargs) -> dict:
    """List notebook entries sorted by recency."""
    limit = max(1, min(_parse_int(limit, 20), 200))
    tag_tokens = _normalize_tags([tag]) if tag else []
    tag_norm = tag_tokens[0] if tag_tokens else ""
    if tag and not tag_norm:
        return {"summary": "Invalid tag filter.", "error": "invalid_tag"}

    entries, skipped, error = _load_notebook_entries(_session)
    if error:
        return {"summary": error, "error": "notebook_error"}

    if tag_norm:
        entries = [e for e in entries if tag_norm in (e.get("tags") or [])]

    entries = sorted(entries, key=lambda x: str(x.get("created_at") or ""), reverse=True)
    entries = entries[:limit]

    items = []
    for entry in entries:
        preview = str(entry.get("content", "")).replace("\n", " ").strip()
        if len(preview) > 140:
            preview = preview[:137] + "..."
        items.append(
            {
                "id": entry.get("id"),
                "created_at": entry.get("created_at"),
                "title": entry.get("title"),
                "tags": entry.get("tags", []),
                "preview": preview,
            }
        )

    summary = f"Listed {len(items)} notebook entries."
    if tag_norm:
        summary += f" tag={tag_norm}."
    if skipped:
        summary += f" Skipped {skipped} malformed lines."

    return {
        "summary": summary,
        "entries": items,
        "count": len(items),
        "path": str(_notebook_path(_session)),
        "skipped_malformed_lines": skipped,
    }


@registry.register(
    name="ops.notebook_update",
    description="Update fields of an existing notebook entry",
    category="ops",
    parameters={
        "entry_id": "Notebook entry ID",
        "title": "Optional new title",
        "content": "Optional new content",
        "tags": "Optional replacement tags (list or comma-separated)",
        "linked_query": "Optional replacement linked query",
    },
    usage_guide="Use to correct or refine existing notes without creating duplicates.",
)
def notebook_update(
    entry_id: str,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | str | None = None,
    linked_query: str | None = None,
    _session=None,
    **kwargs,
) -> dict:
    """Update an existing notebook entry by ID."""
    needle = (entry_id or "").strip()
    if not needle:
        return {"summary": "entry_id is required.", "error": "missing_entry_id"}

    entries, skipped, error = _load_notebook_entries(_session)
    if error:
        return {"summary": error, "error": "notebook_error"}

    touched = None
    for entry in entries:
        if str(entry.get("id", "")).strip() != needle:
            continue
        if title is not None:
            entry["title"] = str(title).strip()
        if content is not None:
            entry["content"] = str(content).strip()
        if tags is not None:
            entry["tags"] = _normalize_tags(tags)
        if linked_query is not None:
            entry["linked_query"] = str(linked_query).strip() or None
        entry["updated_at"] = _now_iso()
        touched = entry
        break

    if touched is None:
        return {"summary": f"Notebook entry not found: {needle}", "error": "not_found"}
    if not str(touched.get("title", "")).strip():
        return {"summary": "Notebook title cannot be empty.", "error": "invalid_title"}
    if not str(touched.get("content", "")).strip():
        return {"summary": "Notebook content cannot be empty.", "error": "invalid_content"}

    path, error = _save_notebook_entries(entries, _session)
    if error:
        return {"summary": error, "error": "notebook_error"}

    summary = f"Notebook entry {needle} updated."
    if skipped:
        summary += f" Skipped {skipped} malformed lines while loading."
    return {"summary": summary, "entry": touched, "path": str(path)}


@registry.register(
    name="ops.notebook_delete",
    description="Delete a notebook entry by ID",
    category="ops",
    parameters={"entry_id": "Notebook entry ID"},
    usage_guide="Use to remove stale or incorrect notebook entries.",
)
def notebook_delete(entry_id: str, _session=None, **kwargs) -> dict:
    """Delete a notebook entry by ID."""
    needle = (entry_id or "").strip()
    if not needle:
        return {"summary": "entry_id is required.", "error": "missing_entry_id"}

    entries, skipped, error = _load_notebook_entries(_session)
    if error:
        return {"summary": error, "error": "notebook_error"}

    original = len(entries)
    kept = [e for e in entries if str(e.get("id", "")).strip() != needle]
    if len(kept) == original:
        return {"summary": f"Notebook entry not found: {needle}", "error": "not_found"}

    path, error = _save_notebook_entries(kept, _session)
    if error:
        return {"summary": error, "error": "notebook_error"}

    summary = f"Notebook entry deleted: {needle}."
    if skipped:
        summary += f" Skipped {skipped} malformed lines while loading."
    return {"summary": summary, "path": str(path), "count": len(kept)}
